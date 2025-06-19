from flask import Flask, render_template, jsonify, request, redirect, url_for, abort, session, flash, send_file, Response
import json
import os
from datetime import datetime, timezone
import re
from unicodedata import normalize
import bcrypt
import csv
from flask_cors import CORS
from werkzeug.utils import secure_filename
import requests
import threading
import time
from apiMoneyFusion import PaymentClient
import html  # Utilisé pour échapper les caractères spéciaux HTML
from flask_caching import Cache
from flask_compress import Compress
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import random
from jinja2.runtime import Undefined
import logging

# --- Logging robuste en prod ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
    handlers=[
        logging.FileHandler("flask_app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
Compress(app)

# -- Flask-Caching en prod (filesystem ou redis selon config) --
if os.environ.get("USE_REDIS_CACHE") == "1":
    redis_url = os.environ.get("REDIS_URL") or "redis://localhost:6379"
    cache = Cache(config={
        'CACHE_TYPE': 'redis',
        'CACHE_REDIS_URL': redis_url,
        'CACHE_DEFAULT_TIMEOUT': 120
    })
    print("Flask-Cache: Redis backend actif")
else:
    cache = Cache(config={
        'CACHE_TYPE': 'filesystem',
        'CACHE_DIR': '/tmp/flask_cache',  # Change si besoin
        'CACHE_DEFAULT_TIMEOUT': 120
    })
    print("Flask-Cache: Filesystem backend actif")

cache.init_app(app)

Talisman(app, content_security_policy=None)

# -- Flask-Limiter, Redis si possible --
redis_url = os.environ.get("REDIS_URL") or "redis://localhost:6379"
try:
    import redis
    r = redis.from_url(redis_url)
    r.ping()
    app.config["RATELIMIT_STORAGE_URL"] = redis_url
    print("Flask-Limiter : Redis backend actif")
except Exception:
    print("Flask-Limiter : Backend mémoire utilisé (ne pas utiliser en prod multi-worker)")

limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)

# --- Logging du temps de traitement ---
@app.before_request
def start_timer():
    request.start_time = time.perf_counter()

@app.after_request
def log_time(response):
    duration = time.perf_counter() - getattr(request, 'start_time', time.perf_counter())
    logger.info(f"{request.method} {request.path} took {duration*1000:.2f} ms")
    return response

# --- Headers communs ---
@app.after_request
def add_common_headers(response):
    # Pour toutes les réponses API, ajoute un cache HTTP
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "public, max-age=60"
    # Headers sécurité et SEO-friendly
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# --- Helper functions ---

LOGS_FILE = "data/logs.json"
COMMENTS_FILE = "data/comments.json"

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
    # Sécurité : si text est None ou “Undefined” Jinja2
    if not isinstance(text, str):
        if text is None or isinstance(text, Undefined):
            return ""
        text = str(text)
    text = normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[\s]+', '-', text)

def get_seo_context(
    *,
    meta_title=None,
    meta_description=None,
    og_image=None,
    meta_robots="index, follow",
    meta_author="Digital Adept",
    meta_canonical=None,
    meta_og_type="website",
    meta_og_url=None,
    meta_og_site_name="Digital Adept",
    meta_og_locale="fr_FR",
    meta_fb_app_id=None,
    meta_keywords=None,
    meta_theme_color="#244",
    meta_image_alt=None,
    meta_language="fr",
    meta_jsonld=None,
    meta_breadcrumb_jsonld=None,
    meta_twitter_site="@TonCompteTwitter",  # À personnaliser avec ton compte Twitter
    meta_twitter_title=None,
    meta_twitter_description=None,
    meta_twitter_image=None,
    meta_publisher=None,
    meta_date_published=None,
    meta_date_modified=None,
    meta_site_verification=None,  # Google/Bing/Yandex site verification
    extra_vars=None
):
    """
    Génère un contexte SEO complet pour Flask render_template.
    Passez extra_vars=dict(...) pour ajouter des variables spécifiques.
    """
    context = dict(
        meta_title=meta_title or "Digital Adept - Boutique de produits digitaux",
        meta_description=meta_description or "Plateforme de vente de produits digitaux accessibles à tous.",
        meta_robots=meta_robots,
        meta_author=meta_author,
        meta_canonical=(meta_canonical or request.url).replace("http://", "https://"),
        meta_og_title=meta_title or "Digital Adept",
        meta_og_description=meta_description or "Plateforme de vente de produits digitaux accessibles à tous.",
        meta_og_type=meta_og_type,
        meta_og_url=(meta_og_url or request.url).replace("http://", "https://"),
        meta_og_image=og_image,
        meta_og_site_name=meta_og_site_name,
        meta_og_locale=meta_og_locale,
        meta_fb_app_id=meta_fb_app_id,
        meta_keywords=meta_keywords,
        meta_theme_color=meta_theme_color,
        meta_image_alt=meta_image_alt,
        meta_language=meta_language,
        meta_jsonld=json.dumps(meta_jsonld, ensure_ascii=False) if isinstance(meta_jsonld, dict) else meta_jsonld,
        meta_breadcrumb_jsonld=json.dumps(meta_breadcrumb_jsonld, ensure_ascii=False) if isinstance(meta_breadcrumb_jsonld, dict) else meta_breadcrumb_jsonld,
        meta_twitter_title=meta_twitter_title or meta_title or "Digital Adept",
        meta_twitter_description=meta_twitter_description or meta_description or "Plateforme de vente de produits digitaux accessibles à tous.",
        meta_twitter_image=meta_twitter_image or og_image,
        meta_twitter_site=meta_twitter_site,
        meta_publisher=meta_publisher,
        meta_date_published=meta_date_published,
        meta_date_modified=meta_date_modified,
        meta_site_verification=meta_site_verification,
        og_image=og_image,  # fallback pour twitter:image
    )
    if extra_vars:
        context.update(extra_vars)
    return context


def make_breadcrumb(*elements):
    """
    elements: liste de tuples (name, url)
    Retourne le JSON-LD du fil d'Ariane.
    """
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i+1,
                "name": name,
                "item": url
            } for i, (name, url) in enumerate(elements)
        ]
    }

