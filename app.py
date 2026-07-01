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
import json

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'digiscool-secret-2025')
app.config['MAX_CONTENT_LENGTH'] = 150 * 1024 * 1024

DB_PATH = os.path.join(BASE_DIR, 'instance', 'digiscool.db')
UPLOAD_VIDEOS = os.path.join(BASE_DIR, 'uploads', 'videos')
UPLOAD_DOCS = os.path.join(BASE_DIR, 'uploads', 'documents')
UPLOAD_COURS = os.path.join(BASE_DIR, 'uploads', 'cours')
UPLOAD_EXOS = os.path.join(BASE_DIR, 'uploads', 'exercices')
UPLOAD_TESTS_EXERCICE = os.path.join(BASE_DIR, 'uploads', 'tests', 'exercices')
UPLOAD_TESTS_EXAMEN = os.path.join(BASE_DIR, 'uploads', 'tests', 'examens')
UPLOAD_REPONSES = os.path.join(BASE_DIR, 'uploads', 'reponses')

ALLOWED_VIDEO = {'mp4', 'webm', 'ogg', 'mov', 'avi'}
ALLOWED_DOC = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip', 'png', 'jpg', 'jpeg'}

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(UPLOAD_VIDEOS, exist_ok=True)
os.makedirs(UPLOAD_DOCS, exist_ok=True)
os.makedirs(UPLOAD_COURS, exist_ok=True)
os.makedirs(UPLOAD_EXOS, exist_ok=True)
os.makedirs(UPLOAD_TESTS_EXERCICE, exist_ok=True)
os.makedirs(UPLOAD_TESTS_EXAMEN, exist_ok=True)
os.makedirs(UPLOAD_REPONSES, exist_ok=True)


