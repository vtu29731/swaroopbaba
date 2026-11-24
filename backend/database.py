import os
import sqlite3
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


ROOT = Path(__file__).resolve().parent.parent
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    location TEXT NOT NULL,
    property_type TEXT NOT NULL,
    area_sqft REAL NOT NULL,
    bedrooms INTEGER NOT NULL,
    bathrooms INTEGER NOT NULL,
    price REAL NOT NULL,
    image_url TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    is_demo INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    city TEXT NOT NULL,
    location TEXT NOT NULL,
    property_type TEXT NOT NULL,
    area_sqft REAL NOT NULL,
    bedrooms INTEGER NOT NULL,
    bathrooms INTEGER NOT NULL,
    property_age INTEGER NOT NULL,
    parking TEXT NOT NULL,
    furnishing TEXT NOT NULL,
    predicted_price REAL NOT NULL,
    price_per_sqft REAL NOT NULL,
    model_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS saved_properties (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, property_id)
);
"""

DEMO_PROPERTIES = [
    ("Greenwood Residences", "Bengaluru", "Whitefield", "Apartment", 1420, 3, 2, 14800000, "photo-1600607687939-ce8a6c25118c"),
    ("Lakeview Courtyard", "Bengaluru", "Sarjapur Road", "Villa", 2460, 4, 3, 29800000, "photo-1600047509807-ba8f99d2cdde"),
    ("The Palm House", "Mumbai", "Powai", "Apartment", 1180, 2, 2, 23100000, "photo-1600566753086-00f18fb6b3ea"),
    ("Cedar Park Homes", "Pune", "Baner", "Independent House", 1860, 3, 3, 17400000, "photo-1600585154340-be6161a56a0c"),
    ("Skyline Gardens", "Hyderabad", "Gachibowli", "Apartment", 1550, 3, 2, 13200000, "photo-1600607687920-4e2a09cf159d"),
    ("Maple Grove", "Delhi", "Dwarka", "Apartment", 1260, 2, 2, 11900000, "photo-1600566753190-17f0baa2a6c3"),
    ("Olive Tree Estate", "Chennai", "OMR", "Villa", 2240, 4, 3, 20500000, "photo-1600607687644-c7171b42498f"),
    ("Riverstone Apartment", "Kolkata", "New Town", "Apartment", 1080, 2, 2, 7600000, "photo-1600607687920-4e2a09cf159d"),
    ("Orchid Corner", "Ahmedabad", "Satellite", "Independent House", 1720, 3, 2, 11300000, "photo-1600585154526-990dced4db0d"),
]


def get_db():
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM properties").fetchone()[0] == 0:
        for name, city, location, kind, area, beds, baths, price, photo in DEMO_PROPERTIES:
            db.execute(
                """INSERT INTO properties
                   (name, city, location, property_type, area_sqft, bedrooms, bathrooms,
                    price, image_url, description, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (name, city, location, kind, area, beds, baths, price,
                 f"https://images.unsplash.com/{photo}?auto=format&fit=crop&w=1000&q=85",
                 "A demonstration listing created for the HomeValue academic project."),
            )
    admin_username = os.environ.get("HOMEVALUE_ADMIN_USER", "admin@homevalue.local").strip()
    admin_password = os.environ.get("HOMEVALUE_ADMIN_PASSWORD", "ChangeMe123!")
    if not db.execute("SELECT id FROM admins WHERE username = ?", (admin_username,)).fetchone():
        db.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            (admin_username, generate_password_hash(admin_password)),
        )
    db.commit()