MOCKAPI_URL = "https://6840a10f5b39a8039a58afb0.mockapi.io/api/externalapi/produits"

@cache.cached(timeout=120, key_prefix="products")
def fetch_products():
    """Récupère tous les produits depuis MockAPI (avec cache Flask)"""
    r = requests.get(MOCKAPI_URL, timeout=7)
    produits = r.json()
    for p in produits:
        try:
            p['id'] = int(p['id'])
        except (KeyError, ValueError, TypeError):
            pass
    return produits

def fetch_product_by_id(product_id):
    try:
        r = requests.get(f"{MOCKAPI_URL}/{product_id}", timeout=7)
        if r.status_code == 200:
            produit = r.json()
            try:
                produit['id'] = int(produit['id'])
            except (KeyError, ValueError, TypeError):
                pass
            # Correction des champs attendus
            if "badges" not in produit or not isinstance(produit["badges"], list):
                produit["badges"] = []
            if "faq" not in produit or not isinstance(produit["faq"], list):
                produit["faq"] = []
            if "images" not in produit or not isinstance(produit["images"], list):
                produit["images"] = []
            return produit
        return None
    except Exception as e:
        print(f"[MOCKAPI] Erreur fetch_product_by_id: {e}")
        return None

def add_product_to_mockapi(new_product):
    """Ajoute un produit via MockAPI."""
    try:
        r = requests.post(MOCKAPI_URL, json=new_product, timeout=10)
        if r.status_code in (200, 201):
            return r.json()
        print(f"[MOCKAPI] Erreur création produit: {r.text}")
        return None
    except Exception as e:
        print(f"[MOCKAPI] Erreur add_product_to_mockapi: {e}")
        return None

def update_product_in_mockapi(product_id, update_dict):
    """Met à jour un produit MockAPI (PUT)."""
    try:
        r = requests.put(f"{MOCKAPI_URL}/{product_id}", json=update_dict, timeout=10)
        if r.status_code in (200, 201):
            return r.json()
        print(f"[MOCKAPI] Erreur update produit: {r.text}")
        return None
    except Exception as e:
        print(f"[MOCKAPI] Erreur update_product_in_mockapi: {e}")
        return None

def delete_product_from_mockapi(product_id):
    """Supprime un produit MockAPI."""
    try:
        r = requests.delete(f"{MOCKAPI_URL}/{product_id}", timeout=7)
        return r.status_code == 200
    except Exception as e:
        print(f"[MOCKAPI] Erreur delete_product_from_mockapi: {e}")
        return False

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

MESSAGES_BOT_TOKEN = "7709634006:AAEvJvaqd9VGsCY8bGJdu6bKGwGTmGmwNB4"
MESSAGES_CHAT_ID = "7313154263"

def escape_md(text):
    """
    Échappe tous les caractères spéciaux requis par MarkdownV2 pour Telegram.
    """
    for c in ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(c, f'\\{c}')
    return text


def escape_code_md(text):
    """
    Échappe uniquement le backslash et le backtick dans un bloc code MarkdownV2.
    """
    text = text.replace('\\', '\\\\')
    text = text.replace('`', '\\`')
    return text



def send_telegram_message(data):
    nom = html.escape(str(data.get("nom", "")).strip())
    email = html.escape(str(data.get("email", "")).strip())
    message = str(data.get("message", "")).strip()

    # Quote et bold chaque ligne du message utilisateur
    if message:
        quoted_lines = [f"<b>{html.escape(line)}</b>" for line in message.splitlines()]
        quoted_message = "<blockquote>" + "\n".join(quoted_lines) + "</blockquote>"
    else:
        quoted_message = "<blockquote><b>(vide)</b></blockquote>"

    text = (
        f"📩 Nouveau message de contact\n\n"
        f"👤 Nom : {nom}\n"
        f"✉️ E-mail : {email}\n\n"
        f"📝 Message :\n\n"
        f"{quoted_message}"
    )

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{MESSAGES_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": MESSAGES_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=8,
        )
        print("Telegram response:", response.status_code, response.text)
        return response.ok
    except Exception as e:
        print("Erreur lors de l'envoi à Telegram:", e)
        return False