def upload_dir_for_categorie(categorie):
    """Retourne le dossier d'upload selon la categorie (exercice/examen)."""
    return UPLOAD_TESTS_EXAMEN if categorie == 'examen' else UPLOAD_TESTS_EXERCICE


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT DEFAULT '',
                prenom TEXT DEFAULT '',
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                statut TEXT NOT NULL DEFAULT 'En attente',
                sexe TEXT DEFAULT '',
                adresse TEXT DEFAULT '',
                classe TEXT DEFAULT '',
                dob TEXT DEFAULT '',
                profession TEXT DEFAULT '',
                etablissement TEXT DEFAULT '',
                filiere TEXT DEFAULT '',
                lien_etablissement TEXT DEFAULT '',
                matricule TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        user_columns = [row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()]
        for col, col_def in [
            ('nom', "TEXT DEFAULT ''"),
            ('prenom', "TEXT DEFAULT ''"),
            ('statut', "TEXT NOT NULL DEFAULT 'En attente'"),
            ('sexe', "TEXT DEFAULT ''"),
            ('adresse', "TEXT DEFAULT ''"),
            ('classe', "TEXT DEFAULT ''"),
            ('dob', "TEXT DEFAULT ''"),
            ('profession', "TEXT DEFAULT ''"),
            ('etablissement', "TEXT DEFAULT ''"),
            ('filiere', "TEXT DEFAULT ''"),
            ('lien_etablissement', "TEXT DEFAULT ''"),
            ('matricule', "TEXT DEFAULT ''"),
            ('phone', "TEXT DEFAULT ''"),
        ]:
            if col not in user_columns:
                db.execute(f'ALTER TABLE users ADD COLUMN {col} {col_def}')

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
                target_url TEXT DEFAULT '',
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        notification_columns = [row[1] for row in db.execute("PRAGMA table_info(notifications)").fetchall()]
        for col, col_def in [
            ('user_id', "INTEGER NOT NULL"),
            ('message', "TEXT NOT NULL"),
            ('target_url', "TEXT DEFAULT ''"),
            ('is_read', "INTEGER NOT NULL DEFAULT 0"),
            ('created_at', "DATETIME DEFAULT CURRENT_TIMESTAMP"),
        ]:
            if col not in notification_columns:
                db.execute(f'ALTER TABLE notifications ADD COLUMN {col} {col_def}')
        db.execute('''
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categorie TEXT NOT NULL DEFAULT 'exercice',
                content_type TEXT NOT NULL DEFAULT 'fichier',
                titre TEXT DEFAULT '',
                fichier_nom TEXT DEFAULT '',
                fichier_url TEXT DEFAULT '',
                contenu_texte TEXT DEFAULT '',
                contenu_qcm TEXT DEFAULT '[]',
                date_debut TEXT DEFAULT '',
                heure_debut TEXT DEFAULT '',
                date_fin TEXT DEFAULT '',
                heure_fin TEXT DEFAULT '',
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(created_by) REFERENCES users(id)
            )
        ''')
        tests_columns = [row[1] for row in db.execute("PRAGMA table_info(tests)").fetchall()]
        for col, col_def in [
            ('categorie', "TEXT NOT NULL DEFAULT 'exercice'"),
            ('content_type', "TEXT NOT NULL DEFAULT 'fichier'"),
            ('titre', "TEXT DEFAULT ''"),
            ('fichier_nom', "TEXT DEFAULT ''"),
            ('fichier_url', "TEXT DEFAULT ''"),
            ('contenu_texte', "TEXT DEFAULT ''"),
            ('contenu_qcm', "TEXT DEFAULT '[]'"),
            ('date_debut', "TEXT DEFAULT ''"),
            ('heure_debut', "TEXT DEFAULT ''"),
            ('date_fin', "TEXT DEFAULT ''"),
            ('heure_fin', "TEXT DEFAULT ''"),
            ('created_by', "INTEGER"),
            ('created_at', "DATETIME DEFAULT CURRENT_TIMESTAMP"),
        ]:
            if col not in tests_columns:
                db.execute(f'ALTER TABLE tests ADD COLUMN {col} {col_def}')
        db.execute('''
            CREATE TABLE IF NOT EXISTS commentaires (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                cours_id INTEGER,
                texte TEXT DEFAULT '',
                note REAL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(cours_id) REFERENCES cours(id)
            )
        ''')
        commentaire_columns = [row[1] for row in db.execute("PRAGMA table_info(commentaires)").fetchall()]
        for col, col_def in [
            ('user_id', "INTEGER"),
            ('cours_id', "INTEGER"),
            ('texte', "TEXT DEFAULT ''"),
            ('note', "REAL DEFAULT 0"),
            ('reponse', "TEXT DEFAULT ''"),
            ('created_at', "DATETIME DEFAULT CURRENT_TIMESTAMP"),
        ]:
            if col not in commentaire_columns:
                db.execute(f'ALTER TABLE commentaires ADD COLUMN {col} {col_def}')
        db.execute('''
            CREATE TABLE IF NOT EXISTS test_resultats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reponses TEXT DEFAULT '[]',
                fichier_reponse TEXT DEFAULT '',
                note REAL,
                submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(test_id) REFERENCES tests(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        resultats_columns = [row[1] for row in db.execute("PRAGMA table_info(test_resultats)").fetchall()]
        for col, col_def in [
            ('reponses', "TEXT DEFAULT '[]'"),
            ('fichier_reponse', "TEXT DEFAULT ''"),
            ('note', "REAL"),
            ('submitted_at', "DATETIME DEFAULT CURRENT_TIMESTAMP"),
        ]:
            if col not in resultats_columns:
                db.execute(f'ALTER TABLE test_resultats ADD COLUMN {col} {col_def}')
        if not db.execute('SELECT 1 FROM users WHERE email=?', ('admin@digiscool.mg',)).fetchone():
            db.execute(
                'INSERT INTO users(nom,prenom,name,email,password_hash,role,statut) VALUES(?,?,?,?,?,?,?)',
                ('Admin', 'Admin', 'Admin', 'admin@digiscool.mg', generate_password_hash('admin123'), 'admin', 'Approuvé')
            )
        db.execute("UPDATE users SET statut='Approuvé' WHERE email=? AND (statut IS NULL OR statut='')", ('admin@digiscool.mg',))
        db.execute("UPDATE users SET statut='En attente' WHERE statut IS NULL",)
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
    if not email:
        return None
    with get_db() as db:
        return db.execute('SELECT * FROM users WHERE LOWER(email)=?', (email.lower(),)).fetchone()


def normalize_video_url(url):
    if not url:
        return ''
    cleaned = url.strip()
    if 'youtube.com/watch?v=' in cleaned:
        return cleaned.replace('watch?v=', 'embed/')
    if 'youtu.be/' in cleaned:
        return cleaned.replace('youtu.be/', 'www.youtube.com/embed/')
    return cleaned


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


def serialize_commentaire(row):
    return {
        'id': row['id'],
        'user_id': row['user_id'],
        'cours_id': row['cours_id'],
        'texte': row['texte'],
        'note': row['note'],
        'reponse': row['reponse'] if 'reponse' in row.keys() else '',
        'created_at': row['created_at'],
        'user_name': row['user_name'] if 'user_name' in row.keys() else None,
    }


def serialize_test(row):
    return {
        'id': row['id'],
        'categorie': row['categorie'],
        'content_type': row['content_type'],
        'titre': row['titre'],
        'fichier_nom': row['fichier_nom'],
        'fichier_url': row['fichier_url'],
        'contenu_texte': row['contenu_texte'],
        'contenu_qcm': row['contenu_qcm'],
        'date_debut': row['date_debut'],
        'heure_debut': row['heure_debut'],
        'date_fin': row['date_fin'],
        'heure_fin': row['heure_fin'],
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
        payload = []
        for row in rows:
            cours_data = serialize_cours(row)
            comments = db.execute(
                '''SELECT c.*, u.name AS user_name
                   FROM commentaires c
                   LEFT JOIN users u ON u.id = c.user_id
                   WHERE c.cours_id=?
                   ORDER BY c.created_at DESC''',
                (row['id'],)
            ).fetchall()
            cours_data['notes'] = [serialize_commentaire(comment_row) for comment_row in comments]
            payload.append(cours_data)
    return jsonify(payload)


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


@app.route('/api/tests', methods=['GET'])
@login_required
def api_get_tests():
    """Liste des tests (exercices/examens) - utilisee par user/test_user.html et admin/test.html."""
    categorie = request.args.get('categorie', '').strip()
    query = 'SELECT * FROM tests'
    params = []
    if categorie in ('exercice', 'examen'):
        query += ' WHERE categorie = ?'
        params.append(categorie)
    query += ' ORDER BY created_at DESC'
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    return jsonify([serialize_test(row) for row in rows])


@app.route('/api/tests/<int:test_id>', methods=['GET'])
@login_required
def api_get_test(test_id):
    with get_db() as db:
        row = db.execute('SELECT * FROM tests WHERE id = ?', (test_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Test introuvable.'}), 404
    return jsonify(serialize_test(row))


@app.route('/api/tests', methods=['POST'])
@login_required
@admin_required
def api_create_test():
    """Insertion d'un test par l'admin : stocke le fichier sur disque (si fourni)
    et les metadonnees/texte/QCM dans la base de donnees."""
    categorie = request.form.get('categorie', 'exercice').strip()
    if categorie not in ('exercice', 'examen'):
        categorie = 'exercice'
    content_type = request.form.get('content_type', 'fichier').strip()
    if content_type not in ('fichier', 'texte', 'qcm'):
        content_type = 'fichier'

    titre = request.form.get('titre', '').strip()
    date_debut = request.form.get('date_debut', '').strip()
    heure_debut = request.form.get('heure_debut', '').strip()
    date_fin = request.form.get('date_fin', '').strip()
    heure_fin = request.form.get('heure_fin', '').strip()

    fichier_nom = ''
    fichier_url = ''
    contenu_texte = ''
    contenu_qcm = '[]'

    try:
        if content_type == 'fichier':
            fichier_url = request.form.get('fichier_url', '').strip()
            if 'fichier' in request.files and request.files['fichier'].filename:
                fichier_nom = save_uploaded_file(
                    request.files['fichier'], upload_dir_for_categorie(categorie), ALLOWED_DOC
                )
        elif content_type == 'texte':
            contenu_texte = request.form.get('contenu_texte', '').strip()
        elif content_type == 'qcm':
            contenu_qcm = request.form.get('contenu_qcm', '[]')
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    if content_type == 'fichier' and not fichier_nom and not fichier_url:
        return jsonify({'error': 'Veuillez importer un fichier ou fournir une URL.'}), 400
    if content_type == 'texte' and not contenu_texte:
        return jsonify({'error': 'Le texte est requis.'}), 400
    if content_type == 'qcm' and contenu_qcm in ('[]', ''):
        return jsonify({'error': 'Au moins une question QCM est requise.'}), 400

    with get_db() as db:
        cur = db.execute(
            '''INSERT INTO tests (categorie, content_type, titre, fichier_nom, fichier_url,
                contenu_texte, contenu_qcm, date_debut, heure_debut, date_fin, heure_fin, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (categorie, content_type, titre, fichier_nom, fichier_url,
             contenu_texte, contenu_qcm, date_debut, heure_debut, date_fin, heure_fin,
             session['user_id'])
        )
        new_id = cur.lastrowid
        # Notifie tous les utilisateurs (hors admins) qu'un nouveau test est disponible
        label = 'examen' if categorie == 'examen' else 'exercice'
        users = db.execute("SELECT id FROM users WHERE role != 'admin'").fetchall()
        for u in users:
            db.execute(
                'INSERT INTO notifications (user_id, message, target_url) VALUES (?, ?, ?)',
                (u['id'], f"Nouveau {label} disponible : {titre or 'Sans titre'}", f"/user/test?focus_test_id={new_id}")
            )
        db.commit()
        test = db.execute('SELECT * FROM tests WHERE id = ?', (new_id,)).fetchone()
    return jsonify(serialize_test(test))


@app.route('/api/tests/<int:test_id>', methods=['PUT'])
@login_required
@admin_required
def api_update_test(test_id):
    """Modification d'un test existant (fichier/texte/QCM) par l'admin.
    Réutilise la même logique de validation que la création."""
    with get_db() as db:
        existing = db.execute('SELECT * FROM tests WHERE id = ?', (test_id,)).fetchone()
        if not existing:
            return jsonify({'error': 'Test introuvable.'}), 404

        categorie = request.form.get('categorie', existing['categorie']).strip()
        if categorie not in ('exercice', 'examen'):
            categorie = existing['categorie']
        content_type = request.form.get('content_type', existing['content_type']).strip()
        if content_type not in ('fichier', 'texte', 'qcm'):
            content_type = existing['content_type']

        titre = request.form.get('titre', existing['titre'] or '').strip()
        date_debut = request.form.get('date_debut', existing['date_debut'] or '').strip()
        heure_debut = request.form.get('heure_debut', existing['heure_debut'] or '').strip()
        date_fin = request.form.get('date_fin', existing['date_fin'] or '').strip()
        heure_fin = request.form.get('heure_fin', existing['heure_fin'] or '').strip()

        fichier_nom = existing['fichier_nom'] or ''
        fichier_url = existing['fichier_url'] or ''
        contenu_texte = existing['contenu_texte'] or ''
        contenu_qcm = existing['contenu_qcm'] or '[]'

        try:
            if content_type == 'fichier':
                new_url = request.form.get('fichier_url', '').strip()
                if 'fichier' in request.files and request.files['fichier'].filename:
                    # Nouveau fichier local importé : remplace l'ancien
                    if existing['fichier_nom']:
                        remove_file(os.path.join(upload_dir_for_categorie(existing['categorie']), existing['fichier_nom']))
                    fichier_nom = save_uploaded_file(
                        request.files['fichier'], upload_dir_for_categorie(categorie), ALLOWED_DOC
                    )
                    fichier_url = ''
                elif new_url:
                    fichier_url = new_url
                    if existing['fichier_nom']:
                        remove_file(os.path.join(upload_dir_for_categorie(existing['categorie']), existing['fichier_nom']))
                    fichier_nom = ''
                contenu_texte = ''
                contenu_qcm = '[]'
            elif content_type == 'texte':
                contenu_texte = request.form.get('contenu_texte', '').strip()
                fichier_nom = ''
                fichier_url = ''
                contenu_qcm = '[]'
            elif content_type == 'qcm':
                contenu_qcm = request.form.get('contenu_qcm', '[]')
                fichier_nom = ''
                fichier_url = ''
                contenu_texte = ''
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400

        if content_type == 'fichier' and not fichier_nom and not fichier_url:
            return jsonify({'error': 'Veuillez importer un fichier ou fournir une URL.'}), 400
        if content_type == 'texte' and not contenu_texte:
            return jsonify({'error': 'Le texte est requis.'}), 400
        if content_type == 'qcm' and contenu_qcm in ('[]', ''):
            return jsonify({'error': 'Au moins une question QCM est requise.'}), 400

        db.execute(
            '''UPDATE tests SET categorie=?, content_type=?, titre=?, fichier_nom=?, fichier_url=?,
               contenu_texte=?, contenu_qcm=?, date_debut=?, heure_debut=?, date_fin=?, heure_fin=?
               WHERE id=?''',
            (categorie, content_type, titre, fichier_nom, fichier_url,
             contenu_texte, contenu_qcm, date_debut, heure_debut, date_fin, heure_fin, test_id)
        )
        db.commit()
        test = db.execute('SELECT * FROM tests WHERE id = ?', (test_id,)).fetchone()
    return jsonify(serialize_test(test))


@app.route('/api/tests/<int:test_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_test(test_id):
    with get_db() as db:
        existing = db.execute('SELECT * FROM tests WHERE id = ?', (test_id,)).fetchone()
        if not existing:
            return jsonify({'error': 'Test introuvable.'}), 404
        if existing['fichier_nom']:
            remove_file(os.path.join(upload_dir_for_categorie(existing['categorie']), existing['fichier_nom']))
        db.execute('DELETE FROM tests WHERE id = ?', (test_id,))
        db.commit()
    return jsonify({'ok': True})


@app.route('/api/tests/bulk_delete', methods=['POST'])
@login_required
@admin_required
def api_bulk_delete_tests():
    """Supprime plusieurs tests en une seule requete (ids en JSON)."""
    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])
    if not ids or not isinstance(ids, list):
        return jsonify({'error': "Liste d'ids requise."}), 400
    deleted = 0
    with get_db() as db:
        for test_id in ids:
            try:
                test_id = int(test_id)
            except (TypeError, ValueError):
                continue
            existing = db.execute('SELECT * FROM tests WHERE id = ?', (test_id,)).fetchone()
            if not existing:
                continue
            if existing['fichier_nom']:
                remove_file(os.path.join(upload_dir_for_categorie(existing['categorie']), existing['fichier_nom']))
            db.execute('DELETE FROM tests WHERE id = ?', (test_id,))
            deleted += 1
        db.commit()
    return jsonify({'ok': True, 'deleted': deleted})


