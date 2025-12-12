from flask import Flask, request, render_template, redirect, url_for, session
import os
import requests

app = Flask(__name__, template_folder="templates", static_folder="static")

# Python (inside Docker) -> backend
INTERNAL_BACKEND_URL = os.getenv("INTERNAL_BACKEND_URL", "http://server:5003")

# Browser (host) -> backend
PUBLIC_BACKEND_URL = os.getenv("PUBLIC_BACKEND_URL", "http://localhost:5003")

app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

# ---------- Helpers ----------

def current_username():
    """Return the logged-in username from the session, or None."""
    return session.get("username")


def require_login():
    """
    Redirect to /login if user is not logged in.
    Usage:
        maybe_redirect = require_login()
        if maybe_redirect: return maybe_redirect
    """
    if not current_username():
        return redirect(url_for("login"))
    return None


# ---------- Root ----------

@app.get("/")
def home():
    # If already logged in, go to dashboard; otherwise to login
    if current_username():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# ---------- Login ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            r = requests.post(
                f"{INTERNAL_BACKEND_URL}/auth/login",   # <--- internal
                json={"username": username, "password": password},
                timeout=5,
            )
            if r.status_code == 200:
                session["username"] = username
                return redirect(url_for("dashboard"))

            err = r.json().get("error", "Login failed")
            return render_template("login.html", error=err)
        except Exception as e:
            return render_template("login.html", error=str(e))

    if current_username():
        return redirect(url_for("dashboard"))
    return render_template("login.html", error=None)



# ---------- Logout ----------

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------- Signup ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if password != confirm:
            return render_template("signup.html", error="Passwords do not match.")

        try:
            r = requests.post(
                f"{INTERNAL_BACKEND_URL}/auth/signup",  # <--- internal
                json={"username": username, "password": password},
                timeout=5,
            )
            if r.status_code == 201:
                return redirect(url_for("login"))
            err = r.json().get("error", "Signup failed")
            return render_template("signup.html", error=err)
        except Exception as e:
            return render_template("signup.html", error=str(e))

    return render_template("signup.html", error=None)


@app.get("/register")
def register():
    # Backwards compat: /register → /signup
    return redirect(url_for("signup"))


# ---------- Pages (protected) ----------

@app.get("/dashboard")
def dashboard():
    maybe_redirect = require_login()
    if maybe_redirect:
        return maybe_redirect

    return render_template(
        "calendar.html",
        backend_url=PUBLIC_BACKEND_URL,
        username=current_username(),
    )


@app.get("/analytics")
def analytics():
    maybe_redirect = require_login()
    if maybe_redirect:
        return maybe_redirect

    return render_template(
        "analytics.html",
        backend_url=PUBLIC_BACKEND_URL,
        username=current_username(),
    )


@app.get("/priority")
def priority():
    maybe_redirect = require_login()
    if maybe_redirect:
        return maybe_redirect

    return render_template(
        "priority.html",
        backend_url=PUBLIC_BACKEND_URL,
        username=current_username(),
    )


@app.get("/task/<task_id>")
def task_detail(task_id):
    maybe_redirect = require_login()
    if maybe_redirect:
        return maybe_redirect

    return render_template(
        "task_detail.html",
        backend_url=BACKEND_URL,
        username=current_username(),
        task_id=task_id,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)

