from flask import Flask, render_template, jsonify, request, redirect, url_for, abort, session, flash, send_file
import json
import os
from datetime import datetime, timezone
import re
from unicodedata import normalize
import bcrypt
import csv
from flask_cors import CORS
from werkzeug.utils import secure_filename


app = Flask(__name__)
CORS(app)

# --- Helper functions ---

LOGS_FILE = "data/logs.json"
COMMENTS_FILE = "data/comments.json"
CONTACTS_FILE = "data/contacts.json"

def log_action(action, details=None):
    """Ajoute une action au journal des activités en incluant l'utilisateur connecté."""
    user = session.get("username", "anonyme")  # Récupère l'utilisateur connecté ou "anonyme"
    try:
        # Charger les logs existants
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, "r") as f:
                logs = json.load(f)
        else:
            logs = []

        # Ajouter le nouveau log
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": user,  # Toujours une chaîne
            "action": str(action),  # Assurez-vous que l'action est une chaîne
            "details": details if isinstance(details, dict) else {}  # Toujours un objet JSON
        }
        logs.append(log_entry)

        # Sauvegarder les logs
        with open(LOGS_FILE, "w") as f:
            json.dump(logs, f, indent=4)
    except Exception as e:
        print(f"Erreur lors de l'enregistrement du log : {e}")

def slugify(text):
    """
    Convertit une chaîne de caractères en un slug URL-friendly.
    Exemples :
    - "Produit Test" devient "produit-test"
    - "Élément spécial !" devient "element-special"
    """
    text = normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')  # Supprime les accents
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()  # Supprime les caractères spéciaux
    return re.sub(r'[\s]+', '-', text)  # Remplace les espaces par des tirets

def load_products(file_path='data/products.json'):
    """
    Charge les données des produits depuis products.json, génère les slugs si absents, et sauvegarde.
    """
    if not os.path.exists(file_path):
        print(f"Le fichier {file_path} n'existe pas.")
        return []

    try:
        # Charger les produits depuis le fichier JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            products = json.load(f)

        # Vérifier et générer les slugs si nécessaire
        slugs_updated = False
        for product in products:
            # Générer le slug uniquement s'il est absent ou vide
            if "slug" not in product or not product["slug"]:
                if "name" in product:
                    product["slug"] = slugify(product["name"])
                    slugs_updated = True
                else:
                    print(f"Produit sans nom détecté : {product}")

        # Sauvegarder les slugs générés dans le fichier JSON si nécessaire
        if slugs_updated:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(products, f, indent=4, ensure_ascii=False)
            print(f"Les slugs manquants ont été générés et sauvegardés dans {file_path}.")

        return products

    except Exception as e:
        print(f"Erreur lors du chargement ou de la sauvegarde des produits : {e}")
        return []

def load_comments():
    """
    Charge les données des commentaires depuis comments.json
    """
    if not os.path.exists('data/comments.json'):
        return {}
    with open('data/comments.json', 'r', encoding="utf-8") as f:
        return json.load(f)

def save_comments(comments):
    """
    Sauvegarde les données des commentaires dans comments.json
    """
    with open('data/comments.json', 'w', encoding="utf-8") as f:
        json.dump(comments, f, indent=4, ensure_ascii=False)

def sort_comments(comments):
    """
    Trie les commentaires par note (du meilleur au moins bon) et par date (plus récent en premier si égalité)
    """
    return sorted(comments, key=lambda c: (-c["rating"], c["date"]), reverse=False)