@app.route('/api/tests/<int:test_id>/resultats', methods=['POST'])
@login_required
def api_submit_test_resultat(test_id):
    """Soumission de la reponse d'un utilisateur (QCM -> JSON, fichier -> upload).
    Notifie les administrateurs avec le nom de l'utilisateur et la date/heure d'envoi."""
    import json as _json
    with get_db() as db:
        test = db.execute('SELECT * FROM tests WHERE id = ?', (test_id,)).fetchone()
        if not test:
            return jsonify({'error': 'Test introuvable.'}), 404

        reponses_json = '[]'
        fichier_reponse = ''

        is_multipart = bool(request.files) or request.content_type and 'multipart/form-data' in request.content_type
        if is_multipart:
            if 'fichier_reponse' in request.files and request.files['fichier_reponse'].filename:
                try:
                    fichier_reponse = save_uploaded_file(request.files['fichier_reponse'], UPLOAD_REPONSES, ALLOWED_DOC)
                except ValueError as exc:
                    return jsonify({'error': str(exc)}), 400
            else:
                return jsonify({'error': 'Aucun fichier reçu.'}), 400
        else:
            data = request.get_json(silent=True) or {}
            texte_reponse = data.get('texte_reponse', '')
            if texte_reponse is not None and str(texte_reponse).strip():
                reponses_json = _json.dumps([{'type': 'texte', 'reponse': str(texte_reponse).strip()}])
            else:
                reponses = data.get('reponses', [])
                if not reponses:
                    return jsonify({'error': 'Aucune réponse à envoyer.'}), 400
                reponses_json = _json.dumps(reponses)

        cur = db.execute(
            'INSERT INTO test_resultats (test_id, user_id, reponses, fichier_reponse) VALUES (?, ?, ?, ?)',
            (test_id, session['user_id'], reponses_json, fichier_reponse)
        )
        result_id = cur.lastrowid

        horodatage = time.strftime('%d/%m/%Y %H:%M')
        label = 'examen' if test['categorie'] == 'examen' else 'exercice'
        nom_user = session.get('name', 'Utilisateur')
        message = f"{nom_user} a envoyé sa réponse pour l'{label} \"{test['titre'] or 'Sans titre'}\" le {horodatage}"
        admins = db.execute("SELECT id FROM users WHERE role='admin'").fetchall()
        for a in admins:
            db.execute(
                'INSERT INTO notifications (user_id, message, target_url) VALUES (?, ?, ?)',
                (a['id'], message, f"/admin/test/travaille_user?result_id={result_id}")
            )

        db.commit()
    return jsonify({'ok': True, 'envoye_par': session.get('name'), 'date_envoi': horodatage})