app.jinja_env.globals['slugify'] = slugify
@app.template_filter('shuffle')
def shuffle_filter(seq):
    seq = list(seq)
    random.shuffle(seq)
    return seq

# --- Routes produits ---
@cache.cached(timeout=120)
@app.route('/')
def home():
    produits = fetch_products()
    produits_vedette = [p for p in produits if p.get("featured")]

    website_jsonld = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Digital Adept™",
        "url": url_for('home', _external=True),
        "description": "La meilleure boutique africaine de produits digitaux, logiciels, services et astuces pour booster, démarrer ou commencer votre business en ligne.",
        "inLanguage": "fr"
    }

    faq_jsonld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "Digital Adept, c’est quoi exactement ?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Plateforme africaine de produits digitaux : on vous propose le meilleur du numérique, accessible, simple et sécurisé, pour tous les usages."
                }
            },
            {
                "@type": "Question",
                "name": "Qui peut acheter sur Digital Adept ?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Tout le monde ! Que vous soyez en Afrique ou ailleurs, Digital Adept est ouvert à tous ceux qui cherchent des solutions numériques innovantes à prix doux."
                }
            },
            {
                "@type": "Question",
                "name": "Pourquoi faire confiance à Digital Adept ?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": (
                        "• Créé en Afrique, pour les réalités africaines.<br>"
                        "• Des prix <b>waou</b> et des promos régulières.<br>"
                        "• Des produits testés, validés et recommandés par l’équipe.<br>"
                        "• Plateforme rapide, moderne, et 100 % sécurisée (https)."
                    )
                }
            },
            {
                "@type": "Question",
                "name": "Comment sont sécurisés mes paiements ?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": (
                        "<b>Vos paiements passent par FusionPay</b> : solution de paiement chiffrée, reconnue pour la sécurité et la fiabilité en Afrique.<br>"
                        "Digital Adept ne stocke jamais vos infos bancaires."
                    )
                }
            },
            {
                "@type": "Question",
                "name": "Et mes données personnelles alors ?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": (
                        "Vos données restent confidentielles : elles ne sont jamais revendues ni partagées. La confiance, c’est la base chez Digital Adept."
                    )
                }
            },
            {
                "@type": "Question",
                "name": "Quels types de produits trouve-t-on ici ?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": (
                        "Logiciels, ebooks, outils pour entreprises, ressources pour étudiants, services exclusifs, et plein d’autres surprises à venir !"
                    )
                }
            },
            {
                "@type": "Question",
                "name": "Comment contacter l’équipe ou obtenir un conseil personnalisé ?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": (
                        "Écrivez-nous via le formulaire de contact sur /contact : on répond vite et avec le sourire !"
                    )
                }
            }
        ]
    }

    context = get_seo_context(
        meta_title="Digital Adept™ - Boutique africaine de produits 100%  digitaux",
        meta_description="La meilleure boutique africaine de produits digitaux, logiciels, services et astuces pour booster, démarrer ou commencer votre business en ligne.",
        og_image=url_for('static', filename='img/logo.png', _external=True),
        meta_keywords="digital, boutique, ebooks, logiciels, services, Afrique",
        meta_jsonld=[website_jsonld, faq_jsonld],  # <-- la bonne syntaxe
        meta_breadcrumb_jsonld=make_breadcrumb(
            ("Accueil", url_for('home', _external=True))
        ),
        extra_vars={
            "produits_vedette": produits_vedette,
            "produits": produits
        }
    )
    return render_template('home.html', **context)
@cache.cached(timeout=120)
@app.route('/produits')
def produits():
    produits = fetch_products()
    context = get_seo_context(
        meta_title="Tous les produits - Digital Adept™",
        meta_description="Liste complète de tous les produits digitaux, logiciels, ebooks et services disponibles.",
        og_image=url_for('static', filename='img/logo.png', _external=True),
        meta_keywords="catalogue, produits digitaux, ebooks, logiciels, services",
        meta_jsonld={
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "Tous les produits - Digital Adept™",
            "description": "Liste complète de tous les produits digitaux, logiciels, ebooks et services.",
            "url": url_for('produits', _external=True),
            "inLanguage": "fr"
        },
        meta_breadcrumb_jsonld=make_breadcrumb(
            ("Accueil", url_for('home', _external=True)),
            ("Produits", url_for('produits', _external=True)),
        ),
        extra_vars={"produits": produits}
    )
    return render_template('produits.html', **context)
