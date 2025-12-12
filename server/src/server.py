import os
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING, errors
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI
from collections import defaultdict 

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# ---------- Flask app ----------

app = Flask(__name__)
CORS(app, supports_credentials=True)

# ---------- Mongo setup ----------

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/calendar")
mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = mongo_client.get_database()

users = db["users"]
tasks = db["tasks"]

# Indexes
try:
    users.create_index([("username", ASCENDING)], unique=True)
    tasks.create_index([("username", ASCENDING)])
    tasks.create_index([("date", ASCENDING)])
    tasks.create_index([("due_date", ASCENDING)])
except Exception:
    pass


# ---------- Helpers ----------

def parse_date_str(date_str: str | None) -> str | None:
    """Normalize a date string to YYYY-MM-DD or return None."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def task_to_json(doc: dict | None) -> dict | None:
    """Convert a Mongo document into JSON-friendly dict for the client."""
    if not doc:
        return None
    return {
        "id": str(doc.get("_id")),
        "event_name": doc.get("event_name"),
        "event_description": doc.get("event_description"),
        "date": doc.get("date"),          # calendar date (string)
        "due_date": doc.get("due_date"),  # due date (string or None)
        "priority": doc.get("priority"),
        "is_active": doc.get("is_active", True),
        "username": doc.get("username"),
        "ai_priority_score": doc.get("ai_priority_score"),
    }

def compute_ai_priority_score(event_name: str, event_description: str) -> float | None:
    """
    Semantic importance score: 0–100.
    User-assigned priority and due dates are handled separately in sorting.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[AI] No OPENAI_API_KEY set; skipping AI scoring.")
        return None

    prompt = f"""
You are ranking tasks by how important or impactful they seem,
ignoring user labels and due dates.

Task title: {event_name}
Task description: {event_description}

Return ONLY a single number from 0 to 100 (no text), where:
- 90–100 = extremely important
- 70–89  = important
- 40–69  = moderate
- 0–39   = minor
"""

    try:
        print(f"[AI] Scoring task: {event_name!r}")
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You score the semantic importance of tasks.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        text = resp.choices[0].message.content.strip()
        print("[AI] Raw model output:", text)

        score = float(text)
        score = max(0.0, min(score, 100.0))
        print(f"[AI] Parsed score: {score}")
        return score
    except Exception as e:
        print("[AI] priority scoring error:", e)
        return None
# ---------- Health ----------

@app.get("/health")
def health():
    try:
        db.command("ping")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ---------- Auth: Signup (Mongo) ----------

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
        users.insert_one(
            {
                "username": username,
                "passwordHash": generate_password_hash(password),
                "roles": ["user"],
                "createdAt": datetime.utcnow(),
            }
        )
        return jsonify({"ok": True, "user": {"username": username}}), 201
    except errors.DuplicateKeyError:
        return jsonify({"error": "username already exists"}), 409


# ---------- Auth: Login (Mongo) ----------

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

    return jsonify({"ok": True, "user": {"username": username}}), 200


# ---------- TASK ROUTES (Mongo + OpenAI) ----------

