"""
Digiscool – Serveur Flask  (version complète v3)
Tables : users, cours, commentaires, examens, soumissions_examen, notes_test
"""
from flask import (
    Flask, request, jsonify, session,
    render_template, redirect, url_for, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import os, sqlite3, json

# ── Config ──────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "digiscool-secret-2025")
DB_PATH       = os.path.join(app.root_path, "users.db")
UPLOAD_FOLDER = os.path.join(app.root_path, "uploads")
ALLOWED_VIDEO = {"mp4","webm","ogg","mov","avi"}
ALLOWED_DOC   = {"pdf","doc","docx","ppt","pptx","txt","png","jpg","jpeg"}
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

os.makedirs(os.path.join(UPLOAD_FOLDER,"videos"),    exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER,"cours"),     exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER,"exercices"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER,"examens"),   exist_ok=True)

def allowed(fn, s): return "." in fn and fn.rsplit(".",1)[1].lower() in s

# ── DB ───────────────────────────────────────────────────────────────────────
def get_db():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

def get_unread_notification_count(user_id):
    with get_db() as db:
        return db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND lu=0",(user_id,)).fetchone()[0]

def init_db():
    with get_db() as db:
        # users
        db.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student' CHECK(role IN('admin','student')),
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN('pending','approved','rejected')),
            photo TEXT DEFAULT '', adresse TEXT DEFAULT '',
            sexe TEXT DEFAULT '', classe TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        _migrate(db,"users",[("status","TEXT NOT NULL DEFAULT 'pending'"),
            ("photo","TEXT DEFAULT ''"),("adresse","TEXT DEFAULT ''"),
            ("sexe","TEXT DEFAULT ''"),("classe","TEXT DEFAULT ''")])
        db.execute("UPDATE users SET status='approved' WHERE role='admin'")

        # cours
        db.execute("""CREATE TABLE IF NOT EXISTS cours(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT NOT NULL, matiere TEXT DEFAULT '',
            description TEXT DEFAULT '',
            video_filename TEXT DEFAULT '', video_url TEXT DEFAULT '',
            has_cours INTEGER DEFAULT 0,
            cours_type TEXT DEFAULT 'fichier',
            cours_fichier TEXT DEFAULT '', cours_texte TEXT DEFAULT '',
            cours_qcm TEXT DEFAULT '[]',
            has_exercice INTEGER DEFAULT 0,
            exercice_type TEXT DEFAULT 'fichier',
            exercice_fichier TEXT DEFAULT '', exercice_texte TEXT DEFAULT '',
            exercice_qcm TEXT DEFAULT '[]',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        _migrate(db,"cours",[("matiere","TEXT DEFAULT ''"),
            ("description","TEXT DEFAULT ''"),("video_url","TEXT DEFAULT ''"),
            ("has_cours","INTEGER DEFAULT 0"),("cours_type","TEXT DEFAULT 'fichier'"),
            ("cours_fichier","TEXT DEFAULT ''"),("cours_texte","TEXT DEFAULT ''"),
            ("cours_qcm","TEXT DEFAULT '[]'"),("has_exercice","INTEGER DEFAULT 0"),
            ("exercice_type","TEXT DEFAULT 'fichier'"),
            ("exercice_fichier","TEXT DEFAULT ''"),("exercice_texte","TEXT DEFAULT ''"),
            ("exercice_qcm","TEXT DEFAULT '[]'"),("updated_at","DATETIME DEFAULT CURRENT_TIMESTAMP")])

        # commentaires
        db.execute("""CREATE TABLE IF NOT EXISTS commentaires(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cours_id INTEGER NOT NULL,
            user_id  INTEGER NOT NULL,
            texte    TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(cours_id) REFERENCES cours(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id)  REFERENCES users(id) ON DELETE CASCADE)""")

        # examens  (créés par admin)
        db.execute("""CREATE TABLE IF NOT EXISTS examens(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre    TEXT NOT NULL,
            matiere  TEXT DEFAULT '',
            type     TEXT DEFAULT 'examen' CHECK(type IN('examen','test','devoir')),
            duree_h  INTEGER DEFAULT 2,
            duree_m  INTEGER DEFAULT 0,
            contenu  TEXT DEFAULT '',
            fichier  TEXT DEFAULT '',
            qcm      TEXT DEFAULT '[]',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        _migrate(db,"examens",[("matiere","TEXT DEFAULT ''"),
            ("type","TEXT DEFAULT 'examen'"),
            ("duree_h","INTEGER DEFAULT 2"),("duree_m","INTEGER DEFAULT 0"),
            ("contenu","TEXT DEFAULT ''"),("fichier","TEXT DEFAULT ''"),
            ("qcm","TEXT DEFAULT '[]'")])

        # soumissions_examen  (réponses utilisateurs)
        db.execute("""CREATE TABLE IF NOT EXISTS soumissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            examen_id  INTEGER NOT NULL,
            user_id    INTEGER NOT NULL,
            contenu    TEXT DEFAULT '',
            fichier    TEXT DEFAULT '',
            reponses   TEXT DEFAULT '{}',
            note       REAL DEFAULT NULL,
            lu         INTEGER DEFAULT 0,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(examen_id) REFERENCES examens(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id)   REFERENCES users(id)   ON DELETE CASCADE)""")
        _migrate(db,"soumissions",[("note","REAL DEFAULT NULL"),
            ("lu","INTEGER DEFAULT 0"),("fichier","TEXT DEFAULT ''"),
            ("reponses","TEXT DEFAULT '{}'")])

        # notifications
        db.execute("""CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER NOT NULL,
            texte    TEXT NOT NULL,
            lu       INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)""")

    _create_default_admin()

def _migrate(db, table, cols):
    existing = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
    for col, defn in cols:
        if col not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")

def _create_default_admin():
    e=os.environ.get("ADMIN_EMAIL","admin@gmail.com")
    p=os.environ.get("ADMIN_PASSWORD","admin123")
    n=os.environ.get("ADMIN_NAME","Digiscool Admin")
    with get_db() as db:
        if not db.execute("SELECT id FROM users WHERE role='admin'").fetchone():
            db.execute("INSERT INTO users(name,email,password_hash,role,status) VALUES(?,?,?,?,?)",
                       (n,e,generate_password_hash(p),"admin","approved"))

def _row(r): d=dict(r); d.pop("password_hash",None); return d
def _rows(rs): return [_row(r) for r in rs]

def get_user_by_email(email):
    with get_db() as db: return db.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
def get_user_by_id(uid):
    with get_db() as db: return db.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
def list_users():
    with get_db() as db: return db.execute("SELECT * FROM users ORDER BY role DESC,name ASC").fetchall()
def get_cours_by_id(cid):
    with get_db() as db: return db.execute("SELECT * FROM cours WHERE id=?",(cid,)).fetchone()
def list_cours(q=None,sort="id"):
    if sort not in {"id","titre","matiere","created_at"}: sort="id"
    with get_db() as db:
        if q: return db.execute(f"SELECT * FROM cours WHERE titre LIKE ? OR matiere LIKE ? ORDER BY {sort} ASC",(f"%{q}%",f"%{q}%")).fetchall()
        return db.execute(f"SELECT * FROM cours ORDER BY {sort} ASC").fetchall()

# ── Auth decorators ─────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def w(*a,**kw):
        if "user_email" not in session: return redirect(url_for("index"))
        return f(*a,**kw)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a,**kw):
        if "user_email" not in session: return redirect(url_for("index"))
        u=get_user_by_email(session["user_email"])
        if not u or u["role"]!="admin": return redirect(url_for("dashboard"))
        return f(*a,**kw)
    return w

# ── Pages HTML ───────────────────────────────────────────────────────────────
@app.route("/")
def index(): return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    u=get_user_by_email(session["user_email"])
    if u and u["role"]=="admin":
        return redirect(url_for("dashboard_admin"))
    return redirect(url_for("dashboard_user"))

@app.route("/dashboard_user")
@login_required
def dashboard_user():
    u=get_user_by_email(session["user_email"])
    if u and u["role"]=="admin":
        return redirect(url_for("dashboard_admin"))
    return render_template("dashboard_user.html", user_name=u["name"], user_email=u["email"])

@app.route("/dashboard_admin")
@admin_required
def dashboard_admin():
    admin=get_user_by_email(session["user_email"])
    notif_count=get_unread_notification_count(admin["id"])
    return render_template("dashboard_admin.html",admin_name=admin["name"],admin_email=admin["email"],notif_count=notif_count)
"""
@app.route("/education")
@admin_required
def education_page(): return render_template("education.html")
"""
@app.route("/education")
@login_required
def education_redirect():
    u=get_user_by_email(session["user_email"])
    if u and u["role"]=="admin":
        return redirect(url_for("admin_education"))
    return redirect(url_for("user_education"))

@app.route("/admin/education")
@admin_required
def admin_education():
    admin=get_user_by_email(session["user_email"])
    notif_count=get_unread_notification_count(admin["id"])
    return render_template("education.html",admin_name=admin["name"],notif_count=notif_count)

@app.route("/test_admin")
@admin_required
def test_admin():
    admin=get_user_by_email(session["user_email"])
    with get_db() as db:
        notif_count=db.execute("SELECT COUNT(*) FROM notifications WHERE lu=0").fetchone()[0]
    return render_template("test_admin.html",admin_name=admin["name"],notif_count=notif_count)

# ── Admin Pages ──────────────────────────────────────────────────────────────
@app.route("/admin/test")
@admin_required
def admin_test():
    admin=get_user_by_email(session["user_email"])
    notif_count=get_unread_notification_count(admin["id"])
    return render_template("admin_test.html",admin_name=admin["name"],notif_count=notif_count)

@app.route("/admin/result")
@admin_required
def admin_result():
    admin=get_user_by_email(session["user_email"])
    notif_count=get_unread_notification_count(admin["id"])
    return render_template("admin_result.html",admin_name=admin["name"],notif_count=notif_count)

@app.route("/admin/user-work")
@admin_required
def admin_user_work():
    admin=get_user_by_email(session["user_email"])
    notif_count=get_unread_notification_count(admin["id"])
    return render_template("admin_user_work.html",admin_name=admin["name"],notif_count=notif_count)

@app.route("/admin/notifications")
@admin_required
def admin_notifications():
    admin=get_user_by_email(session["user_email"])
    with get_db() as db:
        rows=db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC",(admin["id"],)).fetchall()
        db.execute("UPDATE notifications SET lu=1 WHERE user_id=?",(admin["id"],))
    return render_template("admin_notifications.html",admin_name=admin["name"],notif_count=0,notifications=rows)

# ── User Pages ───────────────────────────────────────────────────────────────
@app.route("/user/education")
@login_required
def user_education():
    u=get_user_by_email(session["user_email"])
    with get_db() as db:
        notif_count=db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND lu=0",(u["id"],)).fetchone()[0]
    return render_template("education_user.html",user_name=u["name"],user_id=u["id"],notif_count=notif_count)

@app.route("/user/education/video")
@login_required
def user_education_video():
    u=get_user_by_email(session["user_email"])
    return render_template("user_education_video.html",user_name=u["name"])

@app.route("/user/exam")
@login_required
def user_exam():
    u=get_user_by_email(session["user_email"])
    return render_template("user_exam.html",user_name=u["name"])

@app.route("/user/notes")
@login_required
def user_notes():
    u=get_user_by_email(session["user_email"])
    return render_template("user_notes.html",user_name=u["name"])

@app.route("/api/logout")
def api_logout(): session.clear(); return redirect(url_for("index"))

@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename): return send_from_directory(UPLOAD_FOLDER,filename)