@cache.cached(timeout=120)
@app.route('/produit/<slug>')
def product_detail(slug):
    produits = fetch_products()
    produit = next((p for p in produits if slugify(p.get("name")) == slug), None)
    if not produit:
        context = get_seo_context(
            meta_title="Produit introuvable - Digital Adept™",
            meta_description="Le produit recherché n'existe pas ou a été supprimé.",
            meta_robots="noindex, follow",
            meta_breadcrumb_jsonld=make_breadcrumb(
                ("Accueil", url_for('home', _external=True)),
                ("Produits", url_for('produits', _external=True)),
            )
        )
        return render_template('404.html', **context), 404

    produit_comments = load_comments().get(str(produit.get("id")), [])
    context = get_seo_context(
        meta_title=f"{produit['name']} - Digital Adept™",
        meta_description=produit.get("short_description", "Découvrez ce produit digital sur Digital Adept."),
        og_image=produit.get("images", [url_for('static', filename='img/logo.png', _external=True)])[0],
        meta_keywords=f"{produit['name']}, digital, boutique",
        meta_jsonld={
            "@context": "https://schema.org",
            "@type": "Product",
            "name": produit['name'],
            "image": produit.get("images"),
            "description": produit.get("short_description"),
            "brand": "Digital Adept™",
            "offers": {
                "@type": "Offer",
                "price": produit['price'],
                "priceCurrency": produit['currency'],
                "availability": "https://schema.org/InStock" if produit['stock'] > 0 else "https://schema.org/OutOfStock"
            }
        },
        meta_breadcrumb_jsonld=make_breadcrumb(
            ("Accueil", url_for('home', _external=True)),
            ("Produits", url_for('produits', _external=True)),
            (produit['name'], url_for('product_detail', slug=slugify(produit['name']), _external=True)),
        ),
        extra_vars={
            "produit": produit,
            "comments": produit_comments
        }
    )
    return render_template('product.html', **context)

@app.route('/produit/<slug>/comment', methods=['POST'])
def add_comment(slug):
    """
    Route pour ajouter un commentaire à un produit spécifique
    """
    produits = fetch_products()

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
    produits = fetch_products()
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
@cache.cached(timeout=120)
@app.route('/contact')
def contact():
    context = get_seo_context(
        meta_title="Contactez-nous - Digital Adept™",
        meta_description="Besoin d'informations ou d'aide ? Contactez l'équipe Digital Adept™.",
        og_image=url_for('static', filename='img/logo.png', _external=True),
        meta_keywords="contact, support, digital adept, assistance",
        meta_jsonld={
            "@context": "https://schema.org",
            "@type": "ContactPage",
            "name": "Contact - Digital Adept™",
            "description": "Besoin d'aide ou d'une information ? Contactez-nous.",
            "url": url_for('contact', _external=True),
            "inLanguage": "fr"
        },
        meta_breadcrumb_jsonld=make_breadcrumb(
            ("Accueil", url_for('home', _external=True)),
            ("Contact", url_for('contact', _external=True)),
        ),
    )
    return render_template('contact.html', **context)

@app.route('/contact', methods=['POST'])
def messages():
    try:
        # Récupérer les données du formulaire
        data = request.form.to_dict()

        # ENVOI AU BOT TELEGRAM
        # (si tu veux, tu peux le rendre async/multithread pour ne pas bloquer la réponse web)
        threading.Thread(target=send_telegram_message, args=(data,)).start()
        return jsonify({"status": "success", "message": "Votre message a été envoyé avec succès !"}), 200
    except Exception as e:
        print(f"Erreur : {e}")
        return jsonify({"status": "error", "message": "Une erreur est survenue."}), 500

@app.route("/payer", methods=["POST"])
def payer():
    """
    Reçoit paymentData du frontend,
    crée la demande MoneyFusion côté serveur,
    et renvoie l’URL de paiement.
    """
    data = request.json
    MONEYFUSION_API_URL = "https://www.pay.moneyfusion.net/Digital_Adept/a5f4d44ad70069fa/pay/"
    try:
        r = requests.post(MONEYFUSION_API_URL, json=data)
        print("Réponse brute MoneyFusion:", r.status_code, repr(r.text))
        try:
            res = r.json()
        except Exception as e:
            print("Erreur JSON decode:", e)
            print("Texte brut reçu:", r.text)
            return jsonify({"error": "Réponse MoneyFusion non valide", "details": r.text}), 400
        # On attend un champ "statut" True et "url" pour le paiement
        if res.get("statut") and res.get("url"):
            # On renvoie l'URL de paiement et le token (pour le callback)
            return jsonify({"pay_url": res["url"], "token": res.get("token")})
        return jsonify({"error": res.get("message")}), 400
        print("Erreur dans /payer:", e)
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/webhook", methods=["POST"])
def webhook():
    """
    MoneyFusion envoie les notifications ici.
    Sans base : on peut juste accuser réception avec 200 OK.
    """
    return "", 200