@app.route('/files/reponses/<path:filename>')
@login_required
@admin_required
def file_reponse(filename):
    return send_from_directory(UPLOAD_REPONSES, filename)


@app.route('/files/tests/<categorie>/<path:filename>')
@login_required
def file_test(categorie, filename):
    return send_from_directory(upload_dir_for_categorie(categorie), filename)


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
        notif_count = db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id IN (SELECT id FROM users WHERE role='admin') AND is_read=0"
        ).fetchone()[0]
    return render_template('admin/dashboard.html', admin_name=session.get('name'), users=users, cours=cours, notif_count=notif_count)


@app.route('/dashboard/user')
@login_required
def dashboard_user():
    with get_db() as db:
        cours = db.execute('SELECT * FROM cours ORDER BY created_at DESC').fetchall()
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)).fetchone()[0]
    return render_template('user/dashboard.html', user_name=session.get('name'), cours=cours, notif_count=notif_count)


@app.route('/user/dashboard')
@login_required
def user_dashboard_alias():
    if session.get('role') == 'admin':
        return redirect(url_for('dashboard_admin'))
    return redirect(url_for('dashboard_user'))


@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard_alias():
    return redirect(url_for('dashboard_admin'))


@app.route('/admin/education')
@login_required
@admin_required
def admin_education():
    with get_db() as db:
        cours = db.execute('SELECT * FROM cours ORDER BY created_at DESC').fetchall()
        notif_count = db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id IN (SELECT id FROM users WHERE role='admin') AND is_read=0"
        ).fetchone()[0]
    return render_template('admin/education.html', cours=cours, notif_count=notif_count)