# ── API auth ─────────────────────────────────────────────────────────────────
@app.route("/api/register",methods=["POST"])
def api_register():
    d=request.get_json(silent=True) or {}
    # accept either `name` or `first_name`+`last_name`, and accept `contact` as fallback for email
    name=d.get("name","" ).strip() or ( (d.get("first_name","" ).strip() + " " + d.get("last_name","" ).strip()).strip() )
    email=(d.get("email","") or d.get("contact","" )).strip().lower()
    password=d.get("password","")
    if not name or not email or not password: return jsonify({"error":"Champs obligatoires."}),400
    if "@" not in email: return jsonify({"error":"E-mail invalide."}),400
    if len(password)<6: return jsonify({"error":"Mot de passe trop court."}),400
    if get_user_by_email(email): return jsonify({"error":"E-mail déjà utilisé."}),409
    with get_db() as db:
        db.execute("INSERT INTO users(name,email,password_hash,role,status,adresse,sexe,classe) VALUES(?,?,?,?,?,?,?,?)",
            (name,email,generate_password_hash(password),"student","pending",
             d.get("adresse",""),d.get("sexe",""),d.get("classe","")))
    return jsonify({"message":"Demande envoyée.","name":name}),201

@app.route("/api/login",methods=["POST"])
def api_login():
    d=request.get_json(silent=True) or {}
    identifier=d.get("email","" ).strip().lower()
    password=d.get("password","")
    if not identifier or not password: return jsonify({"error":"Champs obligatoires."}),400
    # allow login by email or by name (identifier without @)
    if "@" in identifier:
        u=get_user_by_email(identifier)
    else:
        with get_db() as db:
            u=db.execute("SELECT * FROM users WHERE lower(name)=? OR lower(email)=?",(identifier,identifier)).fetchone()
    if not u or not check_password_hash(u["password_hash"],password): return jsonify({"error":"Identifiants incorrects."}),401
    if u["status"]=="pending": return jsonify({"error":"Compte en attente d'approbation."}),403
    if u["status"]=="rejected": return jsonify({"error":"Compte rejeté."}),403
    # store canonical email from DB in session
    session["user_email"]=u["email"]
    return jsonify({"message":"Connexion réussie.","name":u["name"],"role":u["role"]}),200

