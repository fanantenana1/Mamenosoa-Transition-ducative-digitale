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
import time

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'digiscool-secret-2025')
app.config['MAX_CONTENT_LENGTH'] = 150 * 1024 * 1024

DB_PATH = os.path.join(BASE_DIR, 'instance', 'digiscool.db')
UPLOAD_VIDEOS = os.path.join(BASE_DIR, 'uploads', 'videos')
UPLOAD_DOCS = os.path.join(BASE_DIR, 'uploads', 'documents')
UPLOAD_COURS = os.path.join(BASE_DIR, 'uploads', 'cours')
UPLOAD_EXOS = os.path.join(BASE_DIR, 'uploads', 'exercices')

ALLOWED_VIDEO = {'mp4', 'webm', 'ogg', 'mov', 'avi'}
ALLOWED_DOC = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip', 'png', 'jpg', 'jpeg'}

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(UPLOAD_VIDEOS, exist_ok=True)
os.makedirs(UPLOAD_DOCS, exist_ok=True)
os.makedirs(UPLOAD_COURS, exist_ok=True)
os.makedirs(UPLOAD_EXOS, exist_ok=True)


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
                matiere TEXT DEFAULT '',
                description TEXT DEFAULT '',
                video_filename TEXT DEFAULT '',
                video_url TEXT DEFAULT '',
                cours_type TEXT DEFAULT 'fichier',
                cours_fichier TEXT DEFAULT '',
                cours_texte TEXT DEFAULT '',
                cours_qcm TEXT DEFAULT '[]',
                exercice_type TEXT DEFAULT 'fichier',
                exercice_fichier TEXT DEFAULT '',
                exercice_texte TEXT DEFAULT '',
                exercice_qcm TEXT DEFAULT '[]',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        columns = [row[1] for row in db.execute("PRAGMA table_info(cours)").fetchall()]
        for col, col_def in [
            ('matiere', "TEXT DEFAULT ''"),
            ('video_url', "TEXT DEFAULT ''"),
            ('cours_type', "TEXT DEFAULT 'fichier'"),
            ('cours_fichier', "TEXT DEFAULT ''"),
            ('cours_texte', "TEXT DEFAULT ''"),
            ('cours_qcm', "TEXT DEFAULT '[]'"),
            ('exercice_type', "TEXT DEFAULT 'fichier'"),
            ('exercice_fichier', "TEXT DEFAULT ''"),
            ('exercice_texte', "TEXT DEFAULT ''"),
            ('exercice_qcm', "TEXT DEFAULT '[]'"),
        ]:
            if col not in columns:
                db.execute(f'ALTER TABLE cours ADD COLUMN {col} {col_def}')
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


def serialize_cours(row):
    return {
        'id': row['id'],
        'titre': row['titre'],
        'matiere': row['matiere'],
        'description': row['description'],
        'video_filename': row['video_filename'],
        'video_url': row['video_url'],
        'cours_type': row['cours_type'],
        'cours_fichier': row['cours_fichier'],
        'cours_texte': row['cours_texte'],
        'cours_qcm': row['cours_qcm'],
        'exercice_type': row['exercice_type'],
        'exercice_fichier': row['exercice_fichier'],
        'exercice_texte': row['exercice_texte'],
        'exercice_qcm': row['exercice_qcm'],
        'created_at': row['created_at'],
    }


def save_uploaded_file(uploaded_file, upload_dir, allowed_set=None):
    if not uploaded_file or not uploaded_file.filename:
        return ''
    filename = secure_filename(uploaded_file.filename)
    if not filename:
        return ''
    if allowed_set and not allowed_file(filename, allowed_set):
        raise ValueError('Type de fichier non autorisé.')
    name, ext = os.path.splitext(filename)
    filename = f"{name}_{int(time.time())}{ext}"
    destination = os.path.join(upload_dir, filename)
    uploaded_file.save(destination)
    return filename


def remove_file(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


@app.route('/api/cours', methods=['GET'])
@login_required
def api_get_cours():
    q = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'id')
    if sort not in ('id', 'titre', 'matiere', 'created_at'):
        sort = 'id'
    query = 'SELECT * FROM cours'
    params = []
    if q:
        query += ' WHERE titre LIKE ? OR matiere LIKE ? OR description LIKE ?'
        pattern = f'%{q}%'
        params = [pattern, pattern, pattern]
    order = 'DESC' if sort in ('id', 'created_at') else 'ASC'
    query += f' ORDER BY {sort} {order}'
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    return jsonify([serialize_cours(row) for row in rows])


