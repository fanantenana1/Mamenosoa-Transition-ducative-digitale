from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3, os, datetime, json

app = Flask(__name__)
app.secret_key = 'digiscool_secret_2025'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'instance', 'digiscool.db')
UPLOAD_VIDEOS = os.path.join(BASE_DIR, 'uploads', 'videos')
UPLOAD_DOCS   = os.path.join(BASE_DIR, 'uploads', 'documents')

ALLOWED_VIDEO = {'mp4', 'webm', 'ogg', 'mkv'}
ALLOWED_DOC   = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'zip'}

os.makedirs(UPLOAD_VIDEOS, exist_ok=True)
os.makedirs(UPLOAD_DOCS,   exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

# ── DATABASE ────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            email    TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role     TEXT NOT NULL DEFAULT 'user',
            created  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS education (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            titre       TEXT NOT NULL,
            description TEXT,
            type        TEXT NOT NULL,
            video_path  TEXT,
            doc_cours   TEXT,
            doc_exercice TEXT,
            created     TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS examens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            titre       TEXT NOT NULL,
            duree       TEXT DEFAULT '2:00',
            fichier     TEXT,
            created     TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS soumissions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            examen_id   INTEGER,
            fichier     TEXT,
            date_soumis TEXT DEFAULT (datetime('now')),
            note        TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(examen_id) REFERENCES examens(id)
        );
        CREATE TABLE IF NOT EXISTS commentaires (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            education_id INTEGER,
            texte      TEXT NOT NULL,
            created    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(education_id) REFERENCES education(id)
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER,
            message  TEXT NOT NULL,
            lu       INTEGER DEFAULT 0,
            created  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    ''')
    # Seed admin
    existing = c.execute("SELECT id FROM users WHERE email='admin@digiscool.mg'").fetchone()
    if not existing:
        c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                  ('Admin','admin@digiscool.mg', generate_password_hash('admin123'), 'admin'))
    conn.commit()
    conn.close()

init_db()

# ── HELPERS ─────────────────────────────────────────────────────────────────
def allowed_video(f): return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_VIDEO
def allowed_doc(f):   return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_DOC

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def notif_count():
    if 'user_id' not in session: return 0
    db = get_db()
    n = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND lu=0",
                   (session['user_id'],)).fetchone()[0]
    db.close()
    return n

# ── PUBLIC ROUTES ────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard') if session.get('role')=='admin' else url_for('user_dashboard'))
    return render_template('index.html')

# ── AUTH API ─────────────────────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.get_json()
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE email=?", (d['email'],)).fetchone()
    db.close()
    if u and check_password_hash(u['password'], d['password']):
        session['user_id'] = u['id']
        session['name']    = u['name']
        session['role']    = u['role']
        return jsonify({'name': u['name'], 'role': u['role']})
    return jsonify({'error': 'Identifiants incorrects.'}), 401

@app.route('/api/register', methods=['POST'])
def api_register():
    d = request.get_json()
    db = get_db()
    try:
        db.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                   (d['name'], d['email'], generate_password_hash(d['password'])))
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({'error': 'Email déjà utilisé.'}), 400
    db.close()
    return jsonify({'ok': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ── USER DASHBOARD ───────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def user_dashboard():
    db = get_db()
    educations = db.execute("SELECT * FROM education ORDER BY created DESC").fetchall()
    db.close()
    return render_template('user/dashboard.html', educations=educations, notif=notif_count())

@app.route('/education/<int:eid>')
@login_required
def user_education_view(eid):
    db = get_db()
    edu = db.execute("SELECT * FROM education WHERE id=?", (eid,)).fetchone()
    comms = db.execute(
        "SELECT c.*, u.name FROM commentaires c JOIN users u ON c.user_id=u.id WHERE c.education_id=? ORDER BY c.created DESC",
        (eid,)).fetchall()
    db.close()
    return render_template('user/education_view.html', edu=edu, comms=comms, notif=notif_count())

@app.route('/api/commentaire', methods=['POST'])
@login_required
def api_commentaire():
    d = request.get_json()
    db = get_db()
    db.execute("INSERT INTO commentaires(user_id,education_id,texte) VALUES(?,?,?)",
               (session['user_id'], d['education_id'], d['texte']))
    db.commit()
    db.close()
    return jsonify({'ok': True})

@app.route('/examens')
@login_required
def user_examens():
    db = get_db()
    examens = db.execute("SELECT * FROM examens ORDER BY created DESC").fetchall()
    db.close()
    return render_template('user/examens.html', examens=examens, notif=notif_count())

@app.route('/examen/<int:eid>')
@login_required
def user_examen_view(eid):
    db = get_db()
    ex = db.execute("SELECT * FROM examens WHERE id=?", (eid,)).fetchone()
    db.close()
    return render_template('user/examen_view.html', ex=ex, notif=notif_count())

@app.route('/api/soumettre', methods=['POST'])
@login_required
def api_soumettre():
    examen_id = request.form.get('examen_id')
    fichier = request.files.get('fichier')
    fname = None
    if fichier and allowed_doc(fichier.filename):
        fname = secure_filename(f"soum_{session['user_id']}_{examen_id}_{fichier.filename}")
        fichier.save(os.path.join(UPLOAD_DOCS, fname))
    db = get_db()
    db.execute("INSERT INTO soumissions(user_id,examen_id,fichier) VALUES(?,?,?)",
               (session['user_id'], examen_id, fname))
    db.commit()
    db.close()
    return jsonify({'ok': True})

@app.route('/notifications')
@login_required
def user_notifications():
    db = get_db()
    notifs = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created DESC",
                        (session['user_id'],)).fetchall()
    db.execute("UPDATE notifications SET lu=1 WHERE user_id=?", (session['user_id'],))
    db.commit()
    db.close()
    return render_template('user/notifications.html', notifs=notifs, notif=0)

# ── ADMIN DASHBOARD ──────────────────────────────────────────────────────────
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    db = get_db()
    users = db.execute("SELECT * FROM users WHERE role='user' ORDER BY created DESC").fetchall()
    educations = db.execute("SELECT * FROM education ORDER BY created DESC").fetchall()
    examens = db.execute("SELECT * FROM examens ORDER BY created DESC").fetchall()
    db.close()
    return render_template('admin/dashboard.html', users=users, educations=educations,
                           examens=examens, notif=notif_count())

# ── ADMIN EDUCATION ──────────────────────────────────────────────────────────
@app.route('/admin/education')
@login_required
@admin_required
def admin_education():
    db = get_db()
    educations = db.execute("SELECT * FROM education ORDER BY created DESC").fetchall()
    db.close()
    return render_template('admin/education.html', educations=educations, notif=notif_count())

@app.route('/admin/education/add', methods=['POST'])
@login_required
@admin_required
def admin_education_add():
    titre       = request.form.get('titre')
    description = request.form.get('description')
    type_       = request.form.get('type')
    video_file  = request.files.get('video')
    doc_cours   = request.files.get('doc_cours')
    doc_exo     = request.files.get('doc_exercice')

    vpath = dpath = epath = None
    if video_file and allowed_video(video_file.filename):
        vpath = secure_filename(video_file.filename)
        video_file.save(os.path.join(UPLOAD_VIDEOS, vpath))
    if doc_cours and allowed_doc(doc_cours.filename):
        dpath = secure_filename(doc_cours.filename)
        doc_cours.save(os.path.join(UPLOAD_DOCS, dpath))
    if doc_exo and allowed_doc(doc_exo.filename):
        epath = secure_filename(doc_exo.filename)
        doc_exo.save(os.path.join(UPLOAD_DOCS, epath))

    db = get_db()
    db.execute("INSERT INTO education(titre,description,type,video_path,doc_cours,doc_exercice) VALUES(?,?,?,?,?,?)",
               (titre, description, type_, vpath, dpath, epath))
    db.commit()
    db.close()
    return redirect(url_for('admin_education'))

@app.route('/admin/education/<int:eid>/edit', methods=['POST'])
@login_required
@admin_required
def admin_education_edit(eid):
    titre       = request.form.get('titre')
    description = request.form.get('description')
    type_       = request.form.get('type')
    db = get_db()
    db.execute("UPDATE education SET titre=?,description=?,type=? WHERE id=?",
               (titre, description, type_, eid))
    db.commit()
    db.close()
    return redirect(url_for('admin_education'))

@app.route('/admin/education/<int:eid>/delete', methods=['POST'])
@login_required
@admin_required
def admin_education_delete(eid):
    db = get_db()
    db.execute("DELETE FROM education WHERE id=?", (eid,))
    db.commit()
    db.close()
    return redirect(url_for('admin_education'))

@app.route('/admin/education/<int:eid>')
@login_required
@admin_required
def admin_education_view(eid):
    db = get_db()
    edu = db.execute("SELECT * FROM education WHERE id=?", (eid,)).fetchone()
    db.close()
    return render_template('admin/education_view.html', edu=edu, notif=notif_count())

# ── ADMIN UTILISATEURS ───────────────────────────────────────────────────────
@app.route('/admin/utilisateurs')
@login_required
@admin_required
def admin_utilisateurs():
    db = get_db()
    users = db.execute("SELECT * FROM users WHERE role='user' ORDER BY created DESC").fetchall()
    db.close()
    return render_template('admin/utilisateurs.html', users=users, notif=notif_count())

@app.route('/admin/utilisateur/<int:uid>')
@login_required
@admin_required
def admin_utilisateur_detail(uid):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    soumissions = db.execute(
        "SELECT s.*, e.titre FROM soumissions s JOIN examens e ON s.examen_id=e.id WHERE s.user_id=? ORDER BY s.date_soumis DESC",
        (uid,)).fetchall()
    db.close()
    return render_template('admin/utilisateur_detail.html', user=user, soumissions=soumissions, notif=notif_count())

@app.route('/admin/utilisateur/<int:uid>/note', methods=['POST'])
@login_required
@admin_required
def admin_note(uid):
    soum_id = request.form.get('soum_id')
    note    = request.form.get('note')
    db = get_db()
    db.execute("UPDATE soumissions SET note=? WHERE id=?", (note, soum_id))
    # notifier l'utilisateur
    db.execute("INSERT INTO notifications(user_id,message) VALUES(?,?)",
               (uid, f"Votre travail a été noté : {note}/20"))
    db.commit()
    db.close()
    return redirect(url_for('admin_utilisateur_detail', uid=uid))

# ── ADMIN EXAMENS / TEST ─────────────────────────────────────────────────────
@app.route('/admin/test')
@login_required
@admin_required
def admin_test():
    db = get_db()
    types = db.execute("SELECT DISTINCT type FROM education").fetchall()
    db.close()
    return render_template('admin/test.html', types=types, notif=notif_count())

@app.route('/admin/test/envoyer', methods=['POST'])
@login_required
@admin_required
def admin_test_envoyer():
    type_   = request.form.get('type')
    titre   = request.form.get('titre', 'Examen')
    duree   = request.form.get('duree', '2:00')
    fichier = request.files.get('fichier')
    fname = None
    if fichier and allowed_doc(fichier.filename):
        fname = secure_filename(fichier.filename)
        fichier.save(os.path.join(UPLOAD_DOCS, fname))
    db = get_db()
    db.execute("INSERT INTO examens(titre,duree,fichier) VALUES(?,?,?)", (titre, duree, fname))
    examen_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    # Notifier tous les utilisateurs
    users = db.execute("SELECT id FROM users WHERE role='user'").fetchall()
    for u in users:
        db.execute("INSERT INTO notifications(user_id,message) VALUES(?,?)",
                   (u['id'], f"Nouvel examen disponible : {titre}"))
    db.commit()
    db.close()
    return redirect(url_for('admin_test'))

@app.route('/admin/resultats')
@login_required
@admin_required
def admin_resultats():
    db = get_db()
    soumissions = db.execute(
        "SELECT s.*, u.name as uname, e.titre as etitle FROM soumissions s "
        "JOIN users u ON s.user_id=u.id JOIN examens e ON s.examen_id=e.id "
        "ORDER BY s.date_soumis DESC").fetchall()
    db.close()
    return render_template('admin/resultats.html', soumissions=soumissions, notif=notif_count())

@app.route('/admin/resultats/delete', methods=['POST'])
@login_required
@admin_required
def admin_resultats_delete():
    ids = request.form.getlist('ids[]')
    db = get_db()
    for sid in ids:
        db.execute("DELETE FROM soumissions WHERE id=?", (sid,))
    db.commit()
    db.close()
    return jsonify({'ok': True})

# ── STATIC FILES (uploads) ───────────────────────────────────────────────────
@app.route('/uploads/videos/<path:fname>')
def serve_video(fname):
    return send_from_directory(UPLOAD_VIDEOS, fname)

@app.route('/uploads/documents/<path:fname>')
def serve_doc(fname):
    return send_from_directory(UPLOAD_DOCS, fname)

if __name__ == '__main__':
    app.run(debug=True)