@cache.cached(timeout=120)
@app.route("/callback")
def callback():
    """
    Affiche la page de téléchargement après paiement.
    - MoneyFusion doit renvoyer ici avec ?token=xxxx dans le return_url.
    - On va demander à l’API MoneyFusion le détail de la transaction avec ce token.
    - On affiche les produits achetés à partir des infos du paiement.
    """
    token = request.args.get("token")
    produits = PRODUIT_CACHE

    # Si pas de token, impossible de savoir quoi donner
    if not token:
        print("DEBUG CALLBACK:", {
        "token": token,
        "produits envoyés": user_products if 'user_products' in locals() else [],
        "message": message if 'message' in locals() else None
        })
        print("product_names:", product_names)
        print("user_products:", user_products)
        return render_template("download.html", products=[], message="Erreur, paiement introuvable")

    # Appelle MoneyFusion pour vérifier le paiement
    try:
        r = requests.get(f"https://www.pay.moneyfusion.net/paiementNotif/{token}")
        res = r.json()
        print("Réponse MoneyFusion callback:", res)
        if not res.get("statut") or "data" not in res:
            print("DEBUG CALLBACK:", {
            "token": token,
            "produits envoyés": user_products if 'user_products' in locals() else [],
            "message": message if 'message' in locals() else None
            })
            print("product_names:", product_names)
            print("user_products:", user_products)
            return render_template("download.html", products=[], message="Erreur, paiement introuvable")

        data = res["data"]

        # On vérifie si le paiement est bien complété
        if data.get("statut") != "paid":
            print("DEBUG CALLBACK:", {
            "token": token,
            "produits envoyés": user_products if 'user_products' in locals() else [],
            "message": message if 'message' in locals() else None
            })
            print("product_names:", product_names)
            print("user_products:", user_products)
            attente_msg = (
                "Votre paiement est en cours de validation par MoneyFusion… "
                "Merci de patienter quelques secondes, la page va se recharger automatiquement. "
                "Si rien ne s'affiche après 2 minutes, contactez le support avec votre numéro de transaction."
            )
            return render_template("download.html", products=[], message=attente_msg)

        # On récupère les noms des produits achetés depuis le paiement (dans "article" ou similaire)
        # Ici, on suppose que tu as envoyé les noms dans personal_Info ou un champ custom, sinon adapte
        product_names = []
        # Si tu as stocké le nom dans personal_Info (à adapter à la structure reçue)
        if "personal_Info" in data and isinstance(data["personal_Info"], list):
            # Ex : [{"userId": 1, "orderId": 123, "products": ["Sac", "Chaussure"]}]
            if "products" in data["personal_Info"][0]:
                product_names = data["personal_Info"][0]["products"]
        # Sinon, ici tu pourrais stocker dans un autre champ lors du POST initial (à adapter à ton besoin)

        # Si pas de produits précisés, on propose tout ce qui est disponible (mieux de restreindre !)
        if not product_names:
            user_products = [
                {
                    "id": produit["id"],
                    "name": produit["name"],
                    "file_id": produit.get("resource_file_id"),
                }
                for produit in produits
                if produit.get("resource_file_id")
            ]
        else:
            user_products = [
                {
                    "name": produit["name"],
                    "file_id": produit.get("resource_file_id"),
                    "id": produit["id"]
                }
                for produit in produits
                if produit.get("name") in product_names
            ]

        if not user_products:
            print("DEBUG CALLBACK:", {
            "token": token,
            "produits envoyés": user_products if 'user_products' in locals() else [],
            "message": message if 'message' in locals() else None
            })

            print("product_names:", product_names)
            print("user_products:", user_products)
            return render_template("download.html", products=[], message="Erreur, Veuillez nous contacter")

        # Affiche la page de téléchargement avec les bons produits
        print("DEBUG CALLBACK:", {
        "token": token,
        "produits envoyés": user_products if 'user_products' in locals() else [],
        "message": message if 'message' in locals() else None
        })

        print("product_names:", product_names)
        print("user_products:", user_products)
        return render_template("download.html", products=user_products, message=None)

    except Exception as e:
        print("DEBUG CALLBACK:", {
        "token": token,
        "produits envoyés": user_products if 'user_products' in locals() else [],
        "message": message if 'message' in locals() else None
        })

        print("product_names:", product_names)
        print("user_products:", user_products)
        return render_template("download.html", products=[], message="Erreur technique, contactez le support.")

