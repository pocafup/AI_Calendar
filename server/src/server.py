
import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING, errors
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Compose gives you the hostname 'mongo' on the network
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/calendar")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client.get_database()       # uses DB from URI path (myapp)
users = db["users"]

# Ensure unique index on username once
try:
    users.create_index([("username", ASCENDING)], unique=True)
except Exception:
    pass

@app.get("/health")
def health():
    try:
        db.command("ping")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# ---------- Signup ----------
@app.post("/auth/signup")
def auth_signup():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if len(username) < 3 or len(password) < 6:
        return jsonify({"error": "username >=3 chars, password >=6 chars"}), 400

    try:
        users.insert_one({
            "username": username,
            "passwordHash": generate_password_hash(password),
            "roles": ["user"],
            "createdAt": datetime.utcnow(),
        })
        return jsonify({"ok": True, "user": {"username": username}}), 201
    except errors.DuplicateKeyError:
        return jsonify({"error": "username already exists"}), 409

# ---------- Login ----------
@app.post("/auth/login")
def auth_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    u = users.find_one({"username": username})
    if not u or not u.get("passwordHash"):
        return jsonify({"error": "invalid credentials"}), 401

    if not check_password_hash(u["passwordHash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    # Return only safe fields
    return jsonify({"ok": True, "user": {"username": username}}), 200

if __name__ == "__main__":
    # server listens on 5003 in the container
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5003")))
