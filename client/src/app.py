import requests
from flask import Flask, render_template_string, request, jsonify
app = Flask(__name__) 

@app.get("/")
def home():
    return "Hello World"

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5000)