@cache.cached(timeout=120)
@app.route("/callbacktest")
def callbacktest():
    """
    Affiche la page de téléchargement après paiement.
    - MoneyFusion doit renvoyer ici avec ?token=xxxx dans le return_url.
    - On va demander à l’API MoneyFusion le détail de la transaction avec ce token.
    - On affiche les produits achetés à partir des infos du paiement.
    - MODE DEV : on peut forcer l'état via ?debug_status=pending|paid|fail        http://localhost:5005/callbacktest?debug_status=
    """
    token = request.args.get("token")
    debug_status = request.args.get("debug_status")  # Pour tests sans paiement réel !
    produits = PRODUIT_CACHE

    # SIMULATION : debug_status présent = mode test
    if debug_status:
        if debug_status == "pending":
            attente_msg = (
                "Votre paiement est en cours de validation par MoneyFusion… "
            )
            return render_template("download.html", products=[], message=attente_msg)
        elif debug_status == "paid":
            # Simule un produit acheté
            user_products = [{
                "name": "Produit Test",
                "file_id": ["AgACAgQAAyEFAASgim1aAAMTaE77UHaZ6MLC5mNKYFY2IoS67D8AAurFMRtRbnlSRE_8-hjk_tgBAAMCAAN3AAM2BA"],
                "id": 1
            }]
            return render_template("download.html", products=user_products, message=None)
        elif debug_status == "fail":
            return render_template("download.html", products=[], message="Paiement non validé. Contactez le support.")
        else:
            return render_template("download.html", products=[], message="Erreur, paiement introuvable")

    # === CODE NORMAL (prod) ===
    if not token:
        print("DEBUG CALLBACK:", {
        "token": token,
        "produits envoyés": [],
        "message": None
        })
        return render_template("download.html", products=[], message="Erreur, paiement introuvable")

    try:
        r = requests.get(f"https://www.pay.moneyfusion.net/paiementNotif/{token}")
        res = r.json()
        print("Réponse MoneyFusion callback:", res)
        if not res.get("statut") or "data" not in res:
            print("DEBUG CALLBACK:", {
            "token": token,
            "produits envoyés": [],
            "message": None
            })
            return render_template("download.html", products=[], message="Erreur, paiement introuvable")

        data = res["data"]

        if data.get("statut") != "paid":
            attente_msg = (
                "Votre paiement est en cours de validation par MoneyFusion… "
                "Merci de patienter quelques secondes, la page va se recharger automatiquement. "
                "Si rien ne s'affiche après 2 minutes, contactez le support avec votre numéro de transaction."
            )
            return render_template("download.html", products=[], message=attente_msg)

        product_names = []
        if "personal_Info" in data and isinstance(data["personal_Info"], list):
            if "products" in data["personal_Info"][0]:
                product_names = data["personal_Info"][0]["products"]

        if not product_names:
            user_products = [
                {
                    "id": produit["id"],
                    "name": produit["name"],
                    "file_id": produit.get("resource_file_id"),
                }
                for produit in produits
                if produit.get("resource_file_id")
            ]
        else:
            user_products = [
                {
                    "name": produit["name"],
                    "file_id": produit.get("resource_file_id"),
                    "id": produit["id"]
                }
                for produit in produits
                if produit.get("name") in product_names
            ]

        if not user_products:
            return render_template("download.html", products=[], message="Erreur, Veuillez nous contacter")

        return render_template("download.html", products=user_products, message=None)

    except Exception as e:
        print("DEBUG CALLBACK:", {
        "token": token,
        "produits envoyés": [],
        "message": None
        })
        return render_template("download.html", products=[], message="Erreur technique, contactez le support.")


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
@cache.cached(timeout=120)
@app.route('/k4d3t', methods=['GET', 'POST'])
@limiter.limit("10/minute")
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
@cache.cached(timeout=120)
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

@cache.cached(timeout=120)
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
# PAS D'UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'avif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

CDN_PREFIX = "https://cdn.jsdelivr.net/gh/k4d2t/DigitalAdept@main/project/static/img/"

@app.route('/admin/products', methods=['GET'])
def get_products():
    """
    Retourne la liste des produits.
    """
    try:
        products = fetch_products()
    except (FileNotFoundError, json.JSONDecodeError):
        products = []

    return jsonify(products)
@cache.cached(timeout=120)
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


# --- Mémoire temporaire pour fichiers Telegram reçus par webhook ---
TELEGRAM_FILES = []
TELEGRAM_FILES_LIMIT = 200  # Ajuste le nombre max si tu veux
FILE_CHAT_ID = "-1002693426522"

@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    print("Webhook reçu !", request.json)
    update = request.json
    msg = update.get("message") or update.get("channel_post")
    if not msg:
        return '', 200
    # Filtrer par chat_id
    if str(msg.get("chat", {}).get("id")) != FILE_CHAT_ID:
        return '', 200

    # PHOTOS
    if 'photo' in msg:
        variants = []
        for photo in msg['photo']:
            variants.append({
                "label": f"{photo['width']}x{photo['height']}",
                "file_id": photo['file_id'],
            })
        TELEGRAM_FILES.append({
            "name": msg.get("caption", "Photo Telegram"),
            "type": "image",
            "date": msg.get("date"),
            "variants": variants,
            "preview_file_id": variants[-1]['file_id'] if variants else None,
        })
    # DOCUMENTS (pdf, zip, etc)
    elif 'document' in msg:
        doc = msg['document']
        TELEGRAM_FILES.append({
            "name": doc.get("file_name", "Fichier Telegram"),
            "type": doc.get("mime_type", "document"),
            "date": msg.get("date"),
            "file_id": doc.get("file_id"),
            "size": doc.get("file_size"),
        })

    if len(TELEGRAM_FILES) > TELEGRAM_FILES_LIMIT:
        TELEGRAM_FILES.pop(0)

    return '', 200