@app.route('/api/cours', methods=['POST'])
@login_required
def api_create_cours():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accès refusé.'}), 403

    titre = request.form.get('titre', '').strip()
    matiere = request.form.get('matiere', '').strip()
    description = request.form.get('description', '').strip()
    video_url = request.form.get('video_url', '').strip()
    cours_type = request.form.get('cours_type', 'fichier')
    cours_texte = request.form.get('cours_texte', '').strip()
    cours_qcm = request.form.get('cours_qcm', '[]') if cours_type == 'qcm' else '[]'
    exercice_type = request.form.get('exercice_type', 'fichier')
    exercice_texte = request.form.get('exercice_texte', '').strip()
    exercice_qcm = request.form.get('exercice_qcm', '[]') if exercice_type == 'qcm' else '[]'

    if not titre:
        return jsonify({'error': 'Le titre est requis.'}), 400

    try:
        video_filename = ''
        if 'video_file' in request.files and request.files['video_file'].filename:
            video_filename = save_uploaded_file(request.files['video_file'], UPLOAD_VIDEOS, ALLOWED_VIDEO)

        cours_fichier = ''
        if cours_type == 'fichier' and 'cours_fichier' in request.files and request.files['cours_fichier'].filename:
            cours_fichier = save_uploaded_file(request.files['cours_fichier'], UPLOAD_COURS, ALLOWED_DOC)

        exercice_fichier = ''
        if exercice_type == 'fichier' and 'exercice_fichier' in request.files and request.files['exercice_fichier'].filename:
            exercice_fichier = save_uploaded_file(request.files['exercice_fichier'], UPLOAD_EXOS, ALLOWED_DOC)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    with get_db() as db:
        cur = db.execute(
            '''INSERT INTO cours (titre, matiere, description, video_filename, video_url,
                cours_type, cours_fichier, cours_texte, cours_qcm,
                exercice_type, exercice_fichier, exercice_texte, exercice_qcm)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (titre, matiere, description, video_filename, video_url,
             cours_type, cours_fichier, cours_texte, cours_qcm,
             exercice_type, exercice_fichier, exercice_texte, exercice_qcm)
        )
        db.commit()
        cours = db.execute('SELECT * FROM cours WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(serialize_cours(cours))


@app.route('/api/cours/<int:cours_id>', methods=['PUT'])
@login_required
def api_update_cours(cours_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accès refusé.'}), 403

    with get_db() as db:
        existing = db.execute('SELECT * FROM cours WHERE id = ?', (cours_id,)).fetchone()
        if not existing:
            return jsonify({'error': 'Cours introuvable.'}), 404

        titre = request.form.get('titre', existing['titre']).strip()
        matiere = request.form.get('matiere', existing['matiere']).strip()
        description = request.form.get('description', existing['description']).strip()
        video_url = request.form.get('video_url', existing['video_url']).strip()
        cours_type = request.form.get('cours_type', existing['cours_type'] or 'fichier')
        exercice_type = request.form.get('exercice_type', existing['exercice_type'] or 'fichier')

        cours_texte = request.form.get('cours_texte', existing['cours_texte'] or '').strip() if cours_type == 'texte' else (existing['cours_texte'] or '')
        cours_qcm = request.form.get('cours_qcm', existing['cours_qcm'] or '[]') if cours_type == 'qcm' else (existing['cours_qcm'] or '[]')
        exercice_texte = request.form.get('exercice_texte', existing['exercice_texte'] or '').strip() if exercice_type == 'texte' else (existing['exercice_texte'] or '')
        exercice_qcm = request.form.get('exercice_qcm', existing['exercice_qcm'] or '[]') if exercice_type == 'qcm' else (existing['exercice_qcm'] or '[]')
        remove_video_file = request.form.get('remove_video_file') == '1'
        remove_cours_file = request.form.get('remove_cours_file') == '1'
        remove_exercice_file = request.form.get('remove_exercice_file') == '1'

        video_filename = existing['video_filename']
        try:
            if remove_video_file and video_filename:
                remove_file(os.path.join(UPLOAD_VIDEOS, video_filename))
                video_filename = ''
            if 'video_file' in request.files and request.files['video_file'].filename:
                if video_filename:
                    remove_file(os.path.join(UPLOAD_VIDEOS, video_filename))
                video_filename = save_uploaded_file(request.files['video_file'], UPLOAD_VIDEOS, ALLOWED_VIDEO)

            cours_fichier = existing['cours_fichier']
            if remove_cours_file and cours_fichier:
                remove_file(os.path.join(UPLOAD_COURS, cours_fichier))
                cours_fichier = ''
            if cours_type == 'fichier' and 'cours_fichier' in request.files and request.files['cours_fichier'].filename:
                if cours_fichier:
                    remove_file(os.path.join(UPLOAD_COURS, cours_fichier))
                cours_fichier = save_uploaded_file(request.files['cours_fichier'], UPLOAD_COURS, ALLOWED_DOC)

            exercice_fichier = existing['exercice_fichier']
            if remove_exercice_file and exercice_fichier:
                remove_file(os.path.join(UPLOAD_EXOS, exercice_fichier))
                exercice_fichier = ''
            if exercice_type == 'fichier' and 'exercice_fichier' in request.files and request.files['exercice_fichier'].filename:
                if exercice_fichier:
                    remove_file(os.path.join(UPLOAD_EXOS, exercice_fichier))
                exercice_fichier = save_uploaded_file(request.files['exercice_fichier'], UPLOAD_EXOS, ALLOWED_DOC)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400

        db.execute(
            '''UPDATE cours SET titre=?, matiere=?, description=?, video_filename=?, video_url=?,
                cours_type=?, cours_fichier=?, cours_texte=?, cours_qcm=?,
                exercice_type=?, exercice_fichier=?, exercice_texte=?, exercice_qcm=?
               WHERE id = ?''',
            (titre, matiere, description, video_filename, video_url,
             cours_type, cours_fichier, cours_texte, cours_qcm,
             exercice_type, exercice_fichier, exercice_texte, exercice_qcm, cours_id)
        )
        db.commit()
        cours = db.execute('SELECT * FROM cours WHERE id = ?', (cours_id,)).fetchone()
    return jsonify(serialize_cours(cours))


@app.route('/api/cours/<int:cours_id>', methods=['DELETE'])
@login_required
def api_delete_cours(cours_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accès refusé.'}), 403

    with get_db() as db:
        existing = db.execute('SELECT * FROM cours WHERE id = ?', (cours_id,)).fetchone()
        if not existing:
            return jsonify({'error': 'Cours introuvable.'}), 404

        if existing['video_filename']:
            remove_file(os.path.join(UPLOAD_VIDEOS, existing['video_filename']))
        if existing['cours_fichier']:
            remove_file(os.path.join(UPLOAD_COURS, existing['cours_fichier']))
        if existing['exercice_fichier']:
            remove_file(os.path.join(UPLOAD_EXOS, existing['exercice_fichier']))

        db.execute('DELETE FROM cours WHERE id = ?', (cours_id,))
        db.commit()
    return jsonify({'ok': True})


@app.route('/uploads/videos/<path:filename>')
@login_required
def uploaded_video(filename):
    return send_from_directory(UPLOAD_VIDEOS, filename)


@app.route('/uploads/cours/<path:filename>')
@login_required
def uploaded_cours(filename):
    return send_from_directory(UPLOAD_COURS, filename)


@app.route('/uploads/exercices/<path:filename>')
@login_required
def uploaded_exercice(filename):
    return send_from_directory(UPLOAD_EXOS, filename)


@app.route('/')
def index():
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


@app.route('/admin/video/<int:cours_id>')
@login_required
def admin_video(cours_id):
    with get_db() as db:
        cours = db.execute('SELECT * FROM cours WHERE id = ?', (cours_id,)).fetchone()
        if not cours:
            return redirect(url_for('admin_education'))
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE is_read=0').fetchone()[0]
    return render_template('video.html', cours=cours, notif_count=notif_count)


@app.route('/admin/test')
@login_required
def admin_test():
    with get_db() as db:
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE is_read=0').fetchone()[0]
    return render_template('admin/test.html', notif_count=notif_count)
@app.route('/admin/test/resultats')
@login_required
def admin_test_resultat():
    #with get_db() as db:
        #notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE is_read=0').fetchone()[0]
    return render_template('admin/resultat.html')

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


@app.route('/api/logout')
def api_logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/dashboard_admin')
def dashboard_admin_alias():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return redirect(url_for('dashboard_admin'))


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
