from flask import Flask, request, jsonify, send_file, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import secrets
import re
import os
from datetime import datetime, timedelta
app = Flask(__name__)

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", BASE)

os.makedirs(DATA_DIR, exist_ok=True)

DB = os.path.join(DATA_DIR, "lusix.db")
SECRET_FILE = os.path.join(DATA_DIR, "secret.key")
if not os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, "w") as f:
        f.write(secrets.token_hex(32))

app.secret_key = open(SECRET_FILE).read()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_tokens():
    db = connect()
    db.execute("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    db.commit()
    db.close()

def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None

    token = auth[7:].strip()
    if not token:
        return None

    db = connect()
    user = db.execute("""
        SELECT users.id, users.name, users.email, users.role,
               users.created_at
        FROM api_tokens
        JOIN users ON users.id=api_tokens.user_id
        WHERE api_tokens.token=?
    """, (token,)).fetchone()
    db.close()
    return user

def require_user():
    user = current_user()
    if not user:
        return None
    return user

def make_token(user_id):
    token = secrets.token_urlsafe(48)
    db = connect()
    db.execute(
        "INSERT INTO api_tokens(token,user_id) VALUES(?,?)",
        (token, user_id)
    )
    db.commit()
    db.close()
    return token

def user_json(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "created_at": user["created_at"]
    }
@app.route("/")
def home():
    return send_file(os.path.join(BASE, "index.html"))

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    upload_folder = os.path.join(DATA_DIR, "uploads")
    return send_from_directory(upload_folder, filename)


@app.route("/api/register", methods=["POST"])
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    phone = str(data.get("phone", "")).strip()

    if len(name) < 2:
        return jsonify({"detail": "Ism noto‘g‘ri"}), 400
    if not re.fullmatch(r"[^@\s]+@gmail\.com", email):
        return jsonify({"detail": "To‘g‘ri Gmail kiriting"}), 400
    if len(password) < 8:
        return jsonify({"detail": "Parol kamida 8 belgidan iborat bo‘lsin"}), 400

    db = connect()
    try:
        cur = db.execute("""
            INSERT INTO users(name,email,password)
            VALUES(?,?,?)
        """, (name, email, generate_password_hash(password)))
        db.commit()
        uid = cur.lastrowid
        token = make_token(uid)
        user = db.execute(
            "SELECT id,name,email,role,created_at FROM users WHERE id=?",
            (uid,)
        ).fetchone()
        return jsonify({
            "success": True,
            "user": user_json(user),
            "access_token": token
        }), 201
    except sqlite3.IntegrityError:
        return jsonify({"detail": "Bu Gmail avval ro‘yxatdan o‘tgan"}), 409
    finally:
        db.close()

@app.route("/api/login", methods=["POST"])
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    db = connect()
    user = db.execute(
        "SELECT * FROM users WHERE email=?", (email,)
    ).fetchone()
    db.close()

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"detail": "Gmail yoki parol noto‘g‘ri"}), 401

    token = make_token(user["id"])
    return jsonify({
        "success": True,
        "user": user_json(user),
        "access_token": token
    })

@app.route("/api/logout", methods=["POST"])
def logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        db = connect()
        db.execute(
            "DELETE FROM api_tokens WHERE token=?", (auth[7:].strip(),)
        )
        db.commit()
        db.close()
    return jsonify({"success": True})

@app.route("/api/me")
@app.route("/api/me/profile")
def me():
    user = require_user()
    if not user:
        return jsonify({"detail": "Tizimga kirmagansiz"}), 401

    db = connect()
    uid = user["id"]

    favorites = [
        r["movie_id"] for r in db.execute(
            "SELECT movie_id FROM favorites WHERE user_id=?", (uid,)
        )
    ]
    watched = [
        r["movie_id"] for r in db.execute(
            "SELECT movie_id FROM watch_history WHERE user_id=?", (uid,)
        )
    ]

    sub = db.execute("""
        SELECT plan,expires_at FROM subscriptions
        WHERE user_id=? AND status='active'
        ORDER BY id DESC LIMIT 1
    """, (uid,)).fetchone()

    payments = db.execute("""
        SELECT id,amount,method,status,created_at
        FROM payments WHERE user_id=? ORDER BY id DESC
    """, (uid,)).fetchall()

    db.close()

    return jsonify({
        "user": user_json(user),
        "favorites": favorites,
        "watched": watched,
        "subscription": (
            {"plan": sub["plan"], "until": sub["expires_at"]}
            if sub else None
        ),
        "payments": [
            {
                "id": p["id"],
                "amount": p["amount"],
                "method": p["method"],
                "date": p["created_at"],
                "status": p["status"]
            } for p in payments
        ]
    })

