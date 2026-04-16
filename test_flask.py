#!/usr/bin/env python3
from flask import Flask, jsonify
app = Flask(__name__)

@app.route("/")
def hello():
    return jsonify({"message": "Hello from ArduinoBridge!"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765)