def save_message(data):
    """
    Sauvegarde un message dans contacts.json
    """
    file_path = 'data/contacts.json'
    try:
        # Charger les messages existants
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                messages = json.load(f)
        else:
            messages = []

        # Ajouter le nouveau message
        messages.append(data)

        # Écrire dans le fichier JSON
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(messages, f, indent=4, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde : {e}")
        return False

# --- Routes produits ---
PRODUIT_CACHE = load_products()
@app.route('/')
def home():
    """
    Page d'accueil : affiche les produits vedettes
    """
    produits = load_products()
    produits_vedette = [p for p in produits if p.get("featured")]
    return render_template('home.html', produits_vedette=produits_vedette)

@app.route('/produits')
def produits():
    """
    Page listant tous les produits
    """
    produits = load_products()
    return render_template('produits.html', produits=produits)

@app.route('/produit/<slug>')
def product_detail(slug):
    """
    Page détaillée d'un produit (utilise le slug dans l'URL)
    """
    produits = load_products()

    # Trouver le produit correspondant au slug
    produit = next((p for p in produits if slugify(p.get("name")) == slug), None)
    if not produit:
        return render_template('404.html'), 404

    # Charger les commentaires pour ce produit
    comments = load_comments()
    produit_comments = comments.get(str(produit.get("id")), [])

    # Tri des commentaires
    produit_comments = sort_comments(produit_comments)

    # Calculer la note moyenne
    if produit_comments:
        produit["rating"] = round(sum(c["rating"] for c in produit_comments) / len(produit_comments), 2)
    else:
        produit["rating"] = None

    return render_template('product.html', produit=produit, comments=produit_comments)

@app.route('/produit/<slug>/comment', methods=['POST'])
def add_comment(slug):
    """
    Route pour ajouter un commentaire à un produit spécifique
    """
    produits = load_products()

    # Trouver le produit correspondant au slug
    produit = next((p for p in produits if slugify(p.get("name")) == slug), None)
    if not produit:
        abort(404, "Produit introuvable.")

    product_id = produit.get("id")
    comments = load_comments()
    new_comment = request.form.to_dict()

    # Vérifier que les champs nécessaires sont présents
    if not new_comment.get("comment") or not new_comment.get("rating"):
        abort(400, "Le commentaire et la note sont obligatoires.")

    # Créer un id unique pour le commentaire
    comment_id = max([c['id'] for c in comments.get(str(product_id), [])] or [0]) + 1
    new_comment["id"] = comment_id
    new_comment["date"] = datetime.now(timezone.utc).isoformat()
    new_comment["rating"] = int(new_comment["rating"])  # Convertir en entier

    # Ajouter le commentaire
    if str(product_id) not in comments:
        comments[str(product_id)] = []
    comments[str(product_id)].append(new_comment)

    # Sauvegarder dans le fichier JSON
    save_comments(comments)

    # Rediriger vers la page du produit après soumission
    return redirect(url_for('product_detail', slug=slug))

# --- Routes API ---
@app.route('/api/produits')
def api_produits():
    """
    API pour récupérer tous les produits
    """
    produits = load_products()
    return jsonify(produits)

@app.route('/api/product/<int:product_id>/comments', methods=['GET'])
def get_product_comments(product_id):
    """
    API pour récupérer les commentaires d'un produit spécifique
    """
    comments = load_comments()
    product_comments = comments.get(str(product_id), [])
    product_comments = sort_comments(product_comments)  # Trier les commentaires
    return jsonify(product_comments)

@app.route('/contact')
def contact():
    """
    Page de contact
    """
    return render_template('contact.html')

@app.route('/contact', methods=['POST'])
def messages():
    """
    Route pour recevoir et sauvegarder un message
    """
    try:
        # Récupérer les données du formulaire
        data = request.form.to_dict()
        data['date'] = datetime.now(timezone.utc).isoformat() # Ajouter la date

        # Sauvegarder le message
        if save_message(data):
            return jsonify({"status": "success", "message": "Votre message a été envoyé avec succès !"}), 200
        else:
            return jsonify({"status": "error", "message": "Erreur lors de la sauvegarde du message."}), 500
    except Exception as e:
        print(f"Erreur : {e}")
        return jsonify({"status": "error", "message": "Une erreur est survenue."}), 500


@app.route("/download/<user_id>")
def download(user_id):
    produits = PRODUIT_CACHE  # Utilisation du cache pour les produits
    product_names = request.args.get('products', '').split(',')

    if not product_names or product_names == ['']:
        # Si aucun paramètre `products` n'est fourni, afficher tous les produits
        user_products = [
            {
                "id": produit["id"],
                "name": produit["name"],
                "file_id": produit.get("resource_file_id")
            }
            for produit in produits
            if produit.get("resource_file_id")
        ]
    else:
        # Filtre basé sur les noms des produits envoyés
        user_products = [
            {
                "id": produit["id"],
                "name": produit["name"],
                "file_id": produit.get("resource_file_id")
            }
            for produit in produits
            if produit.get("name") in product_names
        ]

    # Si aucun produit valide n'est trouvé
    if not user_products:
        return render_template("error.html", message="Aucun produit valide trouvé.")

    # Transmettre les produits au template
    return render_template("download.html", user_id=user_id, products=user_products)




# --- Authentification pour le tableau de bord ---
app.secret_key = 'r5Ik9KbKouxeI1uxXtvHLNCvSHAsciBF4cWUcBkMk0g'  # Assurez-vous de stocker la clé de manière sécurisée

# --- Identifiants admin (à placer dans une base de données idéalement) ---
ADMIN_USERNAME = "k4d3t"
# Hash du mot de passe "spacekali"
ADMIN_PASSWORD_HASH = bcrypt.hashpw("spacekali".encode('utf-8'), bcrypt.gensalt())

DATA_FILE = 'data/site_data.json'

def load_data():
    """Charge les données depuis le fichier JSON."""
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    """Sauvegarde les données dans le fichier JSON."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Vérification du rôle super_admin
def is_super_admin():
    return session.get('username') == 'k4d3t'

@app.route('/k4d3t', methods=['GET', 'POST'])
def admin_login():
    """
    Page de connexion pour accéder au tableau de bord admin.
    """
    if session.get('admin_logged_in'):
        flash("Vous êtes déjà connecté.", "info")
        log_action("already_logged_in", {"message": "Tentative d'accès à la page de connexion alors que l'utilisateur est déjà connecté."})
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        data = load_data()
        users = data.get("users", [])

        for user in users:
            if user['username'] == username:
                if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                    session['admin_logged_in'] = True
                    session['username'] = username
                    session['role'] = user['role']

                    log_action("login_success", {"username": username, "role": user['role']})
                    flash("Connexion réussie !", "success")
                    return redirect(url_for('admin_dashboard'))

                log_action("login_failed", {"username": username, "reason": "Mot de passe incorrect."})
                flash("Identifiants invalides. Réessayez.", "error")
                break
        else:
            log_action("login_failed", {"username": username, "reason": "Nom d'utilisateur introuvable."})
            flash("Identifiants invalides. Réessayez.", "error")

    return render_template('admin_login.html')

@app.route('/k4d3t/dashboard')
def admin_dashboard():
    """
    Tableau de bord admin (protégé par authentification).
    """
    if not session.get('admin_logged_in'):
        log_action("unauthenticated_access_attempt", {"path": "/k4d3t/dashboard"})
        flash("Veuillez vous connecter pour accéder au tableau de bord.", "error")
        return redirect(url_for('admin_login'))

    log_action("access_dashboard", {"role": session.get('role')})
    return render_template('admin_dashboard.html', role=session.get('role'))

@app.route('/k4d3t/settings', methods=['GET', 'POST'])
def admin_settings():
    """
    Page de gestion des paramètres du site (accessible uniquement pour le super_admin).
    """
    # Vérifier si l'utilisateur est connecté et est un super_admin
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        log_action("unauthorized_access_attempt", {"path": "/k4d3t/settings"})
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))

    # Charger les données du site
    data = load_data()

    if request.method == 'POST':
        # Récupérer les données du formulaire
        site_title = request.form.get('title')
        site_description = request.form.get('description')

        # Vérifier que les champs sont remplis
        if site_title and site_description:
            # Mettre à jour les paramètres dans le fichier JSON
            data['site_settings']['title'] = site_title
            data['site_settings']['description'] = site_description

            # Sauvegarder les modifications
            save_data(data)
            log_action("update_site_settings", {
                "new_title": site_title,
                "new_description": site_description
            })
            flash("Paramètres mis à jour avec succès.", "success")
        else:
            log_action("update_site_settings_failed", {
                "reason": "Champs requis manquants"
            })
            flash("Tous les champs sont requis.", "error")

    log_action("access_settings_page", {"role": session.get('role')})
    return render_template('admin_settings.html', data=data)


@app.route('/k4d3t/settings/users', methods=['GET', 'POST'])
def admin_settings_users():
    """
    Page pour gérer les administrateurs et leurs rôles.
    Accessible uniquement au super_admin.
    """
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        log_action("unauthorized_access_attempt", {"path": "/k4d3t/settings/users"})
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))

    data = load_data()

    if request.method == 'POST':
        # Récupérer les données du formulaire
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        # Validation des champs
        if not username or not password or not role:
            log_action("add_user_failed", {
                "reason": "Champs requis manquants",
                "username": username,
                "role": role
            })
            flash("Tous les champs sont requis.", "error")
        elif len(username) < 3 or len(username) > 20:
            log_action("add_user_failed", {
                "reason": "Nom d'utilisateur invalide",
                "username": username,
                "role": role
            })
            flash("Le nom d'utilisateur doit contenir entre 3 et 20 caractères.", "error")
        elif len(password) < 6:
            log_action("add_user_failed", {
                "reason": "Mot de passe trop court",
                "username": username
            })
            flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
        elif not username.isalnum():
            log_action("add_user_failed", {
                "reason": "Nom d'utilisateur non alphanumérique",
                "username": username
            })
            flash("Le nom d'utilisateur ne doit contenir que des lettres et des chiffres.", "error")
        else:
            # Vérifier si l'utilisateur existe déjà
            for user in data['users']:
                if user['username'] == username:
                    log_action("add_user_failed", {
                        "reason": "Nom d'utilisateur déjà pris",
                        "username": username
                    })
                    flash("Nom d'utilisateur déjà pris. Choisissez-en un autre.", "error")
                    return render_template('admin_settings_users.html', users=data['users'])

            # Ajouter le nouvel utilisateur
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            data['users'].append({"username": username, "password": hashed_password, "role": role})
            save_data(data)
            log_action("add_user_success", {"username": username, "role": role})
            flash("Nouvel administrateur ajouté avec succès.", "success")

    log_action("access_users_management", {"role": session.get('role')})
    return render_template('admin_settings_users.html', users=data['users'])

@app.route('/k4d3t/settings/users/edit/<username>', methods=['POST'])
def edit_user(username):
    """
    Modifier un utilisateur existant via une requête AJAX.
    Accessible uniquement au super_admin.
    """
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        log_action("unauthorized_edit_attempt", {"target_username": username})
        return {"status": "error", "message": "Accès non autorisé"}, 403

    data = request.json  # Récupérer les données JSON envoyées par le frontend
    new_username = data.get('new_username')
    new_role = data.get('new_role')

    # Charger les données existantes
    site_data = load_data()
    users = site_data.get('users', [])

    # Rechercher l'utilisateur
    user = next((user for user in users if user['username'] == username), None)
    if not user:
        log_action("edit_user_failed", {
            "target_username": username,
            "reason": "Utilisateur introuvable"
        })
        return {"status": "error", "message": "Utilisateur introuvable"}, 404

    # Validation des données
    if not new_username or not new_role:
        log_action("edit_user_failed", {
            "target_username": username,
            "reason": "Champs requis manquants"
        })
        return {"status": "error", "message": "Les champs nom d'utilisateur et rôle sont requis"}, 400

    # Vérifier si le nouveau nom d'utilisateur est déjà pris
    if new_username != username and any(u['username'] == new_username for u in users):
        log_action("edit_user_failed", {
            "target_username": username,
            "new_username": new_username,
            "reason": "Nom d'utilisateur déjà pris"
        })
        return {"status": "error", "message": "Nom d'utilisateur déjà pris"}, 409

    # Mettre à jour les données
    user['username'] = new_username
    user['role'] = new_role

    # Sauvegarder dans le fichier JSON
    save_data(site_data)

    log_action("edit_user_success", {
        "old_username": username,
        "new_username": new_username,
        "new_role": new_role
    })
    return {"status": "success", "message": "Utilisateur mis à jour avec succès"}

@app.route('/settings/logs', methods=['GET'])
def get_logs():
    """Récupère les logs depuis logs.json."""
    try:
        with open(LOGS_FILE, "r") as f:
            logs = json.load(f)

        # Valider et nettoyer les logs avant de les renvoyer
        validated_logs = []
        for log in logs:
            validated_logs.append({
                "timestamp": log.get("timestamp", "N/A"),
                "user": log.get("user", "Anonyme"),
                "action": log.get("action", "Non spécifié"),
                "details": log.get("details", {})
            })

        log_action("view_logs", {"username": session.get('username')})  # Enregistrer l'accès aux logs
        return jsonify(validated_logs)
    except (FileNotFoundError, json.JSONDecodeError):
        log_action("view_logs_failed", {"username": session.get('username')})  # Enregistrer l'échec de l'accès aux logs
        return jsonify([])  # Retourne une liste vide si aucun log


@app.route('/settings/logs/view', methods=['GET'])
def view_logs():
    """Affiche la page HTML pour le journal d'activité."""
    log_action("view_logs_page", {"username": session.get('username')})  # Enregistrer l'accès à la page des logs
    return render_template("admin_settings_logs.html")


@app.route('/settings/logs/export', methods=['GET'])
def export_logs():
    """Exporte les logs au format CSV."""
    csv_file = "data/logs_export.csv"
    try:
        with open(LOGS_FILE, "r") as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log_action("export_logs_failed", {"username": session.get('username')})  # Enregistrer l'échec de l'export
        logs = []

    # Créer un fichier CSV
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        # En-têtes du CSV
        writer.writerow(["Timestamp", "User", "Action", "Details"])
        # Lignes des logs
        for log in logs:
            writer.writerow([log["timestamp"], log["user"], log["action"], json.dumps(log["details"])])

    log_action("export_logs_success", {"username": session.get('username')})  # Enregistrer l'export réussi
    return send_file(csv_file, as_attachment=True)


@app.route('/k4d3t/settings/users/delete/<username>', methods=['POST'])
def delete_user(username):
    """
    Supprimer un utilisateur.
    Accessible uniquement au super_admin.
    """
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        log_action("unauthorized_delete_attempt", {"target_username": username})
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))

    data = load_data()

    # Vérifier si l'utilisateur existe avant suppression
    user_exists = any(user['username'] == username for user in data['users'])
    if not user_exists:
        log_action("delete_user_failed", {"target_username": username, "reason": "Utilisateur introuvable"})
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for('admin_settings_users'))

    # Supprimer l'utilisateur
    data['users'] = [user for user in data['users'] if user['username'] != username]
    save_data(data)
    log_action("delete_user_success", {"deleted_username": username})
    flash("Utilisateur supprimé avec succès.", "success")
    return redirect(url_for('admin_settings_users'))