# ── API users (admin) ────────────────────────────────────────────────────────
@app.route("/api/users",methods=["GET"])
@admin_required
def api_list_users(): return jsonify(_rows(list_users()))

@app.route("/api/users",methods=["POST"])
@admin_required
def api_create_user():
    d=request.get_json(silent=True) or {}
    name=d.get("name","").strip(); email=d.get("email","").strip().lower(); password=d.get("password","")
    role=d.get("role","student"); status=d.get("status","approved")
    if not name or not email or not password: return jsonify({"error":"Champs obligatoires."}),400
    if get_user_by_email(email): return jsonify({"error":"E-mail déjà utilisé."}),409
    with get_db() as db:
        cur=db.execute("INSERT INTO users(name,email,password_hash,role,status,photo,adresse,sexe,classe) VALUES(?,?,?,?,?,?,?,?,?)",
            (name,email,generate_password_hash(password),role,status,
             d.get("photo",""),d.get("adresse",""),d.get("sexe",""),d.get("classe","")))
    return jsonify(_row(get_user_by_id(cur.lastrowid))),201

@app.route("/api/users/<int:uid>",methods=["GET"])
@admin_required
def api_get_user(uid):
    u=get_user_by_id(uid)
    return (jsonify(_row(u)) if u else (jsonify({"error":"Introuvable."}),404))

