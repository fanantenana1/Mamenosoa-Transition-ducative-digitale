"""Digiscool - Application Flask structurée.

Le serveur principal reste simple et clair, avec une configuration propre,
une initialisation SQLite et des routes organisées pour admin / utilisateur.
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'digiscool-secret-2025')
app.config['MAX_CONTENT_LENGTH'] = 150 * 1024 * 1024

DB_PATH = os.path.join(BASE_DIR, 'instance', 'digiscool.db')
UPLOAD_VIDEOS = os.path.join(BASE_DIR, 'uploads', 'videos')
UPLOAD_DOCS = os.path.join(BASE_DIR, 'uploads', 'documents')

ALLOWED_VIDEO = {'mp4', 'webm', 'ogg', 'mov', 'avi'}
ALLOWED_DOC = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip', 'png', 'jpg', 'jpeg'}

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(UPLOAD_VIDEOS, exist_ok=True)
os.makedirs(UPLOAD_DOCS, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS cours (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titre TEXT NOT NULL,
                description TEXT DEFAULT '',
                video_filename TEXT DEFAULT '',
                document_filename TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        if not db.execute('SELECT 1 FROM users WHERE email=?', ('admin@digiscool.mg',)).fetchone():
            db.execute(
                'INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',
                ('Admin', 'admin@digiscool.mg', generate_password_hash('admin123'), 'admin')
            )
        db.commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return view(*args, **kwargs)
    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('dashboard'))
        return view(*args, **kwargs)
    return wrapped_view


def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set


def get_user_by_email(email):
    with get_db() as db:
        return db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/education')
def education_redirect():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index', login='1'))
    return redirect(url_for('dashboard_admin') if session.get('role') == 'admin' else url_for('dashboard_user'))


@app.route('/dashboard/admin')
@login_required
@admin_required
def dashboard_admin():
    with get_db() as db:
        users = db.execute("SELECT * FROM users WHERE role!='admin' ORDER BY created_at DESC").fetchall()
        cours = db.execute('SELECT * FROM cours ORDER BY created_at DESC').fetchall()
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE is_read=0').fetchone()[0]
    return render_template('admin/dashboard.html', admin_name=session.get('name'), users=users, cours=cours, notif_count=notif_count)


@app.route('/dashboard/user')
@login_required
def dashboard_user():
    with get_db() as db:
        cours = db.execute('SELECT * FROM cours ORDER BY created_at DESC').fetchall()
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)).fetchone()[0]
    return render_template('user/dashboard.html', user_name=session.get('name'), cours=cours, notif_count=notif_count)


@app.route('/admin/education')
@login_required
def admin_education():
    with get_db() as db:
        cours = db.execute('SELECT * FROM cours ORDER BY created_at DESC').fetchall()
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE is_read=0').fetchone()[0]
    return render_template('admin/education.html', cours=cours, notif_count=notif_count)


@app.route('/user/education')
@login_required
def user_education():
    with get_db() as db:
        cours = db.execute('SELECT * FROM cours ORDER BY created_at DESC').fetchall()
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)).fetchone()[0]
    return render_template('user/dashboard.html', cours=cours, user_name=session.get('name'), notif_count=notif_count)


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not email or not password:
        return jsonify({'error': 'Email et mot de passe requis.'}), 400
    user = get_user_by_email(email)
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Identifiants incorrects.'}), 401
    session.clear()
    session['user_id'] = user['id']
    session['name'] = user['name']
    session['role'] = user['role']
    return jsonify({'name': user['name'], 'role': user['role']})


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not name or not email or not password:
        return jsonify({'error': 'Tous les champs sont requis.'}), 400
    if get_user_by_email(email):
        return jsonify({'error': 'Email déjà utilisé.'}), 409
    with get_db() as db:
        db.execute(
            'INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',
            (name, email, generate_password_hash(password))
        )
        db.commit()
    return jsonify({'ok': True, 'message': 'Compte créé, connectez-vous.'})


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/files/videos/<path:filename>')
@login_required
def file_video(filename):
    return send_from_directory(UPLOAD_VIDEOS, filename)


@app.route('/files/documents/<path:filename>')
@login_required
def file_document(filename):
    return send_from_directory(UPLOAD_DOCS, filename)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
