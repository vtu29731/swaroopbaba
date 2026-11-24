import json
import re
import secrets
import sqlite3
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Blueprint, abort, flash, g, jsonify, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from backend.authentication import admin_required, login_required
from backend.database import get_db
from ml.predict import predict_price
from ml.train_model import MODELS, train_models


main = Blueprint("main", __name__)
MODEL_METRICS = MODELS / "model_metrics.json"
PROPERTY_TYPES = ["Apartment", "Villa", "Independent House"]
CITIES = ["Ahmedabad", "Bengaluru", "Chennai", "Delhi", "Hyderabad", "Kolkata", "Mumbai", "Pune"]
LOCATIONS = [
    "Whitefield", "Sarjapur Road", "Electronic City", "Indiranagar", "Powai", "Thane",
    "Andheri", "Navi Mumbai", "Baner", "Hinjewadi", "Wakad", "Kharadi", "Gachibowli",
    "Kondapur", "Miyapur", "Banjara Hills", "Dwarka", "Rohini", "Saket", "Noida Extension",
    "OMR", "Velachery", "Porur", "Anna Nagar", "New Town", "Salt Lake", "Rajarhat",
    "Behala", "Satellite", "Bopal", "Prahlad Nagar", "Gota",
]


def _safe_next(value):
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/") or value.startswith("//"):
        return None
    return value


def _prediction_values(source):
    city = source.get("city", "").strip()
    location = source.get("location", "").strip()
    property_type = source.get("property_type", "").strip()
    parking = source.get("parking", "").strip()
    furnishing = source.get("furnishing", "").strip()
    if city not in CITIES:
        raise ValueError("Choose a valid city.")
    if not location or len(location) > 80:
        raise ValueError("Enter a valid location.")
    if property_type not in PROPERTY_TYPES:
        raise ValueError("Choose a valid property type.")
    if parking not in {"Yes", "No"}:
        raise ValueError("Choose whether parking is available.")
    if furnishing not in {"Unfurnished", "Semi-furnished", "Furnished"}:
        raise ValueError("Choose a furnishing status.")
    try:
        area = float(source.get("area_sqft", ""))
        bedrooms = int(source.get("bedrooms", ""))
        bathrooms = int(source.get("bathrooms", ""))
        age = int(source.get("property_age", ""))
    except (TypeError, ValueError):
        raise ValueError("Area, bedrooms, bathrooms and age must be valid numbers.") from None
    if not 200 <= area <= 20000:
        raise ValueError("Area must be between 200 and 20,000 square feet.")
    if not 1 <= bedrooms <= 12 or not 1 <= bathrooms <= 12:
        raise ValueError("Bedrooms and bathrooms must be between 1 and 12.")
    if not 0 <= age <= 150:
        raise ValueError("Property age must be between 0 and 150 years.")
    return {
        "city": city, "location": location, "property_type": property_type,
        "area_sqft": area, "bedrooms": bedrooms, "bathrooms": bathrooms,
        "property_age": age, "parking": parking, "furnishing": furnishing,
    }


@main.app_context_processor
def template_context():
    return {
        "current_user": g.get("user"),
        "current_is_admin": g.get("is_admin", False),
        "csrf_token": session.get("csrf_token", ""),
    }


@main.route("/")
def home():
    featured = get_db().execute(
        "SELECT * FROM properties ORDER BY id DESC LIMIT 3"
    ).fetchall()
    return render_template("index.html", properties=featured)


@main.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(name) < 2 or len(name) > 80:
            flash("Name must be between 2 and 80 characters.", "error")
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Enter a valid email address.", "error")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        elif password != confirm:
            flash("The passwords do not match.", "error")
        else:
            try:
                cursor = get_db().execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
                get_db().commit()
                session.clear()
                session["user_id"] = cursor.lastrowid
                flash("Your account is ready. Welcome to HomeValue!", "success")
                return redirect(url_for("main.dashboard"))
            except sqlite3.IntegrityError:
                flash("An account with that email already exists.", "error")
    return render_template("register.html")


