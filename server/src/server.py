import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING, errors
from werkzeug.security import generate_password_hash, check_password_hash
import openai

from bson import ObjectId

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Mongo connection (from docker-compose)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/calendar")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client.get_database()
users = db["users"]
tasks = db["tasks"]
openai.api_key = os.getenv("OPENAI_API_KEY")

def compute_ai_priority_score(event_name: str, event_description: str) -> float | None:
    """
    Use OpenAI to produce a semantic importance score (0–100).
    Higher = more important/critical based on the content alone.
    User-assigned priority and due dates are handled separately in sorting.
    """
    if not openai.api_key:
        return None

    prompt = f"""
You are ranking tasks by how important or impactful they seem,
ignoring user labels and due dates (these are handled elsewhere).

Task title: {event_name}
Task description: {event_description}

Consider:
- How serious and consequential the task sounds
- Whether it seems related to exams, grades, jobs, health, etc.
- Whether it seems like deep work vs. trivial chores

Return ONLY a single number from 0 to 100 (no text), where:
- 90–100 = extremely important
- 70–89  = important
- 40–69  = moderate
- 0–39   = minor
"""

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You score the semantic importance of tasks."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        text = resp.choices[0].message["content"].strip()
        score = float(text)
        return max(0.0, min(score, 100.0))
    except Exception as e:
        print("AI priority scoring error:", e)
        return None

# Indexes
try:
    users.create_index([("username", ASCENDING)], unique=True)
except Exception:
    pass

try:
    tasks.create_index([("date", ASCENDING)])
    tasks.create_index([("is_active", ASCENDING)])
    tasks.create_index([("username", ASCENDING)])
except Exception:
    pass


def task_to_json(doc):
    if not doc:
        return None
    return {
        "id": str(doc.get("_id")),
        "event_name": doc.get("event_name"),
        "event_description": doc.get("event_description"),
        "date": doc.get("date"),              # event date (calendar cell)
        "due_date": doc.get("due_date"),      # NEW: actual due date
        "priority": doc.get("priority"),
        "is_active": doc.get("is_active", True),
        "username": doc.get("username"),
        "ai_priority_score": doc.get("ai_priority_score"),
    }



# ---------- Health ----------

@app.get("/health")
def health():
    try:
        db.command("ping")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ---------- Auth: Signup ----------

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


# ---------- Auth: Login ----------

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


# =====================================================
# ================  TASKS API  ========================
# =====================================================

