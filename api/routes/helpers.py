from functools import wraps

from flask import jsonify, redirect, request, session, url_for


def wants_json():
    return request.path.startswith("/api/") or request.is_json


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id"):
            return view(*args, **kwargs)

        if wants_json():
            return jsonify({"error": "Please sign in first."}), 401

        return redirect(url_for("auth.signin_page"))

    return wrapped


def current_user_id():
    return session.get("user_id")