@app.route('/admin/video/<int:cours_id>')
@login_required
@admin_required
def admin_video(cours_id):
    with get_db() as db:
        cours = db.execute('SELECT * FROM cours WHERE id = ?', (cours_id,)).fetchone()
        if not cours:
            return redirect(url_for('admin_education'))
        notif_count = db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id IN (SELECT id FROM users WHERE role='admin') AND is_read=0"
        ).fetchone()[0]
    return render_template('video.html', cours=cours, notif_count=notif_count)


@app.route('/admin/test')
@login_required
@admin_required
def admin_test():
    with get_db() as db:
        notif_count = db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id IN (SELECT id FROM users WHERE role='admin') AND is_read=0"
        ).fetchone()[0]
        tests = db.execute('SELECT * FROM tests ORDER BY created_at DESC').fetchall()
    return render_template('admin/test.html', notif_count=notif_count, tests=tests)
@app.route('/admin/test/resultats')
@login_required
@admin_required
def admin_test_resultat():
    with get_db() as db:
        notif_count = db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id IN (SELECT id FROM users WHERE role='admin') AND is_read=0"
        ).fetchone()[0]
        query = '''
            SELECT r.id, r.test_id, r.user_id, r.submitted_at,
                   t.titre AS test_titre, t.categorie AS test_categorie, t.content_type,
                   u.nom, u.prenom, u.name
            FROM test_resultats r
            JOIN tests t ON r.test_id = t.id
            JOIN users u ON r.user_id = u.id
            ORDER BY r.submitted_at DESC
        '''
        results = db.execute(query).fetchall()
    return render_template('admin/resultat.html', notif_count=notif_count, results=results)