def parse_date_str(date_str):
    """Validate/normalize 'YYYY-MM-DD' date strings."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


@app.post("/tasks")
def create_task():
    """
    JSON body:
    {
      "event_name": "My event",
      "event_description": "Optional details",
      "date": "YYYY-MM-DD",
      "priority": "High" | "Medium" | "Low",
      "username": "owner-username"
    }
    """
    data = request.get_json(silent=True) or {}

    event_name = (data.get("event_name") or "").strip()
    event_description = data.get("event_description") or ""
    date_str = parse_date_str(data.get("date"))
    due_date_str = parse_date_str(data.get("due_date")) if data.get("due_date") else None  # NEW
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
        "priority": priority,
        "due_date": due_date_str,
        "is_active": True,
        "createdAt": now,
        "updatedAt": now,
    }
    if username:
        doc["username"] = username

    ai_score = compute_ai_priority_score(event_name, event_description)
    if ai_score is not None:
        doc["ai_priority_score"] = ai_score

    result = tasks.insert_one(doc)
    doc["_id"] = result.inserted_id
    return jsonify(task_to_json(doc)), 201
    

@app.get("/tasks")
def list_tasks():
    """
    GET /tasks?date=YYYY-MM-DD&username=<user>&include_inactive=true|false
    """
    date_raw = request.args.get("date")
    date_str = parse_date_str(date_raw) if date_raw else None
    username = request.args.get("username", "").strip() or None
    include_inactive = request.args.get("include_inactive", "false").lower() in (
        "true", "1", "yes"
    )

    query = {}
    if date_str:
        query["date"] = date_str
    if username:
        query["username"] = username
    if not include_inactive:
        query["is_active"] = True

    docs = list(tasks.find(query).sort("date", ASCENDING))
    return jsonify([task_to_json(d) for d in docs]), 200


@app.get("/tasks/<task_id>")
def get_task(task_id):
    try:
        oid = ObjectId(task_id)
    except Exception:
        return jsonify({"error": "invalid task id"}), 400

    doc = tasks.find_one({"_id": oid})
    if not doc:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(task_to_json(doc)), 200


@app.put("/tasks/<task_id>")
def update_task(task_id):
    try:
        oid = ObjectId(task_id)
    except Exception:
        return jsonify({"error": "invalid task id"}), 400

    data = request.get_json(silent=True) or {}
    update_fields = {}

    if "event_name" in data:
        name = (data.get("event_name") or "").strip()
        if not name:
            return jsonify({"error": "event_name cannot be empty"}), 400
        update_fields["event_name"] = name

    if "event_description" in data:
        update_fields["event_description"] = data.get("event_description") or ""
    if "due_date" in data:
        if data["due_date"]:
            due_date_str = parse_date_str(data["due_date"])
            if not due_date_str:
                return jsonify({"error": "Invalid due_date format, expected YYYY-MM-DD"}), 400
            update_fields["due_date"] = due_date_str
        else:
            update_fields["due_date"] = None


    if "date" in data:
        if data["date"]:
            date_str = parse_date_str(data["date"])
            if not date_str:
                return jsonify({"error": "Invalid date format, expected YYYY-MM-DD"}), 400
            update_fields["date"] = date_str
        else:
            return jsonify({"error": "date cannot be empty"}), 400

    if "priority" in data:
        if data["priority"]:
            prio = (data["priority"] or "").title()
            if prio not in ("High", "Medium", "Low"):
                return jsonify({"error": "priority must be High, Medium, or Low"}), 400
            update_fields["priority"] = prio

    if "is_active" in data:
        update_fields["is_active"] = bool(data["is_active"])

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    update_fields["updatedAt"] = datetime.utcnow()

    existing = tasks.find_one({"_id": oid})
    if not existing:
        return jsonify({"error": "Task not found"}), 404

    new_event_name = update_fields.get("event_name", existing.get("event_name", ""))
    new_description = update_fields.get("event_description", existing.get("event_description", ""))

    ai_score = compute_ai_priority_score(new_event_name, new_description)
    if ai_score is not None:
        update_fields["ai_priority_score"] = ai_score

    result = tasks.find_one_and_update(
        {"_id": oid},
        {"$set": update_fields},
        return_document=True,
    )

    

    if not result:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(task_to_json(result)), 200


@app.delete("/tasks/<task_id>")
def delete_task(task_id):
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

    return jsonify({"status": "deleted", "id": task_id}), 200

PRIORITY_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}

@app.get("/tasks/priorities")
def list_tasks_prioritized():
    username = request.args.get("username", "").strip() or None
    include_inactive = request.args.get("include_inactive", "false").lower() in (
        "true", "1", "yes"
    )

    query = {}
    if username:
        query["username"] = username
    if not include_inactive:
        query["is_active"] = True

    docs = list(tasks.find(query))

    def sort_key(doc):
        # 1) USER PRIORITY
        prio = (doc.get("priority") or "Medium").title()
        user_weight = PRIORITY_WEIGHT.get(prio, 2)  # High=3, Medium=2, Low=1

        # 2) DUE DATE (earlier first). If missing, put far in future.
        due_date = doc.get("due_date") or "9999-12-31"

        # 3) AI SEMANTIC SCORE (higher first)
        ai_score = float(doc.get("ai_priority_score") or 0.0)

        # Higher user priority, earlier due date, higher AI score
        return (-user_weight, due_date, -ai_score, str(doc.get("_id")))

    docs.sort(key=sort_key)

    return jsonify([task_to_json(d) for d in docs]), 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5003")))

