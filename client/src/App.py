import requests
from flask import Flask, render_template_string, request, jsonify
app = Flask(__name__) 

@app.get("/")
def home():
    return render_template_string("<h1>Hello World<h1>")