@main.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.dashboard"))
    next_url = _safe_next(request.values.get("next"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Email or password is incorrect.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(next_url or url_for("main.dashboard"))
    return render_template("login.html", next_url=next_url or "")


@main.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("main.home"))


@main.route("/properties")
def properties():
    db = get_db()
    clauses, values = [], []
    filters = {
        "city": request.args.get("city", "").strip(),
        "location": request.args.get("location", "").strip(),
        "property_type": request.args.get("property_type", "").strip(),
    }
    for column, value in filters.items():
        if value:
            if column == "property_type" and value not in PROPERTY_TYPES:
                continue
            clauses.append(f"{column} = ?")
            values.append(value)
    numeric_filters = [
        ("min_price", "price", ">=", 0, 1_000_000_000),
        ("max_price", "price", "<=", 0, 1_000_000_000),
        ("bedrooms", "bedrooms", ">=", 1, 12),
        ("min_area", "area_sqft", ">=", 200, 20000),
        ("max_area", "area_sqft", "<=", 200, 20000),
    ]
    for param, column, operator, minimum, maximum in numeric_filters:
        raw = request.args.get(param, "").strip()
        if raw:
            try:
                number = float(raw)
            except ValueError:
                continue
            if minimum <= number <= maximum:
                clauses.append(f"{column} {operator} ?")
                values.append(number)
    query = "SELECT * FROM properties"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id DESC"
    listings = db.execute(query, values).fetchall()
    saved_ids = set()
    if g.user:
        saved_ids = {row["property_id"] for row in db.execute(
            "SELECT property_id FROM saved_properties WHERE user_id = ?", (g.user["id"],)
        )}
    return render_template(
        "properties.html", properties=listings, saved_ids=saved_ids, filters=filters,
        cities=CITIES, property_types=PROPERTY_TYPES,
    )


@main.route("/properties/<int:property_id>")
def property_details(property_id):
    listing = get_db().execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    if listing is None:
        abort(404)
    saved = False
    if g.user:
        saved = get_db().execute(
            "SELECT 1 FROM saved_properties WHERE user_id = ? AND property_id = ?",
            (g.user["id"], property_id),
        ).fetchone() is not None
    return render_template("property_details.html", property=listing, saved=saved)


@main.route("/properties/<int:property_id>/save", methods=["POST"])
@login_required
def save_property(property_id):
    db = get_db()
    if db.execute("SELECT id FROM properties WHERE id = ?", (property_id,)).fetchone() is None:
        abort(404)
    db.execute(
        "INSERT OR IGNORE INTO saved_properties (user_id, property_id) VALUES (?, ?)",
        (g.user["id"], property_id),
    )
    db.commit()
    flash("Property saved to your favourites.", "success")
    return redirect(request.form.get("next") or url_for("main.saved_properties"))


@main.route("/properties/<int:property_id>/remove", methods=["POST"])
@login_required
def remove_saved_property(property_id):
    db = get_db()
    db.execute(
        "DELETE FROM saved_properties WHERE user_id = ? AND property_id = ?",
        (g.user["id"], property_id),
    )
    db.commit()
    flash("Property removed from your saved list.", "success")
    return redirect(request.form.get("next") or url_for("main.saved_properties"))


@main.route("/saved")
@login_required
def saved_properties():
    listings = get_db().execute(
        """SELECT p.* FROM properties p JOIN saved_properties s ON p.id = s.property_id
           WHERE s.user_id = ? ORDER BY s.created_at DESC""",
        (g.user["id"],),
    ).fetchall()
    return render_template("saved_properties.html", properties=listings)


@main.route("/predict", methods=["GET", "POST"])
@login_required
def predict():
    result = None
    details = None
    if request.method == "POST":
        try:
            details = _prediction_values(request.form)
            result = predict_price(details)
            db = get_db()
            cursor = db.execute(
                """INSERT INTO predictions
                   (user_id, city, location, property_type, area_sqft, bedrooms, bathrooms,
                    property_age, parking, furnishing, predicted_price, price_per_sqft, model_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (g.user["id"], details["city"], details["location"], details["property_type"],
                 details["area_sqft"], details["bedrooms"], details["bathrooms"],
                 details["property_age"], details["parking"], details["furnishing"],
                 result["predicted_price"], result["price_per_sqft"], result["model_name"]),
            )
            db.commit()
            result["id"] = cursor.lastrowid
        except ValueError as error:
            flash(str(error), "error")
        except (OSError, RuntimeError) as error:
            main.logger.exception("Price prediction failed")
            flash(f"Prediction is temporarily unavailable: {error}", "error")
        if result:
            return render_template("prediction_result.html", result=result, details=details)
    return render_template(
        "predict.html", cities=CITIES, locations=LOCATIONS, property_types=PROPERTY_TYPES,
        form_data=request.form if request.method == "POST" else {},
    )


@main.route("/api/predict", methods=["POST"])
@login_required
def predict_api():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Send a JSON object with property details."), 400
    try:
        details = _prediction_values(payload)
        result = predict_price(details)
        db = get_db()
        cursor = db.execute(
            """INSERT INTO predictions
               (user_id, city, location, property_type, area_sqft, bedrooms, bathrooms,
                property_age, parking, furnishing, predicted_price, price_per_sqft, model_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (g.user["id"], details["city"], details["location"], details["property_type"],
             details["area_sqft"], details["bedrooms"], details["bathrooms"],
             details["property_age"], details["parking"], details["furnishing"],
             result["predicted_price"], result["price_per_sqft"], result["model_name"]),
        )
        db.commit()
        return jsonify(id=cursor.lastrowid, **result, details=details), 201
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except (OSError, RuntimeError) as error:
        main.logger.exception("Prediction API failed")
        return jsonify(error=f"Prediction is temporarily unavailable: {error}"), 503


@main.route("/api/session")
def api_session():
    return jsonify(
        user={"id": g.user["id"], "name": g.user["name"], "email": g.user["email"]}
        if g.user else None,
        csrf_token=session.get("csrf_token", ""),
    )


@main.route("/api/auth/register", methods=["POST"])
def api_register():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    confirm_password = str(payload.get("confirm_password", ""))
    if len(name) < 2 or len(name) > 80:
        return jsonify(error="Name must be between 2 and 80 characters."), 400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify(error="Enter a valid email address."), 400
    if len(password) < 8:
        return jsonify(error="Password must contain at least 8 characters."), 400
    if password != confirm_password:
        return jsonify(error="The passwords do not match."), 400
    try:
        cursor = get_db().execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        get_db().commit()
    except sqlite3.IntegrityError:
        return jsonify(error="An account with that email already exists."), 409
    session.clear()
    session["user_id"] = cursor.lastrowid
    session["csrf_token"] = secrets.token_hex(24)
    return jsonify(
        user={"id": cursor.lastrowid, "name": name, "email": email},
        csrf_token=session["csrf_token"],
    ), 201


@main.route("/api/auth/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Email or password is incorrect."), 401
    session.clear()
    session["user_id"] = user["id"]
    session["csrf_token"] = secrets.token_hex(24)
    return jsonify(
        user={"id": user["id"], "name": user["name"], "email": user["email"]},
        csrf_token=session["csrf_token"],
    )


@main.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    session.clear()
    session["csrf_token"] = secrets.token_hex(24)
    return jsonify(ok=True, csrf_token=session["csrf_token"])


@main.route("/api/properties")
def api_properties():
    db = get_db()
    clauses, values = [], []
    for column in ("city", "location", "property_type"):
        value = request.args.get(column, "").strip()
        if value:
            clauses.append(f"{column} = ?")
            values.append(value)
    if request.args.get("q", "").strip():
        query = f"%{request.args['q'].strip()}%"
        clauses.append("(name LIKE ? OR city LIKE ? OR location LIKE ?)")
        values.extend([query, query, query])
    for param, column, operator in (
        ("min_price", "price", ">="), ("max_price", "price", "<="),
        ("bedrooms", "bedrooms", ">="), ("min_area", "area_sqft", ">="),
        ("max_area", "area_sqft", "<="),
    ):
        raw = request.args.get(param, "").strip()
        if raw:
            try:
                number = float(raw)
            except ValueError:
                continue
            clauses.append(f"{column} {operator} ?")
            values.append(number)
    sql = "SELECT * FROM properties"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC"
    listings = db.execute(sql, values).fetchall()
    saved = set()
    if g.user:
        saved = {row["property_id"] for row in db.execute(
            "SELECT property_id FROM saved_properties WHERE user_id = ?", (g.user["id"],)
        )}
    return jsonify(properties=[
        {**dict(listing), "is_saved": listing["id"] in saved}
        for listing in listings
    ])


@main.route("/api/saved", methods=["GET"])
@login_required
def api_saved_properties():
    listings = get_db().execute(
        """SELECT p.* FROM properties p JOIN saved_properties s ON p.id = s.property_id
           WHERE s.user_id = ? ORDER BY s.created_at DESC""",
        (g.user["id"],),
    ).fetchall()
    return jsonify(properties=[dict(listing) for listing in listings])


@main.route("/api/saved/<int:property_id>", methods=["POST", "DELETE"])
@login_required
def api_toggle_saved(property_id):
    db = get_db()
    if db.execute("SELECT id FROM properties WHERE id = ?", (property_id,)).fetchone() is None:
        return jsonify(error="Property not found."), 404
    if request.method == "POST":
        db.execute(
            "INSERT OR IGNORE INTO saved_properties (user_id, property_id) VALUES (?, ?)",
            (g.user["id"], property_id),
        )
    else:
        db.execute(
            "DELETE FROM saved_properties WHERE user_id = ? AND property_id = ?",
            (g.user["id"], property_id),
        )
    db.commit()
    return jsonify(ok=True, saved=request.method == "POST")


@main.route("/api/dashboard")
@login_required
def api_dashboard():
    db = get_db()
    predictions = db.execute(
        "SELECT * FROM predictions WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (g.user["id"],),
    ).fetchall()
    prediction_count = db.execute(
        "SELECT COUNT(*) FROM predictions WHERE user_id = ?", (g.user["id"],)
    ).fetchone()[0]
    saved_count = db.execute(
        "SELECT COUNT(*) FROM saved_properties WHERE user_id = ?", (g.user["id"],)
    ).fetchone()[0]
    return jsonify(
        prediction_count=prediction_count,
        saved_count=saved_count,
        predictions=[dict(row) for row in predictions],
    )


@main.route("/api/history")
@login_required
def api_history():
    predictions = get_db().execute(
        "SELECT * FROM predictions WHERE user_id = ? ORDER BY created_at DESC",
        (g.user["id"],),
    ).fetchall()
    return jsonify(predictions=[dict(row) for row in predictions])


@main.route("/api/model-performance")
def api_model_performance():
    return jsonify(_get_metrics())


@main.route("/react")
def react_app():
    return render_template("react_app.html")


@main.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    prediction_count = db.execute(
        "SELECT COUNT(*) FROM predictions WHERE user_id = ?", (g.user["id"],)
    ).fetchone()[0]
    saved_count = db.execute(
        "SELECT COUNT(*) FROM saved_properties WHERE user_id = ?", (g.user["id"],)
    ).fetchone()[0]
    recent = db.execute(
        "SELECT * FROM predictions WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
        (g.user["id"],),
    ).fetchall()
    return render_template(
        "dashboard.html", prediction_count=prediction_count, saved_count=saved_count, predictions=recent
    )


@main.route("/history")
@login_required
def history():
    predictions = get_db().execute(
        "SELECT * FROM predictions WHERE user_id = ? ORDER BY created_at DESC",
        (g.user["id"],),
    ).fetchall()
    return render_template("history.html", predictions=predictions)


def _get_metrics():
    if not MODEL_METRICS.exists():
        train_models()
    with MODEL_METRICS.open(encoding="utf-8") as file:
        return json.load(file)


@main.route("/model-performance")
def model_performance():
    return render_template("model_performance.html", model_results=_get_metrics())


@main.route("/about")
def about():
    return render_template("about.html")


@main.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if g.is_admin:
        return redirect(url_for("main.admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = get_db().execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        if admin is None or not check_password_hash(admin["password_hash"], password):
            flash("Admin username or password is incorrect.", "error")
        else:
            session.clear()
            session["admin_id"] = admin["id"]
            return redirect(url_for("main.admin_dashboard"))
    return render_template("admin_login.html")


@main.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("main.home"))


@main.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    totals = {
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "properties": db.execute("SELECT COUNT(*) FROM properties").fetchone()[0],
        "predictions": db.execute("SELECT COUNT(*) FROM predictions").fetchone()[0],
    }
    listings = db.execute("SELECT * FROM properties ORDER BY id DESC").fetchall()
    return render_template("admin_dashboard.html", totals=totals, properties=listings)


def _property_form_values(source):
    name = source.get("name", "").strip()
    city = source.get("city", "").strip()
    location = source.get("location", "").strip()
    kind = source.get("property_type", "").strip()
    image = source.get("image_url", "").strip()
    description = source.get("description", "").strip()
    try:
        area = float(source.get("area_sqft", ""))
        beds = int(source.get("bedrooms", ""))
        baths = int(source.get("bathrooms", ""))
        price = float(source.get("price", ""))
    except (ValueError, TypeError):
        raise ValueError("Area, bedrooms, bathrooms, and price must be valid numbers.") from None
    if not name or len(name) > 100 or not city or not location:
        raise ValueError("Name, city, and location are required.")
    if kind not in PROPERTY_TYPES or not 200 <= area <= 20000 or not 1 <= beds <= 12 or not 1 <= baths <= 12:
        raise ValueError("Choose a valid property type and enter realistic area/room values.")
    if not 300000 <= price <= 1_000_000_000:
        raise ValueError("Price must be between ₹3 lakh and ₹100 crore.")
    if image and not image.startswith(("https://", "http://")):
        raise ValueError("Image URL must start with http:// or https://.")
    return name, city, location, kind, area, beds, baths, price, image, description


@main.route("/admin/properties/new", methods=["GET", "POST"])
@admin_required
def admin_add_property():
    if request.method == "POST":
        try:
            values = _property_form_values(request.form)
            get_db().execute(
                """INSERT INTO properties
                   (name, city, location, property_type, area_sqft, bedrooms, bathrooms,
                    price, image_url, description, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                values,
            )
            get_db().commit()
            flash("Property listing created.", "success")
            return redirect(url_for("main.admin_dashboard"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("admin_property_form.html", property=None)


@main.route("/admin/properties/<int:property_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_property(property_id):
    listing = get_db().execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    if listing is None:
        abort(404)
    if request.method == "POST":
        try:
            values = _property_form_values(request.form)
            get_db().execute(
                """UPDATE properties SET name=?, city=?, location=?, property_type=?,
                   area_sqft=?, bedrooms=?, bathrooms=?, price=?, image_url=?, description=?
                   WHERE id=?""",
                (*values, property_id),
            )
            get_db().commit()
            flash("Property listing updated.", "success")
            return redirect(url_for("main.admin_dashboard"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("admin_property_form.html", property=listing)


@main.route("/admin/properties/<int:property_id>/delete", methods=["POST"])
@admin_required
def admin_delete_property(property_id):
    db = get_db()
    db.execute("DELETE FROM saved_properties WHERE property_id = ?", (property_id,))
    db.execute("DELETE FROM properties WHERE id = ?", (property_id,))
    db.commit()
    flash("Property listing deleted.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main.route("/admin/users")
@admin_required
def admin_users():
    users = get_db().execute("SELECT id, name, email, created_at FROM users ORDER BY id DESC").fetchall()
    return render_template("admin_users.html", users=users)


@main.route("/admin/predictions")
@admin_required
def admin_predictions():
    predictions = get_db().execute(
        """SELECT p.*, u.name AS user_name, u.email AS user_email
           FROM predictions p JOIN users u ON u.id = p.user_id
           ORDER BY p.created_at DESC"""
    ).fetchall()
    return render_template("admin_predictions.html", predictions=predictions)