# CREATE TASK
@app.post("/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    print("[Tasks] create_task payload:", data)

    event_name = (data.get("event_name") or "").strip()
    event_description = data.get("event_description") or ""
    date_str = parse_date_str(data.get("date"))
    due_date_str = parse_date_str(data.get("due_date")) if data.get("due_date") else None
    priority = (data.get("priority") or "Medium").title()
    username = (data.get("username") or "").strip() or None

    if not event_name or not date_str:
        return jsonify({"error": "event_name and date are required"}), 400
    if priority not in ("High", "Medium", "Low"):
        return jsonify({"error": "priority must be High, Medium, or Low"}), 400

    now = datetime.utcnow()
    doc = {
        "event_name": event_name,
        "event_description": event_description,
        "date": date_str,
        "due_date": due_date_str,
        "priority": priority,
        "is_active": True,
        "createdAt": now,
        "updatedAt": now,
    }
    if username:
        doc["username"] = username

    ai_score = compute_ai_priority_score(event_name, event_description)
    print("[Tasks] AI score for new task:", ai_score)
    if ai_score is not None:
        doc["ai_priority_score"] = ai_score

    res = tasks.insert_one(doc)
    doc["_id"] = res.inserted_id
    print("[Tasks] created:", task_to_json(doc))
    return jsonify(task_to_json(doc)), 201


# LIST TASKS (per date for calendar)
@app.get("/tasks")
def list_tasks():
    date_raw = request.args.get("date")
    date_str = parse_date_str(date_raw) if date_raw else None
    raw_username = request.args.get("username", "")
    username = (raw_username or "").strip()
    include_inactive = request.args.get("include_inactive", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    query = {}
    if date_str:
        query["date"] = date_str
    if username and username.lower() not in ("undefined", "null"):
        query["username"] = username
    if not include_inactive:
        query["is_active"] = True

    docs = list(tasks.find(query).sort("date", ASCENDING))
    return jsonify([task_to_json(d) for d in docs]), 200


# UPDATE TASK
@app.put("/tasks/<task_id>")
def update_task(task_id: str):
    try:
        oid = ObjectId(task_id)
    except Exception:
        return jsonify({"error": "invalid task id"}), 400

    data = request.get_json(silent=True) or {}
    print("[Tasks] update_task payload:", task_id, data)
    update_fields: dict = {}

    if "event_name" in data:
        name = (data.get("event_name") or "").strip()
        if not name:
            return jsonify({"error": "event_name cannot be empty"}), 400
        update_fields["event_name"] = name

    if "event_description" in data:
        update_fields["event_description"] = data.get("event_description") or ""

    if "date" in data:
        if data["date"]:
            date_str = parse_date_str(data["date"])
            if not date_str:
                return jsonify({"error": "Invalid date format, expected YYYY-MM-DD"}), 400
            update_fields["date"] = date_str

    if "due_date" in data:
        if data["due_date"]:
            due_date_str = parse_date_str(data["due_date"])
            if not due_date_str:
                return jsonify(
                    {"error": "Invalid due_date format, expected YYYY-MM-DD"}
                ), 400
            update_fields["due_date"] = due_date_str
        else:
            update_fields["due_date"] = None

    if "priority" in data:
        prio = (data["priority"] or "").title()
        if prio not in ("High", "Medium", "Low"):
            return jsonify({"error": "priority must be High, Medium, or Low"}), 400
        update_fields["priority"] = prio

    if "is_active" in data:
        update_fields["is_active"] = bool(data["is_active"])

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    existing = tasks.find_one({"_id": oid})
    if not existing:
        return jsonify({"error": "Task not found"}), 404

    new_event_name = update_fields.get("event_name", existing.get("event_name", ""))
    new_description = update_fields.get(
        "event_description", existing.get("event_description", "")
    )

    ai_score = compute_ai_priority_score(new_event_name, new_description)
    if ai_score is not None:
        update_fields["ai_priority_score"] = ai_score

    update_fields["updatedAt"] = datetime.utcnow()

    result = tasks.find_one_and_update(
        {"_id": oid},
        {"$set": update_fields},
        return_document=True,
    )

    return jsonify(task_to_json(result)), 200


# DELETE /tasks/<id> (soft delete)
@app.delete("/tasks/<task_id>")
def delete_task(task_id: str):
    try:
        oid = ObjectId(task_id)
    except Exception:
        return jsonify({"error": "invalid task id"}), 400

    result = tasks.find_one_and_update(
        {"_id": oid},
        {"$set": {"is_active": False, "updatedAt": datetime.utcnow()}},
        return_document=True,
    )

    if not result:
        return jsonify({"error": "Task not found"}), 404

    return jsonify({"ok": True}), 200


# PRIORITY VIEW
PRIORITY_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}


@app.get("/tasks/priorities")
def list_tasks_prioritized():
    username = request.args.get("username", "").strip() or None
    include_inactive = request.args.get("include_inactive", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    query: dict = {}
    if username:
        query["username"] = username
    if not include_inactive:
        query["is_active"] = True

    docs = list(tasks.find(query))

    def sort_key(doc):
        # 1) User priority (High > Medium > Low)
        prio = (doc.get("priority") or "Medium").title()
        user_weight = PRIORITY_WEIGHT.get(prio, 2)

        # 2) Due date (earlier first; None treated as far future)
        due_date = doc.get("due_date") or "9999-12-31"

        # 3) AI semantic score (higher first)
        ai_score = float(doc.get("ai_priority_score") or 0.0)

        # 4) tie-breaker: id
        return (-user_weight, due_date, -ai_score, str(doc.get("_id")))

    docs.sort(key=sort_key)
    return jsonify([task_to_json(d) for d in docs]), 200

# ---------- Analytics Summary ----------

@app.get("/analytics/summary")
def analytics_summary():
    """
    Return summary stats and per-day counts for the current user.
    Query param: ?username=...
    """
    username = request.args.get("username", "").strip() or None

    query = {}
    if username:
        query["username"] = username

    docs = list(tasks.find(query))

    total_tasks = len(docs)
    completed_tasks = sum(1 for d in docs if not d.get("is_active", True))
    active_tasks = total_tasks - completed_tasks
    high_priority_active = sum(
        1
        for d in docs
        if d.get("is_active", True) and (d.get("priority") or "").title() == "High"
    )

    # Per-date counts for graph
    total_by_date = defaultdict(int)
    completed_by_date = defaultdict(int)

    for d in docs:
        date_str = d.get("date")
        if not date_str:
            continue
        total_by_date[date_str] += 1
        if not d.get("is_active", True):
            completed_by_date[date_str] += 1

    # Sort by date (string YYYY-MM-DD) and keep the last 30 days
    sorted_dates = sorted(total_by_date.keys())
    if len(sorted_dates) > 30:
        sorted_dates = sorted_dates[-30:]

    by_date = [
        {
            "date": dt,
            "total": total_by_date.get(dt, 0),
            "completed": completed_by_date.get(dt, 0),
        }
        for dt in sorted_dates
    ]

    return jsonify(
        {
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "high_priority_active": high_priority_active,
            "by_date": by_date,
        }
    ), 200



# ---------- Main ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5003")), debug=True)