# --- PAGE ADMIN ---
@cache.cached(timeout=120)
@app.route('/admin/telegram-files', methods=['GET'])
def admin_telegram_files():
    """
    Page pour gérer les fichiers Telegram dans la section admin.
    """
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))

    # Log de l'accès à la page de gestion des fichiers Telegram
    log_action("view_telegram_files_page", {"username": session.get('username')})

    return render_template('admin_telegram_files.html')

# --- API POUR LE FRONTEND ADMIN ---
@app.route('/admin/api/telegram-files', methods=['GET'])
def api_telegram_files():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    # Renvoie les fichiers Telegram reçus via webhook, les plus récents d'abord
    return jsonify(list(TELEGRAM_FILES)[::-1])
@cache.cached(timeout=120)
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
        products = fetch_products()
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "Fichier introuvable ou JSON invalide"}), 500

    # Chercher le produit correspondant à l'ID
    product = fetch_product_by_id(product_id)

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
        products = fetch_products()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        app.logger.error(f"Erreur lors du chargement des produits : {e}")
        return jsonify({"error": "Fichier introuvable ou JSON invalide"}), 500

    # Trouver le produit correspondant à l'ID
    product = fetch_product_by_id(product_id)
    if not product:
        app.logger.warning(f"Produit avec ID {product_id} introuvable.")
        return jsonify({"error": "Produit introuvable"}), 404

    # Récupérer les données de la requête
    data = request.form.to_dict()
    files = request.files.getlist("images")

    # Nouvelle logique : ne sauvegarde rien localement, juste génère les URLs CDN
    image_paths = product.get("images", [])
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # L'admin doit uploader l'image sur GitHub séparément !
            image_paths.append(f"{CDN_PREFIX}{filename}")
        else:
            return jsonify({"error": f"Fichier invalide ou non autorisé : {file.filename}"}), 400

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

    product['images'] = image_paths

    updated = update_product_in_mockapi(product_id, product)
    if not updated:
        return jsonify({"error": "Erreur lors de la sauvegarde sur MockAPI."}), 500

    app.logger.info(f"Produit {product_id} mis à jour avec succès.")
    cache.delete('products')
    return jsonify({"message": "Produit mis à jour avec succès", "product": updated}), 200

@cache.cached(timeout=120)
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

    # Nouvelle logique : ne sauvegarde rien localement, juste génère les URLs CDN
    image_paths = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # L'admin doit uploader l'image sur GitHub séparément !
            image_paths.append(f"{CDN_PREFIX}{filename}")
        else:
            return jsonify({"error": f"Fichier invalide : {file.filename}"}), 400

    slug = slugify(data['name'])
    new_product = {
        "name": data['name'],
        "short_description": data.get('short_description', ''),
        "description": data['description'],
        "price": int(data['price']),
        "old_price": int(data.get('old_price', 0)) if data.get('old_price') else None,
        "currency": data['currency'],
        "images": image_paths,
        "resource_file_id": json.loads(data.get('resource_file_id', '[]')),
        "featured": data.get('featured', False) == 'true',
        "badges": json.loads(data.get('badges', '[]')),
        "category": data['category'],
        "stock": int(data['stock']),
        "sku": data.get('sku', ''),
        "faq": json.loads(data.get('faq', '[]')),
        "slug": slug
    }

    created = add_product_to_mockapi(new_product)
    if not created:
        return jsonify({"error": "Erreur lors de l'ajout du produit."}), 500

    cache.delete('products')
    return jsonify({"message": "Produit ajouté avec succès.", "product": created}), 201


@app.route('/admin/products/manage/<int:product_id>/image/delete', methods=['POST'])
def delete_product_image(product_id):
    """
    Supprime une image spécifique d'un produit.
    """
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403

    # Charger les produits existants
    try:
        products = fetch_products()
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "Fichier introuvable ou JSON invalide"}), 500

    # Trouver le produit correspondant
    product = fetch_product_by_id(product_id)
    if not product:
        return jsonify({"error": "Produit introuvable"}), 404

    data = request.get_json()
    image_url = data.get('imageUrl')
    if not image_url or image_url not in product.get('images', []):
        return jsonify({"error": "Image introuvable ou non associée à ce produit."}), 400

    try:
        product['images'].remove(image_url)
                # SUPPRIMER TOUTE LOGIQUE QUI SUPPRIME UN FICHIER LOCAL
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la suppression de l'image : {str(e)}"}), 500

    updated = update_product_in_mockapi(product_id, product)
    if not updated:
        return jsonify({"error": "Erreur lors de la sauvegarde sur MockAPI."}), 500

    cache.delete('products')
    return jsonify({"message": "Image supprimée avec succès.", "product": updated}), 200