"""
PRODUIT
"""

PRODUCTS_FILE = "data/products.json"  # Fichier JSON contenant les produits
# Configurer le dossier de téléchargement des images
UPLOAD_FOLDER = './static/img'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Vérifier si l'extension du fichier est autorisée
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/products', methods=['GET'])
def get_products():
    """
    Retourne la liste des produits.
    """
    try:
        with open(PRODUCTS_FILE, "r") as f:
            products = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        products = []

    return jsonify(products)

@app.route('/admin/products/page', methods=['GET'])
def admin_products_page():
    """
    Page pour gérer les produits dans la section admin.
    """
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))

    # Log de l'action d'affichage de la page
    log_action("view_products_page", {"username": session.get('username')})

    return render_template('admin_products_dashboard.html')


@app.route('/admin/products/manage', methods=['GET'])
def admin_products_manage():
    """
    Page pour gérer et modifier les produits existants.
    """
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))

    # Log de l'accès à la page de gestion des produits
    log_action("view_products_manage", {"username": session.get('username')})

    return render_template('admin_products_manage.html')


@app.route('/admin/products/manage/<int:product_id>', methods=['GET'])
def get_product_by_id(product_id):
    """
    Retourne les détails d'un produit spécifique par son ID.
    """
    try:
        with open(PRODUCTS_FILE, "r") as f:
            products = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "Fichier introuvable ou JSON invalide"}), 500

    # Chercher le produit correspondant à l'ID
    product = next((p for p in products if p['id'] == product_id), None)

    if not product:
        return jsonify({"error": "Produit introuvable"}), 404

    return jsonify(product)

