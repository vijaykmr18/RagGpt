import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, session, url_for

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from routes.auth import auth_bp
from routes.chat import chat_bp
from routes.upload import upload_bp

load_dotenv()


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )

    app.secret_key = os.getenv("SECRET_KEY", "dev-change-me")
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"

    app.register_blueprint(auth_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(chat_bp)

    @app.route("/")
    def home():
        if not session.get("user_id"):
            return redirect(url_for("auth.signin_page"))
        return render_template("dashboard.html", user_email=session.get("user_email", ""))

    @app.errorhandler(413)
    def file_too_large(_error):
        return {"error": "PDF is too large for this deployment."}, 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG") == "1",
        port=int(os.getenv("PORT", "5000")),
    )
