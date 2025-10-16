
from flask import Flask, request, render_template, redirect, url_for
import os, requests

# If your templates live in client/src/template/, point Flask at it:
app = Flask(__name__, template_folder="templates")

BACKEND_URL = os.getenv("BACKEND_URL", "http://server:5003")

@app.get("/")
def home():
    return "Hello World"

# ---------- Login ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            r = requests.post(
                f"{BACKEND_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=5,
            )
            if r.status_code == 200:
                return redirect(url_for("dashboard"))
            # show backend error if provided
            err = r.json().get("error", "Login failed")
            return render_template("login.html", error=err)
        except Exception as e:
            return render_template("login.html", error=str(e))
    # GET
    return render_template("login.html", error=None)

# ---------- Signup ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")
        if password != confirm:
            return render_template("signup.html", error="Passwords do not match.")
        try:
            r = requests.post(
                f"{BACKEND_URL}/auth/signup",
                json={"username": username, "password": password},
                timeout=5,
            )
            if r.status_code == 201:
                # after signup, go log in
                return redirect(url_for("login"))
            err = r.json().get("error", "Signup failed")
            return render_template("signup.html", error=err)
        except Exception as e:
            return render_template("signup.html", error=str(e))
    # GET
    return render_template("signup.html", error=None)

@app.get("/register")
def register():
    # keep this route for backwards-compat; forward to signup UI
    return redirect(url_for("signup"))

@app.get("/dashboard")
def dashboard():
    return "Welcome to your AI Calendar!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