@app.route('/admin/products/manage/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """
    Met à jour un produit spécifique avec gestion des images.
    """
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403

    try:
        # Charger les produits existants
        with open(PRODUCTS_FILE, "r") as f:
            products = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        app.logger.error(f"Erreur lors du chargement des produits : {e}")
        return jsonify({"error": "Fichier introuvable ou JSON invalide"}), 500

    # Trouver le produit correspondant à l'ID
    product = next((p for p in products if p['id'] == product_id), None)
    if not product:
        app.logger.warning(f"Produit avec ID {product_id} introuvable.")
        return jsonify({"error": "Produit introuvable"}), 404

    # Récupérer les données de la requête
    data = request.form.to_dict()
    files = request.files.getlist("images")

    # Télécharger les nouvelles images
    image_paths = product.get("images", [])  # Garder les images existantes
    upload_folder = app.config.get('UPLOAD_FOLDER', './static/img')
    os.makedirs(upload_folder, exist_ok=True)

    for file in files:
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                image_paths.append(f"/static/img/{filename}")
            except Exception as e:
                app.logger.error(f"Erreur lors du téléchargement de l'image {file.filename} : {e}")
                return jsonify({"error": f"Erreur lors du téléchargement de l'image : {str(e)}"}), 500
        else:
            return jsonify({"error": f"Fichier invalide ou non autorisé : {file.filename}"}), 400

    # Mettre à jour les champs du produit
    allowed_fields = ['name', 'description', 'price', 'old_price', 'currency', 'stock', 'category',
                      'short_description', 'faq', 'badges', 'featured', 'resource_file_id', 'sku', 'images']

    for field in allowed_fields:
        if field in data:
            try:
                if field in ['price', 'stock']:
                    product[field] = int(data[field])
                elif field in ['faq', 'badges']:
                    product[field] = json.loads(data[field])
                elif field == 'featured':
                    product[field] = data[field].lower() == 'true'
                else:
                    product[field] = data[field]
            except (ValueError, json.JSONDecodeError) as e:
                app.logger.error(f"Erreur de validation pour le champ {field} : {e}")
                return jsonify({"error": f"Le champ {field} est invalide."}), 400

    # Mettre à jour les images
    product['images'] = image_paths

    # Sauvegarder les modifications dans le fichier
    try:
        with open(PRODUCTS_FILE, "w") as f:
            json.dump(products, f, indent=4)
    except Exception as e:
        app.logger.error(f"Erreur lors de la sauvegarde des produits : {e}")
        return jsonify({"error": f"Erreur lors de la sauvegarde : {str(e)}"}), 500

    app.logger.info(f"Produit {product_id} mis à jour avec succès.")
    return jsonify({"message": "Produit mis à jour avec succès", "product": product}), 200


@app.route('/admin/products/add', methods=['GET'])
def admin_products_add():
    """
    Récupérer la page pour ajouter un nouveau produit.
    """
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))

    # Log de l'accès à la page d'ajout d'un produit
    log_action("view_products_add", {"username": session.get('username')})

    return render_template('admin_products_add.html')


@app.route('/admin/products/add', methods=['POST'])
def add_product():
    """
    Ajoute un nouveau produit avec gestion des images.
    """
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403

    # Récupérer les données du produit depuis la requête
    data = request.form.to_dict()  # Récupère les champs texte
    files = request.files.getlist("images")  # Récupère les fichiers image

    # Valider les champs requis
    required_fields = ['name', 'description', 'price', 'currency', 'category', 'stock']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Le champ '{field}' est requis."}), 400

    # Charger les produits existants
    try:
        with open(PRODUCTS_FILE, "r") as f:
            products = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        products = []

    # Télécharger les images et générer leurs chemins
    image_paths = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_paths.append(f"/static/img/{filename}")
        else:
            return jsonify({"error": f"Fichier invalide : {file.filename}"}), 400

    # Générer automatiquement l'ID et le slug
    new_id = max([product['id'] for product in products], default=0) + 1
    slug = slugify(data['name'])

    # Créer le nouveau produit
    new_product = {
        "id": new_id,
        "name": data['name'],
        "short_description": data.get('short_description', ''),
        "description": data['description'],
        "price": int(data['price']),
        "old_price": int(data.get('old_price', 0)) if data.get('old_price') else None,
        "currency": data['currency'],
        "images": image_paths,  # Liste des chemins d'images
        "resource_file_id": data.get('resource_file_id', None),
        "featured": data.get('featured', False) == 'true',  # Convertir en booléen
        "badges": json.loads(data.get('badges', '[]')),  # Convertir en liste
        "category": data['category'],
        "stock": int(data['stock']),
        "sku": data.get('sku', f"SKU-{new_id}"),
        "faq": json.loads(data.get('faq', '[]')),  # Convertir en liste
        "slug": slug
    }

    # Ajouter le produit à la liste et sauvegarder dans le fichier JSON
    products.append(new_product)

    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=4)

    return jsonify({"message": "Produit ajouté avec succès.", "product": new_product}), 201


@app.route('/admin/products/manage/<int:product_id>/image/delete', methods=['POST'])
def delete_product_image(product_id):
    """
    Supprime une image spécifique d'un produit.
    """
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403

    # Charger les produits existants
    try:
        with open(PRODUCTS_FILE, "r") as f:
            products = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "Fichier introuvable ou JSON invalide"}), 500

    # Trouver le produit correspondant
    product = next((p for p in products if p['id'] == product_id), None)
    if not product:
        return jsonify({"error": "Produit introuvable"}), 404

    # Récupérer le chemin de l'image à supprimer
    data = request.get_json()
    image_url = data.get('imageUrl')
    if not image_url or image_url not in product.get('images', []):
        return jsonify({"error": "Image introuvable ou non associée à ce produit."}), 400

    # Supprimer l'image de la liste et du serveur
    try:
        product['images'].remove(image_url)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(image_url))
        if os.path.exists(image_path):
            os.remove(image_path)  # Supprimer physiquement l'image
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la suppression de l'image : {str(e)}"}), 500

    # Sauvegarder les modifications dans le fichier
    try:
        with open(PRODUCTS_FILE, "w") as f:
            json.dump(products, f, indent=4)
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la sauvegarde : {str(e)}"}), 500

    return jsonify({"message": "Image supprimée avec succès.", "product": product}), 200


@app.route('/admin/products/manage/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """
    Supprime un produit par son ID.
    """
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403

    try:
        # Charger les produits depuis le fichier JSON
        with open(PRODUCTS_FILE, "r") as f:
            products = json.load(f)

        # Filtrer les produits pour exclure celui à supprimer
        updated_products = [product for product in products if product['id'] != product_id]

        # Vérifier si le produit a bien été supprimé
        if len(products) == len(updated_products):
            return jsonify({"error": "Produit introuvable"}), 404

        # Sauvegarder la nouvelle liste de produits
        with open(PRODUCTS_FILE, "w") as f:
            json.dump(updated_products, f, indent=4)

        return jsonify({"message": "Produit supprimé avec succès."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


"""
FIN PRODUIT
"""
@app.route('/admin/payments')
def admin_payments():
    """
    Page pour gérer les paiements (accessible uniquement aux administrateurs).
    """
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))

    # Charger les données des paiements (à implémenter)
    payments = []  # Remplacez par la logique pour charger les paiements
    log_action("view_payments", {"username": session.get('username')})
    return render_template('admin_payments.html', payments=payments)

@app.route('/admin/messages')
def admin_messages_page():
    """
    Page pour consulter les messages reçus.
    """
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))

    # Charger les messages depuis le fichier JSON
    try:
        with open(CONTACTS_FILE, "r") as f:
            messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        messages = []  # Si le fichier est introuvable ou corrompu, utiliser une liste vide

    # Ajouter un champ 'id' unique si manquant dans les messages
    for index, message in enumerate(messages):
        if "id" not in message:
            message["id"] = index  # Nouveau champ ID

    # Sauvegarder les messages avec les nouveaux IDs dans le fichier JSON
    with open(CONTACTS_FILE, "w") as f:
        json.dump(messages, f, indent=4)

    log_action("view_messages", {"username": session.get('username')})
    return render_template('admin_messages.html', messages=messages)


@app.route('/admin/messages/data', methods=['GET'])
def admin_messages_data():
    """
    Retourne la liste des messages et ajoute dynamiquement le champ 'is_read' s'il n'existe pas.
    """
    filter_type = request.args.get('filter', 'all')  # Par défaut : tous les messages

    try:
        with open(CONTACTS_FILE, "r") as f:
            messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        messages = []

    # Ajout dynamique des champs 'id' et 'is_read'
    for index, message in enumerate(messages):
        if "id" not in message:
            message["id"] = index
        if "is_read" not in message:
            message["is_read"] = False

    # Filtrer les messages
    if filter_type == "unread":
        filtered_messages = [m for m in messages if not m["is_read"]]
    else:
        filtered_messages = messages

    return jsonify({"messages": filtered_messages})

@app.route('/admin/messages/<int:message_id>', methods=['GET'])
def get_message(message_id):
    """
    Récupère un message spécifique par son ID.
    """
    try:
        with open(CONTACTS_FILE, "r") as f:
            messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "Fichier de messages introuvable"}), 404

    if 0 <= message_id < len(messages):
        return jsonify(messages[message_id])
    else:
        return jsonify({"error": "Message introuvable"}), 404


@app.route('/admin/messages/mark_as_read', methods=['POST'])
def mark_message_as_read():
    """
    Met à jour le champ 'is_read' d'un message spécifique à 'true'.
    """
    message_id = request.json.get("message_id")

    try:
        with open(CONTACTS_FILE, "r") as f:
            messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "Fichier de messages introuvable"}), 404

    # Met à jour le champ 'is_read' pour le message correspondant
    updated = False
    for message in messages:
        if message.get("id") == message_id:
            message["is_read"] = True
            updated = True
            break

    if updated:
        with open(CONTACTS_FILE, "w") as f:
            json.dump(messages, f, indent=4)
        return jsonify({"message": "Message marqué comme lu"})
    else:
        return jsonify({"error": "Message introuvable"}), 404

@app.route('/admin/messages/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    """
    Supprime un message par son ID.
    """
    try:
        with open(CONTACTS_FILE, "r") as f:
            messages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "Fichier de messages introuvable"}), 404

    # Rechercher le message à supprimer par ID
    for i, message in enumerate(messages):
        if message.get("id") == message_id:
            deleted_message = messages.pop(i)
            with open(CONTACTS_FILE, "w") as f:
                json.dump(messages, f, indent=4)
            return jsonify({"message": f"Message '{deleted_message['message']}' supprimé avec succès"})

    return jsonify({"error": "Message introuvable"}), 404


@app.route('/admin/comments')
def admin_comments_page():
    """
    Page pour gérer et modérer les commentaires utilisateurs.
    """
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))

    # Charger les commentaires
    try:
        with open(COMMENTS_FILE, "r") as f:
            comments = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        comments = {}  # Utiliser un dictionnaire vide si le fichier est introuvable ou corrompu

    # Log action
    log_action("view_comments", {"username": session.get('username')})
    return render_template('admin_comments.html', comments=comments)

@app.route('/admin/comments/data', methods=['GET'])
def admin_comments_data():
    """
    Retourne une liste de commentaires avec un système de filtrage par statut.
    """
    filter_type = request.args.get('filter', 'all')  # Par défaut : tous les commentaires
    page = int(request.args.get('page', 1))  # Pagination : page actuelle
    comments_per_page = 5  # Limite de commentaires par page

    try:
        with open(COMMENTS_FILE, "r") as f:
            comments = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        comments = {}

    # Aplatir les commentaires par produit pour les manipuler facilement
    all_comments = []
    for product_id, product_comments in comments.items():
        for comment in product_comments:
            # Ajouter les champs manquants
            comment["product_id"] = product_id
            if "is_read" not in comment:
                comment["is_read"] = False
            if "content" not in comment:
                comment["content"] = comment["comment"]
            if "preview" not in comment:
                comment["preview"] = comment["comment"][:30] + "..."
            all_comments.append(comment)

    # Filtrer les commentaires selon le filtre
    if filter_type == "unread":
        filtered_comments = [c for c in all_comments if not c.get("is_read", False)]
    elif filter_type == "read":
        filtered_comments = [c for c in all_comments if c.get("is_read", False)]
    else:
        filtered_comments = all_comments

    # Pagination
    start_index = (page - 1) * comments_per_page
    paginated_comments = filtered_comments[start_index:start_index + comments_per_page]

    return jsonify({"comments": paginated_comments, "total": len(filtered_comments)})


@app.route('/admin/comments/<int:comment_id>', methods=['GET'])
def get_comment(comment_id):
    """
    Récupère un commentaire spécifique par son ID.
    """
    try:
        with open(COMMENTS_FILE, "r") as f:
            comments = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "Fichier de commentaires introuvable"}), 404

    # Rechercher le commentaire par ID
    for product_id, product_comments in comments.items():
        for comment in product_comments:
            if comment["id"] == comment_id:
                comment["product_id"] = product_id
                # Retournez le champ "comment" comme "content" pour éviter toute confusion
                return jsonify({
                    "id": comment["id"],
                    "product_id": comment["product_id"],
                    "content": comment["comment"],  # Remappez "comment" en "content"
                    "date": comment["date"],
                    "rating": comment.get("rating", None)  # Inclure d'autres champs si nécessaire
                })

    return jsonify({"error": "Commentaire introuvable"}), 404

@app.route('/admin/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    """
    Supprime un commentaire par son ID.
    """
    try:
        with open(COMMENTS_FILE, "r") as f:
            comments = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "Fichier de commentaires introuvable"}), 404

    # Rechercher et supprimer le commentaire par ID
    for product_id, product_comments in comments.items():
        for i, comment in enumerate(product_comments):
            if comment["id"] == comment_id:
                deleted_comment = product_comments.pop(i)
                with open(COMMENTS_FILE, "w") as f:
                    json.dump(comments, f, indent=4)
                return jsonify({"message": f"Commentaire supprimé avec succès : {deleted_comment['comment']}"})

    return jsonify({"error": "Commentaire introuvable"}), 404


@app.route('/admin/comments/mark_as_read', methods=['POST'])
def mark_comment_as_read():
    """
    Marque un commentaire comme lu.
    """
    comment_id = request.json.get("comment_id")
    updated = False

    try:
        with open(COMMENTS_FILE, "r") as f:
            comments = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "Fichier de commentaires introuvable"}), 404

    for product_id, product_comments in comments.items():
        for comment in product_comments:
            if comment["id"] == comment_id:
                comment["is_read"] = True
                updated = True

    if updated:
        with open(COMMENTS_FILE, "w") as f:
            json.dump(comments, f, indent=4)
        return jsonify({"message": "Commentaire marqué comme lu"})
    else:
        return jsonify({"error": "Commentaire introuvable"}), 404


@app.route('/k4d3t/logout')
def admin_logout():
    """
    Déconnexion de l'admin.
    """
    log_action("logout", {"username": session.get('username')})  # Enregistrer la déconnexion
    session.pop('admin_logged_in', None)
    session.pop('username', None)
    session.pop('role', None)  # Supprimer également le rôle de la session
    flash("Vous avez été déconnecté.", "success")
    return redirect(url_for('admin_login'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5005))  # Utilise le PORT de Render ou 5005 en local
    app.run(port=port)