@app.route('/admin/test/travaille_user')
@login_required
@admin_required
def admin_travaille_user():
    result_id = request.args.get('result_id', type=int)
    with get_db() as db:
        notif_count = db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id IN (SELECT id FROM users WHERE role='admin') AND is_read=0"
        ).fetchone()[0]
        base_query = '''
            SELECT r.*, t.titre AS test_titre, t.categorie AS test_categorie,
                   t.content_type AS test_content_type, t.fichier_nom AS test_fichier_nom,
                   t.fichier_url AS test_fichier_url, t.contenu_texte AS test_contenu_texte,
                   t.contenu_qcm AS test_contenu_qcm, u.nom AS user_nom, u.prenom AS user_prenom,
                   u.name AS user_name
            FROM test_resultats r
            JOIN tests t ON r.test_id = t.id
            JOIN users u ON r.user_id = u.id
        '''
        results = db.execute(base_query + ' ORDER BY r.submitted_at DESC').fetchall()
        selected_result = None
        selected_reponses = []
        if result_id:
            selected_result = db.execute(base_query + ' WHERE r.id = ? LIMIT 1', (result_id,)).fetchone()
            if selected_result and selected_result['reponses']:
                try:
                    selected_reponses = json.loads(selected_result['reponses'])
                except ValueError:
                    selected_reponses = []
    return render_template(
        'admin/travaille_user.html',
        notif_count=notif_count,
        results=results,
        selected_result=selected_result,
        selected_reponses=selected_reponses
    )
@app.route('/api/test_resultats/<int:result_id>/user_info')
@login_required
@admin_required
def api_test_resultat_user_info(result_id):
    """Retourne les informations de l'utilisateur lié à un résultat de test,
    pour affichage dans la fenêtre modale déclenchée par le bouton 'i'."""
    with get_db() as db:
        row = db.execute(
            '''SELECT u.* FROM test_resultats r
               JOIN users u ON r.user_id = u.id
               WHERE r.id = ?''',
            (result_id,)
        ).fetchone()
        if not row:
            return jsonify({'error': "Utilisateur introuvable."}), 404
        user = dict(row)

    nom = user.get('nom') or ''
    prenom = user.get('prenom') or ''
    full_name = (user.get('name') or f"{prenom} {nom}".strip() or '').strip()

    age = None
    dob = (user.get('dob') or '').strip()
    if dob:
        try:
            from datetime import date
            birth = date.fromisoformat(dob[:10])
            today = date.today()
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        except ValueError:
            age = None

    return jsonify({
        'full_name': full_name or 'N/A',
        'classe': user.get('classe') or 'N/A',
        'matricule': user.get('matricule') or 'N/A',
        'age': age if age is not None else 'N/A',
        'adresse': user.get('adresse') or 'N/A',
        'email': user.get('email') or 'N/A',
        'phone': user.get('phone') or 'N/A',
        'sexe': user.get('sexe') or 'N/A',
    })


@app.route('/admin/utilisateur')
@login_required
@admin_required
def admin_utilisateur():
    with get_db() as db:
        rows = db.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
        users = []
        for row in rows:
            user = dict(row)
            user['nom'] = user.get('nom') or ''
            user['prenom'] = user.get('prenom') or ''
            user['username'] = user.get('username') or ''
            user['phone'] = user.get('phone') or ''
            user['adresse'] = user.get('adresse') or ''
            user['profession'] = user.get('profession') or ''
            user['dob'] = user.get('dob') or ''
            user['classe'] = user.get('classe') or ''
            user['filiere'] = user.get('filiere') or ''
            user['etablissement'] = user.get('etablissement') or ''
            user['lien_etablissement'] = user.get('lien_etablissement') or ''
            user['statut'] = user.get('statut') or 'En attente'
            users.append(user)
    return render_template('admin/utilisateur.html', users=users)

@app.route('/api/users/<int:user_id>/statut', methods=['POST'])
@login_required
@admin_required
def api_update_user_statut(user_id):
    data = request.get_json(silent=True) or {}
    statut = data.get('statut', '').strip()
    if statut not in ('Approuvé', 'En attente', 'Rejeté'):
        return jsonify({'error': 'Statut invalide.'}), 400
    with get_db() as db:
        user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not user:
            return jsonify({'error': 'Utilisateur introuvable.'}), 404
        db.execute('UPDATE users SET statut=? WHERE id=?', (statut, user_id))
        db.commit()
    return jsonify({'ok': True, 'statut': statut})

@app.route('/user/education')
@login_required
def user_education():
    with get_db() as db:
        cours = db.execute('SELECT * FROM cours ORDER BY created_at DESC').fetchall()
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)).fetchone()[0]
    return render_template('user/education_user.html', cours=cours, user_name=session.get('name'), notif_count=notif_count)


@app.route('/user/education_user')
@login_required
def user_education_user():
    return redirect(url_for('user_education'))


@app.route('/user/video/<int:cours_id>')
@login_required
def user_video(cours_id):
    with get_db() as db:
        cours = db.execute('SELECT * FROM cours WHERE id = ?', (cours_id,)).fetchone()
        if not cours:
            return redirect(url_for('user_education'))
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)).fetchone()[0]
    video_src = normalize_video_url(cours['video_url']) if cours['video_url'] else ''
    return render_template('user/affichage_video.html', cours=cours, video_src=video_src, user_name=session.get('name'), notif_count=notif_count)