@app.route('/admin/products/manage/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """
    Supprime un produit par son ID.
    """
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403

    deleted = delete_product_from_mockapi(product_id)
    if not deleted:
        return jsonify({"error": "Produit introuvable ou erreur MockAPI"}), 404
    cache.delete('products')
    return jsonify({"message": "Produit supprimé avec succès."}), 200


"""
FIN PRODUIT
"""

ANNOUNCEMENTS_URL = "https://6840a10f5b39a8039a58afb0.mockapi.io/api/externalapi/annoucements"


@cache.cached(timeout=300, key_prefix="announcements")
def fetch_announcements():
    """Récupère toutes les annonces depuis MockAPI (avec cache Flask)"""
    r = requests.get(ANNOUNCEMENTS_URL, timeout=5)
    return r.json()

@app.route('/api/announcements')
def api_announcements():
    return jsonify(fetch_announcements())

@app.route('/api/announcements/active')
def api_announcements_active():
    # Utilise le cache RAM pour éviter un appel API à chaque fois
    announcements = fetch_announcements()
    # Filtre côté Python pour ne garder que les actifs
    active = [a for a in announcements if a.get('active') is True]
    return jsonify(active)
@cache.cached(timeout=120)
@app.route('/admin/announcements', methods=['GET'])
def admin_announcements():
    """
    Page de gestion des annonces dans l'admin dashboard.
    """
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))

    log_action("view_announcements_page", {"username": session.get('username')})

    return render_template('admin_announcements.html')

@app.route('/api/announcements', methods=['POST'])
def api_announcements_post():
    data = request.json
    r = requests.post(ANNOUNCEMENTS_URL, json=data)
    cache.delete('announcements')
    return (r.text, r.status_code, {'Content-Type': 'application/json'})

@app.route('/api/announcements/<id>', methods=['PUT'])
def api_announcements_put(id):
    data = request.json
    r = requests.put(f"{ANNOUNCEMENTS_URL}/{id}", json=data)
    cache.delete('announcements')
    return (r.text, r.status_code, {'Content-Type': 'application/json'})

@app.route('/api/announcements/<id>', methods=['DELETE'])
def api_announcements_delete(id):
    r = requests.delete(f"{ANNOUNCEMENTS_URL}/{id}")
    cache.delete('announcements')
    return (r.text, r.status_code, {'Content-Type': 'application/json'})
@cache.cached(timeout=120)
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


@app.route('/sitemap.xml')
def sitemap():
    pages = [
        {"loc": url_for('home', _external=True), "priority": "1.0", "changefreq": "daily"},
        {"loc": url_for('produits', _external=True), "priority": "0.8", "changefreq": "weekly"}
    ]
    produits = fetch_products()
    for produit in produits:
        pages.append({
            "loc": url_for('product_detail', slug=slugify(produit['name']), _external=True),
            "priority": "0.6",
            "changefreq": "weekly"
        })

    sitemap_xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for page in pages:
        sitemap_xml.append(f"<url><loc>{page['loc']}</loc><changefreq>{page['changefreq']}</changefreq><priority>{page['priority']}</priority></url>")
    sitemap_xml.append("</urlset>")
    return Response("\n".join(sitemap_xml), mimetype="application/xml")


@app.route('/robots.txt')
def robots_txt():
    lines = [
        "User-agent: *",
        "Disallow: /admin",
        "Disallow: /k4d3t",
        "Disallow: /admin/",
        "Disallow: /k4d3t/",
        "Disallow: /settings/",
        "Allow: /",
        f"Sitemap: {url_for('sitemap', _external=True)}"
    ]
    return Response("\n".join(lines), mimetype="text/plain")
@cache.cached(timeout=120)
@app.errorhandler(404)
def page_not_found(e):
    context = get_seo_context(
        meta_title="Erreur 404 - Page non trouvée | Digital Adept™",
        meta_description="Raté 😬! Cette page n’existe pas. Elle a peut-être été supprimée",
        meta_robots="noindex, follow",
        meta_breadcrumb_jsonld=make_breadcrumb(
            ("Accueil", url_for('home', _external=True))
        )
    )
    return render_template("404.html", **context), 404
@cache.cached(timeout=120)
@app.errorhandler(500)
def server_error(e):
    logging.error(f"500 Internal Server Error: {request.path}", exc_info=True)
    return render_template("500.html"), 500

@app.route('/health')
def health():
    return {"status": "ok", "uptime": "100%", "products_count": len(fetch_products())}, 200

if __name__ == '__main__':
    #threading.Thread(target=periodic_ping, daemon=True).start()
    port = int(os.environ.get('PORT', 5005))  # Utilise le PORT de Railway ou 5005 en local
    app.run(host='0.0.0.0', port=port, debug=True)

