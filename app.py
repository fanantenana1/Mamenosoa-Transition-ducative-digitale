from flask import (
    Flask, request, jsonify, session,
    render_template, redirect, url_for, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import os, sqlite3, json


app = Flask(__name__)

@app.route("/")
def login_page():
    return render_template("login.html")
# Route principale pour le dashboard admin
@app.route("/dashboard/admin")
def dashboard_admin():
    return render_template("dashboard_admin.html")

if __name__ == "__main__":
    app.run(debug=True)

