import os
import secrets
from pathlib import Path

from flask import Flask, abort, request, session

from backend.authentication import load_user
from backend.database import close_db, init_db
from backend.routes import main


BASE_DIR = Path(__file__).resolve().parent


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("HOMEVALUE_SECRET_KEY", "local-development-key-change-before-deployment"),
        DATABASE=os.environ.get("HOMEVALUE_DATABASE", str(BASE_DIR / "instance" / "homevalue.db")),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER_EXTERNAL_HOSTNAME")),
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.register_blueprint(main)
    app.before_request(load_user)
    @app.before_request
    def protect_forms():
        token = session.setdefault("csrf_token", secrets.token_hex(24))
        if request.method == "POST":
            submitted = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
            if not submitted or not secrets.compare_digest(token, submitted):
                abort(400, description="The form expired or could not be verified. Please try again.")

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
