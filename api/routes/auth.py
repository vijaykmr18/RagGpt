import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

from db import DatabaseConfigError, ensure_indexes, get_db

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def request_data():
    return request.get_json(silent=True) or request.form


def auth_error(message, status=400):
    return jsonify({"error": message}), status


@auth_bp.route("/signin", methods=["GET"])
def signin_page():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("auth.html", mode="signin")


@auth_bp.route("/signup", methods=["GET"])
def signup_page():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("auth.html", mode="signup")


@auth_bp.route("/api/auth/signup", methods=["POST"])
@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request_data()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or email.split("@")[0]).strip()

    if not EMAIL_RE.match(email):
        return auth_error("Enter a valid email address.")
    if len(password) < 8:
        return auth_error("Password must be at least 8 characters.")

    try:
        ensure_indexes()
        result = get_db().users.insert_one(
            {
                "email": email,
                "name": name,
                "password_hash": generate_password_hash(password),
                "created_at": datetime.now(timezone.utc),
            }
        )
    except DuplicateKeyError:
        return auth_error("An account already exists for this email.")
    except DatabaseConfigError as error:
        return auth_error(str(error), 500)

    session.clear()
    session["user_id"] = str(result.inserted_id)
    session["user_email"] = email

    return jsonify({"message": "Signup successful", "redirect": "/"})


@auth_bp.route("/api/auth/signin", methods=["POST"])
@auth_bp.route("/login", methods=["POST"])
def signin():
    data = request_data()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return auth_error("Email and password are required.")

    try:
        ensure_indexes()
        user = get_db().users.find_one({"email": email})
    except DatabaseConfigError as error:
        return auth_error(str(error), 500)

    if not user or not check_password_hash(user.get("password_hash", ""), password):
        return auth_error("Invalid email or password.", 401)

    session.clear()
    session["user_id"] = str(user["_id"])
    session["user_email"] = user["email"]

    return jsonify({"message": "Signin successful", "redirect": "/"})


@auth_bp.route("/api/auth/logout", methods=["POST"])
@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    if request.method == "GET":
        return redirect(url_for("auth.signin_page"))
    return jsonify({"message": "Signed out", "redirect": "/signin"})


@auth_bp.route("/api/me", methods=["GET"])
def me():
    if not session.get("user_id"):
        return jsonify({"authenticated": False})
    return jsonify(
        {
            "authenticated": True,
            "email": session.get("user_email"),
        }
    )