@app.route('/user/commentaire/<int:cours_id>')
@login_required
def user_commentaire(cours_id):
    with get_db() as db:
        cours = db.execute('SELECT * FROM cours WHERE id = ?', (cours_id,)).fetchone()
        if not cours:
            return redirect(url_for('user_education'))
        comments = db.execute(
            'SELECT c.*, u.name FROM commentaires c JOIN users u ON c.user_id=u.id WHERE c.cours_id=? ORDER BY c.created_at DESC',
            (cours_id,)
        ).fetchall()
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)).fetchone()[0]
    video_src = normalize_video_url(cours['video_url']) if cours['video_url'] else ''
    return render_template('user/commentaire_user.html', cours=cours, comments=comments, video_src=video_src, user_name=session.get('name'), notif_count=notif_count)

@app.route('/user/test')
@login_required
def user_test():
    with get_db() as db:
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)).fetchone()[0]
        tests = db.execute('SELECT * FROM tests ORDER BY created_at DESC').fetchall()
    return render_template('user/test_user.html', user_name=session.get('name'), notif_count=notif_count, tests=tests)

@app.route('/user/notifications')
@login_required
def user_notifications():
    """Affiche la liste des notifications de l'utilisateur (sans marquer comme lue automatiquement)."""
    with get_db() as db:
        notifications = db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC', (session['user_id'],)).fetchall()
        notif_count = db.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)).fetchone()[0]
    return render_template('user/notifications.html', notifications=notifications, user_name=session.get('name'), notif_count=notif_count)


@app.route('/api/test_resultats/count')
@login_required
@admin_required
def api_test_resultats_count():
    """Polling : renvoie le nombre total de soumissions (pour détecter de nouveaux résultats)."""
    with get_db() as db:
        count = db.execute('SELECT COUNT(*) FROM test_resultats').fetchone()[0]
    return jsonify({'count': count})


@app.route('/api/test_resultats/<int:result_id>/note', methods=['POST'])
@login_required
@admin_required
def api_save_note(result_id):
    """Enregistre la note attribuée par l'admin à un résultat utilisateur."""
    data = request.get_json(silent=True) or {}
    note = data.get('note')
    if note is None:
        return jsonify({'error': 'Note manquante.'}), 400
    with get_db() as db:
        db.execute('UPDATE test_resultats SET note=? WHERE id=?', (note, result_id))
        db.commit()
    return jsonify({'ok': True, 'note': note})


@app.route('/api/notifications/count')
@login_required
def api_notifications_count():
    """Endpoint de polling : renvoie le compteur de notifications non lues.
    Appelé toutes les 10s par le frontend pour mettre à jour le badge en temps réel."""
    with get_db() as db:
        if session.get('role') == 'admin':
            count = db.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id IN (SELECT id FROM users WHERE role='admin') AND is_read=0"
            ).fetchone()[0]
        else:
            count = db.execute(
                'SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)
            ).fetchone()[0]
    return jsonify({'notif_count': count})


@app.route('/api/notifications/mark_read', methods=['POST'])
@login_required
def api_notifications_mark_read():
    """Appelée au clic sur l'icône de notification : marque les notifications comme lues
    et renvoie le nouveau compteur (pour mettre à jour le badge sans recharger la page)."""
    data = request.get_json(silent=True) or {}
    ids = data.get('ids')  # liste optionnelle d'ids précis à marquer comme lus
    with get_db() as db:
        if ids:
            placeholders = ','.join('?' for _ in ids)
            db.execute(
                f'UPDATE notifications SET is_read=1 WHERE user_id=? AND id IN ({placeholders})',
                (session['user_id'], *ids)
            )
        else:
            db.execute('UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0', (session['user_id'],))
        db.commit()
        notif_count = db.execute(
            'SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)
        ).fetchone()[0]
    return jsonify({'ok': True, 'notif_count': notif_count})


@app.route('/api/notifications/<int:notif_id>', methods=['DELETE'])
@login_required
def api_delete_notification(notif_id):
    """Supprime une notification spécifique de l'utilisateur connecté."""
    with get_db() as db:
        notif = db.execute('SELECT * FROM notifications WHERE id=?', (notif_id,)).fetchone()
        if not notif:
            return jsonify({'error': 'Notification introuvable.'}), 404
        # Vérifier que l'utilisateur est propriétaire de la notification ou admin
        if session['role'] != 'admin' and notif['user_id'] != session['user_id']:
            return jsonify({'error': 'Accès refusé.'}), 403
        db.execute('DELETE FROM notifications WHERE id=?', (notif_id,))
        db.commit()
    return jsonify({'ok': True})


@app.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def api_notification_read(notif_id):
    """Marque une notification comme lue et retourne le nouveau compteur."""
    with get_db() as db:
        notif = db.execute('SELECT * FROM notifications WHERE id=?', (notif_id,)).fetchone()
        if not notif:
            return jsonify({'error': 'Notification introuvable.'}), 404
        # Vérifier que l'utilisateur est propriétaire ou admin
        if session['role'] != 'admin' and notif['user_id'] != session['user_id']:
            return jsonify({'error': 'Accès refusé.'}), 403
        db.execute('UPDATE notifications SET is_read=1 WHERE id=?', (notif_id,))
        db.commit()
        # Retourner le nouveau compteur
        notif_count = db.execute(
            'SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)
        ).fetchone()[0]
    return jsonify({'ok': True, 'notif_count': notif_count})


