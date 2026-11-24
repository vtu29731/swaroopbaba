from functools import wraps

from flask import g, redirect, request, session, url_for

from backend.database import get_db


def load_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id:
        g.user = get_db().execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if g.user is None:
            session.pop("user_id", None)
    g.is_admin = bool(session.get("admin_id"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("main.login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.is_admin:
            return redirect(url_for("main.admin_login"))
        return view(*args, **kwargs)
    return wrapped