@app.route("/api/users/<int:uid>",methods=["PUT"])
@admin_required
def api_update_user(uid):
    u=get_user_by_id(uid)
    if not u: return jsonify({"error":"Introuvable."}),404
    d=request.get_json(silent=True) or {}
    name=d.get("name",u["name"]).strip(); email=d.get("email",u["email"]).strip().lower()
    role=d.get("role",u["role"]); password=d.get("password","")
    with get_db() as db:
        if db.execute("SELECT id FROM users WHERE email=? AND id!=?",(email,uid)).fetchone():
            return jsonify({"error":"E-mail déjà utilisé."}),409
        if password:
            db.execute("UPDATE users SET name=?,email=?,role=?,adresse=?,sexe=?,classe=?,photo=?,password_hash=? WHERE id=?",
                (name,email,role,d.get("adresse",u["adresse"]),d.get("sexe",u["sexe"]),
                 d.get("classe",u["classe"]),d.get("photo",u["photo"]),generate_password_hash(password),uid))
        else:
            db.execute("UPDATE users SET name=?,email=?,role=?,adresse=?,sexe=?,classe=?,photo=? WHERE id=?",
                (name,email,role,d.get("adresse",u["adresse"]),d.get("sexe",u["sexe"]),
                 d.get("classe",u["classe"]),d.get("photo",u["photo"]),uid))
    return jsonify(_row(get_user_by_id(uid)))

@app.route("/api/users/<int:uid>",methods=["DELETE"])
@admin_required
def api_delete_user(uid):
    u=get_user_by_id(uid)
    if not u: return jsonify({"error":"Introuvable."}),404
    if u["role"]=="admin": return jsonify({"error":"Impossible de supprimer l'admin."}),403
    with get_db() as db: db.execute("DELETE FROM users WHERE id=?",(uid,))
    return jsonify({"message":"Supprimé."})