@app.route('/admin/notifications')
@login_required
@admin_required
def admin_notifications():
    """Affiche toutes les notifications destinées à l'admin connecté."""
    with get_db() as db:
        notifications = db.execute(
            '''SELECT * FROM notifications WHERE user_id IN
               (SELECT id FROM users WHERE role='admin') ORDER BY created_at DESC'''
        ).fetchall()
        notif_count = db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id IN (SELECT id FROM users WHERE role='admin') AND is_read=0"
        ).fetchone()[0]
    return render_template('admin/notifications.html', notifications=notifications, notif_count=notif_count)


@app.route('/user/notification/<int:notif_id>')
@login_required
def user_notification_detail(notif_id):
    """Affiche le détail d'une notification pour l'utilisateur."""
    with get_db() as db:
        notif_row = db.execute(
            'SELECT * FROM notifications WHERE id=? AND user_id=?', (notif_id, session['user_id'])
        ).fetchone()
        if not notif_row:
            return redirect(url_for('user_notifications'))
        notif = dict(notif_row)
        # Marquer comme lue si elle ne l'est pas
        if not notif['is_read']:
            db.execute('UPDATE notifications SET is_read=1 WHERE id=?', (notif_id,))
            db.commit()
            notif['is_read'] = 1
        notif_count = db.execute(
            'SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],)
        ).fetchone()[0]
    return render_template('user/notification_detail.html', notif=notif, notif_count=notif_count)


@app.route('/api/commentaires', methods=['POST'])
@login_required
def api_commentaires():
    data = request.get_json(silent=True) or {}
    cours_id = data.get('cours_id')
    texte = (data.get('texte') or '').strip()
    note = int(data.get('note') or 0)
    if not cours_id or not texte:
        return jsonify({'error': 'Le commentaire et la note sont requis.'}), 400
    with get_db() as db:
        db.execute(
            'INSERT INTO commentaires (user_id, cours_id, texte, note) VALUES (?, ?, ?, ?)',
            (session['user_id'], cours_id, texte, note)
        )
        db.commit()
    return jsonify({'ok': True})


@app.route('/api/commentaires/<int:comment_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_comment(comment_id):
    """Permet à l'admin de supprimer un commentaire."""
    with get_db() as db:
        row = db.execute('SELECT * FROM commentaires WHERE id=?', (comment_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Commentaire introuvable.'}), 404
        db.execute('DELETE FROM commentaires WHERE id=?', (comment_id,))
        db.commit()
    return jsonify({'ok': True})


@app.route('/api/commentaires/<int:comment_id>/reponse', methods=['POST'])
@login_required
@admin_required
def api_reply_comment(comment_id):
    """Enregistre la réponse d'un admin à un commentaire."""
    data = request.get_json(silent=True) or {}
    reponse = (data.get('reponse') or '').strip()
    if not reponse:
        return jsonify({'error': "Réponse vide."}), 400
    with get_db() as db:
        row = db.execute('SELECT * FROM commentaires WHERE id=?', (comment_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Commentaire introuvable.'}), 404
        db.execute('UPDATE commentaires SET reponse=? WHERE id=?', (reponse, comment_id))
        db.commit()
    return jsonify({'ok': True, 'reponse': reponse})

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
    if user['role'] != 'admin' and user['statut'] != 'Approuvé':
        if user['statut'] == 'Rejeté':
            return jsonify({'error': 'Votre compte a été rejeté.'}), 403
        return jsonify({'error': 'Votre compte doit être approuvé par un administrateur.'}), 403
    session.clear()
    session['user_id'] = user['id']
    session['name'] = user['name']
    session['role'] = user['role']
    return jsonify({'name': user['name'], 'role': user['role']})


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json(silent=True) or {}
    nom = data.get('nom', '').strip()
    prenom = data.get('prenom', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    dob = data.get('dob', '').strip()
    sexe = data.get('sexe', '').strip()
    profession = data.get('profession', '').strip()
    classe = data.get('classe', '').strip()
    filiere = data.get('filiere', '').strip()
    etablissement = data.get('etablissement', '').strip()
    lien_etablissement = data.get('lien_etablissement', '').strip()
    adresse = data.get('adresse', '').strip()
    if not nom or not prenom or not email or not password:
        return jsonify({'error': 'Veuillez remplir les champs obligatoires.'}), 400
    if get_user_by_email(email):
        return jsonify({'error': 'Email déjà utilisé.'}), 409
    full_name = f"{prenom} {nom}".strip()
    with get_db() as db:
        db.execute(
            'INSERT INTO users(nom,prenom,name,email,password_hash,role,statut,dob,sexe,profession,classe,filiere,etablissement,lien_etablissement,adresse) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (nom, prenom, full_name, email, generate_password_hash(password), 'user', 'En attente', dob, sexe, profession, classe, filiere, etablissement, lien_etablissement, adresse)
        )
        db.commit()
    return jsonify({'ok': True, 'message': 'Compte créé. Votre profil est en attente de validation par l’administrateur.'})


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