@app.route("/api/me/profile", methods=["PATCH"])
def update_profile():
    user = require_user()
    if not user:
        return jsonify({"detail": "Tizimga kirmagansiz"}), 401

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", user["name"])).strip()

    if len(name) < 2:
        return jsonify({"detail": "Ism noto‘g‘ri"}), 400

    db = connect()
    db.execute(
        "UPDATE users SET name=? WHERE id=?",
        (name, user["id"])
    )
    db.commit()
    updated = db.execute(
        "SELECT id,name,email,role,created_at FROM users WHERE id=?",
        (user["id"],)
    ).fetchone()
    db.close()

    return jsonify({"success": True, "user": user_json(updated)})

@app.route("/api/me/activity", methods=["PUT"])
def activity():
    user = require_user()
    if not user:
        return jsonify({"detail": "Tizimga kirmagansiz"}), 401

    data = request.get_json(silent=True) or {}
    uid = user["id"]
    db = connect()

    for table, field in [
        ("favorites", "favorites"),
        ("watch_history", "watched")
    ]:
        if field in data and isinstance(data[field], list):
            db.execute(
                "DELETE FROM " + table + " WHERE user_id=?", (uid,)
            )
            for mid in data[field]:
                try:
                    db.execute(
                        "INSERT OR IGNORE INTO " + table +
                        "(user_id,movie_id) VALUES(?,?)",
                        (uid, int(mid))
                    )
                except (ValueError, TypeError):
                    pass

    db.commit()
    db.close()
    return jsonify({"success": True})

def movie_list():
    db = connect()
    rows = db.execute("""
        SELECT id,name,type,year,description,poster,video,is_vip
        FROM movies ORDER BY id DESC
    """).fetchall()

    result = []
    for m in rows:
        eps = db.execute("""
            SELECT title,video_url,episode_number
            FROM episodes WHERE movie_id=?
            ORDER BY episode_number
        """, (m["id"],)).fetchall()

        result.append({
            "id": m["id"],
            "name": m["name"],
            "type": m["type"],
            "year": m["year"],
            "desc": m["description"],
            "poster": m["poster"],
            "video": m["video"],
            "vip": bool(m["is_vip"]),
            "eps": [
                {"title": e["title"], "url": e["video_url"]}
                for e in eps
            ]
        })

    db.close()
    return result

@app.route("/api/movies")
def get_movies():
    movies = movie_list()
    return jsonify({
        "success": True,
        "count": len(movies),
        "movies": movies
    })

@app.route("/api/public/state")
def public_state():
    return jsonify({
        "success": True,
        "movies": movie_list()
    })

@app.route("/api/payments", methods=["POST"])
def create_payment():
    user = require_user()
    if not user:
        return jsonify({"detail": "Tizimga kirmagansiz"}), 401

    data = request.get_json(silent=True) or {}
    plan = str(data.get("plan", "")).strip()
    method = str(data.get("method", "")).strip()
    try:
        amount = int(data.get("amount", 0))
    except (ValueError, TypeError):
        amount = 0

    allowed = {
        "7 kun": 15000,
        "30 kun": 35000,
        "90 kun": 90000,
        "365 kun": 250000
    }

    if plan not in allowed or amount != allowed[plan]:
        return jsonify({"detail": "Tarif yoki summa noto‘g‘ri"}), 400

    if method not in [
        "Payme", "Click", "Uzum Bank", "Paynet", "UZCARD", "HUMO"
    ]:
        return jsonify({"detail": "To‘lov usuli noto‘g‘ri"}), 400

    db = connect()
    cur = db.execute("""
        INSERT INTO payments(user_id,amount,method,status)
        VALUES(?,?,?,'pending')
    """, (user["id"], amount, method))
    db.commit()
    payment_id = cur.lastrowid
    db.close()

    return jsonify({
        "success": True,
        "id": payment_id,
        "status": "pending",
        "message": "To‘lov so‘rovi qabul qilindi. To‘lov hali tasdiqlanmagan."
    }), 201

if __name__ == "__main__":
    init_tokens()
    app.run(host="0.0.0.0", port=5000, debug=False)