@app.route("/api/users/<int:uid>/approve",methods=["POST"])
@admin_required
def api_approve_user(uid):
    if not get_user_by_id(uid): return jsonify({"error":"Introuvable."}),404
    with get_db() as db: db.execute("UPDATE users SET status='approved' WHERE id=?",(uid,))
    return jsonify({"status":"approved"})

@app.route("/api/users/<int:uid>/reject",methods=["POST"])
@admin_required
def api_reject_user(uid):
    u=get_user_by_id(uid)
    if not u: return jsonify({"error":"Introuvable."}),404
    if u["role"]=="admin": return jsonify({"error":"Impossible."}),403
    with get_db() as db: db.execute("UPDATE users SET status='rejected' WHERE id=?",(uid,))
    return jsonify({"status":"rejected"})

# ── API cours ────────────────────────────────────────────────────────────────
@app.route("/api/cours",methods=["GET"])
@login_required
def api_list_cours():
    q=request.args.get("q",""); sort=request.args.get("sort","id")
    return jsonify([dict(r) for r in list_cours(q or None,sort)])

@app.route("/api/cours/<int:cid>",methods=["GET"])
@login_required
def api_get_cours(cid):
    c=get_cours_by_id(cid)
    return (jsonify(dict(c)) if c else (jsonify({"error":"Introuvable."}),404))

@app.route("/api/cours",methods=["POST"])
@admin_required
def api_create_cours():
    titre=request.form.get("titre","").strip(); matiere=request.form.get("matiere","").strip()
    if not titre: return jsonify({"error":"Titre obligatoire."}),400
    video_fn=cours_fn=exercice_fn=""
    vf=request.files.get("video_file")
    if vf and vf.filename and allowed(vf.filename,ALLOWED_VIDEO):
        fn=secure_filename(vf.filename); vf.save(os.path.join(UPLOAD_FOLDER,"videos",fn)); video_fn=fn
    cf=request.files.get("cours_fichier")
    if cf and cf.filename and allowed(cf.filename,ALLOWED_DOC):
        fn=secure_filename(cf.filename); cf.save(os.path.join(UPLOAD_FOLDER,"cours",fn)); cours_fn=fn
    ef=request.files.get("exercice_fichier")
    if ef and ef.filename and allowed(ef.filename,ALLOWED_DOC):
        fn=secure_filename(ef.filename); ef.save(os.path.join(UPLOAD_FOLDER,"exercices",fn)); exercice_fn=fn
    ct=request.form.get("cours_type","fichier"); et=request.form.get("exercice_type","fichier")
    ct_txt=request.form.get("cours_texte",""); et_txt=request.form.get("exercice_texte","")
    ct_qcm=request.form.get("cours_qcm","[]"); et_qcm=request.form.get("exercice_qcm","[]")
    has_c=1 if (cours_fn or ct_txt or ct_qcm!="[]") else 0
    has_e=1 if (exercice_fn or et_txt or et_qcm!="[]") else 0
    with get_db() as db:
        cur=db.execute("""INSERT INTO cours(titre,matiere,description,video_filename,video_url,
            has_cours,cours_type,cours_fichier,cours_texte,cours_qcm,
            has_exercice,exercice_type,exercice_fichier,exercice_texte,exercice_qcm)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (titre,matiere,request.form.get("description",""),video_fn,
             request.form.get("video_url",""),has_c,ct,cours_fn,ct_txt,ct_qcm,
             has_e,et,exercice_fn,et_txt,et_qcm))
    return jsonify(dict(get_cours_by_id(cur.lastrowid))),201

@app.route("/api/cours/<int:cid>",methods=["PUT"])
@admin_required
def api_update_cours(cid):
    c=get_cours_by_id(cid)
    if not c: return jsonify({"error":"Introuvable."}),404
    video_fn=c["video_filename"]; cours_fn=c["cours_fichier"]; exercice_fn=c["exercice_fichier"]
    vf=request.files.get("video_file")
    if vf and vf.filename and allowed(vf.filename,ALLOWED_VIDEO):
        fn=secure_filename(vf.filename); vf.save(os.path.join(UPLOAD_FOLDER,"videos",fn)); video_fn=fn
    cf=request.files.get("cours_fichier")
    if cf and cf.filename and allowed(cf.filename,ALLOWED_DOC):
        fn=secure_filename(cf.filename); cf.save(os.path.join(UPLOAD_FOLDER,"cours",fn)); cours_fn=fn
    ef=request.files.get("exercice_fichier")
    if ef and ef.filename and allowed(ef.filename,ALLOWED_DOC):
        fn=secure_filename(ef.filename); ef.save(os.path.join(UPLOAD_FOLDER,"exercices",fn)); exercice_fn=fn
    titre=request.form.get("titre",c["titre"]).strip()
    matiere=request.form.get("matiere",c["matiere"])
    description=request.form.get("description",c["description"])
    video_url=request.form.get("video_url",c["video_url"])
    ct=request.form.get("cours_type",c["cours_type"]); et=request.form.get("exercice_type",c["exercice_type"])
    ct_txt=request.form.get("cours_texte",c["cours_texte"]); et_txt=request.form.get("exercice_texte",c["exercice_texte"])
    ct_qcm=request.form.get("cours_qcm",c["cours_qcm"]); et_qcm=request.form.get("exercice_qcm",c["exercice_qcm"])
    has_c=1 if (cours_fn or ct_txt or ct_qcm!="[]") else 0
    has_e=1 if (exercice_fn or et_txt or et_qcm!="[]") else 0
    with get_db() as db:
        db.execute("""UPDATE cours SET titre=?,matiere=?,description=?,video_filename=?,video_url=?,
            has_cours=?,cours_type=?,cours_fichier=?,cours_texte=?,cours_qcm=?,
            has_exercice=?,exercice_type=?,exercice_fichier=?,exercice_texte=?,exercice_qcm=?,
            updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (titre,matiere,description,video_fn,video_url,has_c,ct,cours_fn,ct_txt,ct_qcm,
             has_e,et,exercice_fn,et_txt,et_qcm,cid))
    return jsonify(dict(get_cours_by_id(cid)))

