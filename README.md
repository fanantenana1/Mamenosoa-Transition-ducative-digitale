# Digiscool – Application Web Flask

## Structure du projet

```
digiscool/
├── app.py                  # Application Flask principale
├── requirements.txt        # Dépendances Python
├── instance/
│   └── digiscool.db        # Base de données SQLite (créée automatiquement)
├── uploads/
│   ├── videos/             # Vidéos uploadées par l'admin
│   └── documents/          # Documents cours/exercices/examens
├── static/
│   ├── css/
│   │   └── main.css        # Styles CSS principaux
│   └── images/             # Logo, décorations (molecule.png, points.png, etc.)
└── templates/
    ├── base.html
    ├── index.html           # Page d'accueil (login/register)
    ├── footer.html
    ├── user/
    │   ├── dashboard.html   # Liste éducation utilisateur
    │   ├── education_view.html
    │   ├── examens.html
    │   ├── examen_view.html
    │   └── notifications.html
    └── admin/
        ├── dashboard.html
        ├── education.html
        ├── education_view.html
        ├── utilisateurs.html
        ├── utilisateur_detail.html
        ├── test.html
        └── resultats.html
```

## Installation & Lancement

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Lancer l'application
python app.py
```

L'application sera disponible sur: http://localhost:5000

## Compte admin par défaut
- Email: admin@digiscool.mg
- Mot de passe: admin123

## Fonctionnalités

### Admin
- Dashboard avec statistiques
- Gestion des contenus éducatifs (vidéos, documents cours/exercices)
- Envoi d'examens aux utilisateurs
- Consultation des résultats / soumissions
- Attribution de notes avec notification automatique

### Utilisateur
- Accès à la liste des contenus éducatifs
- Lecture vidéo + téléchargement de documents
- Dépôt de commentaires sur les vidéos
- Participation aux examens (soumission de fichier)
- Notifications

## Images décoratives à placer dans static/images/
- Logo.png
- molecule.png
- points.png
- molecule_centre.png
- molecule_bas.png
- bockin.png