@app.route("/api/cours/<int:cid>",methods=["DELETE"])
@admin_required
def api_delete_cours(cid):
    c=get_cours_by_id(cid)
    if not c: return jsonify({"error":"Introuvable."}),404
    for sub,fn in [("videos",c["video_filename"]),("cours",c["cours_fichier"]),("exercices",c["exercice_fichier"])]:
        if fn:
            p=os.path.join(UPLOAD_FOLDER,sub,fn)
            if os.path.exists(p): os.remove(p)
    with get_db() as db: db.execute("DELETE FROM cours WHERE id=?",(cid,))
    return jsonify({"message":"Cours supprimé."})

# ── API commentaires ─────────────────────────────────────────────────────────
@app.route("/api/cours/<int:cid>/commentaires",methods=["GET"])
@login_required
def api_get_commentaires(cid):
    with get_db() as db:
        rows=db.execute("""SELECT c.*,u.name as user_name,u.photo as user_photo
            FROM commentaires c JOIN users u ON c.user_id=u.id
            WHERE c.cours_id=? ORDER BY c.created_at ASC""",(cid,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/cours/<int:cid>/commentaires",methods=["POST"])
@login_required
def api_add_commentaire(cid):
    u=get_user_by_email(session["user_email"])
    d=request.get_json(silent=True) or {}
    texte=(d.get("texte") or "").strip()
    if not texte: return jsonify({"error":"Commentaire vide."}),400
    with get_db() as db:
        cur=db.execute("INSERT INTO commentaires(cours_id,user_id,texte) VALUES(?,?,?)",(cid,u["id"],texte))
        cours=db.execute("SELECT titre FROM cours WHERE id=?",(cid,)).fetchone()
        if cours:
            notif_text=f"Nouveau commentaire de {u['name']} sur « {cours['titre']} »"
        else:
            notif_text=f"Nouveau commentaire de {u['name']}"
        db.execute("INSERT INTO notifications(user_id,texte) SELECT id,? FROM users WHERE role='admin'",(notif_text,))
        row=db.execute("SELECT c.*,u.name as user_name FROM commentaires c JOIN users u ON c.user_id=u.id WHERE c.id=?",(cur.lastrowid,)).fetchone()
    return jsonify(dict(row)),201

@app.route("/api/commentaires/<int:cid>",methods=["DELETE"])
@admin_required
def api_delete_commentaire(cid):
    with get_db() as db: db.execute("DELETE FROM commentaires WHERE id=?",(cid,))
    return jsonify({"message":"Supprimé."})

# ── API examens (admin CRUD) ─────────────────────────────────────────────────
@app.route("/api/examens",methods=["GET"])
@login_required
def api_list_examens():
    t=request.args.get("type","")
    with get_db() as db:
        if t: rows=db.execute("SELECT * FROM examens WHERE type=? ORDER BY id DESC",(t,)).fetchall()
        else: rows=db.execute("SELECT * FROM examens ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/examens",methods=["POST"])
@admin_required
def api_create_examen():
    titre=request.form.get("titre","").strip()
    if not titre: return jsonify({"error":"Titre obligatoire."}),400
    fichier=""
    f=request.files.get("fichier")
    if f and f.filename and allowed(f.filename,ALLOWED_DOC):
        fn=secure_filename(f.filename); f.save(os.path.join(UPLOAD_FOLDER,"examens",fn)); fichier=fn
    with get_db() as db:
        cur=db.execute("INSERT INTO examens(titre,matiere,type,duree_h,duree_m,contenu,fichier,qcm) VALUES(?,?,?,?,?,?,?,?)",
            (titre,request.form.get("matiere",""),request.form.get("type","examen"),
             int(request.form.get("duree_h",2)),int(request.form.get("duree_m",0)),
             request.form.get("contenu",""),fichier,request.form.get("qcm","[]")))
        row=db.execute("SELECT * FROM examens WHERE id=?",(cur.lastrowid,)).fetchone()
    return jsonify(dict(row)),201

@app.route("/api/examens/<int:eid>",methods=["GET"])
@login_required
def api_get_examen(eid):
    with get_db() as db: r=db.execute("SELECT * FROM examens WHERE id=?",(eid,)).fetchone()
    return (jsonify(dict(r)) if r else (jsonify({"error":"Introuvable."}),404))

@app.route("/api/examens/<int:eid>",methods=["PUT"])
@admin_required
def api_update_examen(eid):
    with get_db() as db:
        e=db.execute("SELECT * FROM examens WHERE id=?",(eid,)).fetchone()
        if not e: return jsonify({"error":"Introuvable."}),404
        fichier=e["fichier"]
        f=request.files.get("fichier")
        if f and f.filename and allowed(f.filename,ALLOWED_DOC):
            fn=secure_filename(f.filename); f.save(os.path.join(UPLOAD_FOLDER,"examens",fn)); fichier=fn
        db.execute("UPDATE examens SET titre=?,matiere=?,type=?,duree_h=?,duree_m=?,contenu=?,fichier=?,qcm=? WHERE id=?",
            (request.form.get("titre",e["titre"]),request.form.get("matiere",e["matiere"]),
             request.form.get("type",e["type"]),int(request.form.get("duree_h",e["duree_h"])),
             int(request.form.get("duree_m",e["duree_m"])),request.form.get("contenu",e["contenu"]),
             fichier,request.form.get("qcm",e["qcm"]),eid))
        row=db.execute("SELECT * FROM examens WHERE id=?",(eid,)).fetchone()
    return jsonify(dict(row))

@app.route("/api/examens/<int:eid>",methods=["DELETE"])
@admin_required
def api_delete_examen(eid):
    with get_db() as db:
        e=db.execute("SELECT * FROM examens WHERE id=?",(eid,)).fetchone()
        if not e: return jsonify({"error":"Introuvable."}),404
        if e["fichier"]:
            p=os.path.join(UPLOAD_FOLDER,"examens",e["fichier"])
            if os.path.exists(p): os.remove(p)
        db.execute("DELETE FROM examens WHERE id=?",(eid,))
    return jsonify({"message":"Supprimé."})

# ── API soumissions ──────────────────────────────────────────────────────────
@app.route("/api/examens/<int:eid>/soumettre",methods=["POST"])
@login_required
def api_soumettre(eid):
    u=get_user_by_email(session["user_email"])
    fichier=""
    f=request.files.get("fichier")
    if f and f.filename and allowed(f.filename,ALLOWED_DOC):
        fn=secure_filename(f.filename); f.save(os.path.join(UPLOAD_FOLDER,"examens",fn)); fichier=fn
    contenu=request.form.get("contenu","")
    reponses=request.form.get("reponses","{}")
    with get_db() as db:
        cur=db.execute("INSERT INTO soumissions(examen_id,user_id,contenu,fichier,reponses) VALUES(?,?,?,?,?)",
            (eid,u["id"],contenu,fichier,reponses))
        # notif admin
        db.execute("INSERT INTO notifications(user_id,texte) SELECT id,'Nouvelle soumission de '||? FROM users WHERE role='admin'",(u["name"],))
        row=db.execute("SELECT * FROM soumissions WHERE id=?",(cur.lastrowid,)).fetchone()
    return jsonify(dict(row)),201

@app.route("/api/soumissions",methods=["GET"])
@admin_required
def api_list_soumissions():
    eid=request.args.get("examen_id",""); uid=request.args.get("user_id","")
    with get_db() as db:
        q="SELECT s.*,u.name as user_name,u.photo as user_photo,e.titre as examen_titre,e.type as examen_type FROM soumissions s JOIN users u ON s.user_id=u.id JOIN examens e ON s.examen_id=e.id"
        params=[]
        if eid and uid: q+=" WHERE s.examen_id=? AND s.user_id=?"; params=[eid,uid]
        elif eid: q+=" WHERE s.examen_id=?"; params=[eid]
        elif uid: q+=" WHERE s.user_id=?"; params=[uid]
        q+=" ORDER BY s.submitted_at DESC"
        rows=db.execute(q,params).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/soumissions/<int:sid>",methods=["GET"])
@login_required
def api_get_soumission(sid):
    with get_db() as db:
        r=db.execute("""SELECT s.*,u.name as user_name,u.photo as user_photo,
            e.titre as examen_titre,e.type as examen_type,e.duree_h,e.duree_m
            FROM soumissions s JOIN users u ON s.user_id=u.id JOIN examens e ON s.examen_id=e.id
            WHERE s.id=?""",(sid,)).fetchone()
    return (jsonify(dict(r)) if r else (jsonify({"error":"Introuvable."}),404))

@app.route("/api/soumissions/<int:sid>/noter",methods=["POST"])
@admin_required
def api_noter(sid):
    d=request.get_json(silent=True) or {}
    note=d.get("note")
    with get_db() as db:
        s=db.execute("SELECT * FROM soumissions WHERE id=?",(sid,)).fetchone()
        if not s: return jsonify({"error":"Introuvable."}),404
        db.execute("UPDATE soumissions SET note=?,lu=1 WHERE id=?",(note,sid))
        if note is not None:
            e=db.execute("SELECT titre FROM examens WHERE id=?",(s["examen_id"],)).fetchone()
            db.execute("INSERT INTO notifications(user_id,texte) VALUES(?,?)",
                (s["user_id"],f"Votre note pour « {e['titre']} » : {note}/20"))
    return jsonify({"message":"Note enregistrée.","note":note})

@app.route("/api/soumissions/<int:sid>",methods=["DELETE"])
@admin_required
def api_delete_soumission(sid):
    with get_db() as db:
        s=db.execute("SELECT * FROM soumissions WHERE id=?",(sid,)).fetchone()
        if not s: return jsonify({"error":"Introuvable."}),404
        if s["fichier"]:
            p=os.path.join(UPLOAD_FOLDER,"examens",s["fichier"])
            if os.path.exists(p): os.remove(p)
        db.execute("DELETE FROM soumissions WHERE id=?",(sid,))
    return jsonify({"message":"Supprimé."})

# ── API notifications ────────────────────────────────────────────────────────
@app.route("/api/notifications",methods=["GET"])
@login_required
def api_notifications():
    u=get_user_by_email(session["user_email"])
    with get_db() as db:
        rows=db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20",(u["id"],)).fetchall()
        db.execute("UPDATE notifications SET lu=1 WHERE user_id=?",(u["id"],))
    return jsonify([dict(r) for r in rows])

@app.route("/api/notifications/count",methods=["GET"])
@login_required
def api_notif_count():
    u=get_user_by_email(session["user_email"])
    with get_db() as db:
        n=db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND lu=0",(u["id"],)).fetchone()[0]
    return jsonify({"count":n})

# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("Digiscool sur http://localhost:5000")
    app.run(debug=True,host="0.0.0.0",port=5000)