from flask import Flask, render_template, jsonify, request, redirect, url_for, abort, session, flash, send_file, Response
import json
import os
from datetime import datetime, timezone, timedelta
import uuid  
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
from sqlalchemy.orm import joinedload
import logging
from flask_sqlalchemy import SQLAlchemy
from models import *

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


# Configuration Railway/PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,  # recycle connexions toutes les 5 min
}


# Initialisation SQLAlchemy
db.init_app(app)
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
        meta_jsonld=json.dumps(meta_jsonld, ensure_ascii=False) if isinstance(meta_jsonld, (dict, list)) else meta_jsonld,
        meta_breadcrumb_jsonld=json.dumps(meta_breadcrumb_jsonld, ensure_ascii=False) if isinstance(meta_breadcrumb_jsonld, (dict, list)) else meta_breadcrumb_jsonld,
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

PRODUIT_CACHE = fetch_products()

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
@cache.cached(timeout=300)
@app.route('/')
def home():
    # --- OPTIMISATION : Chargement anticipé des relations ---
    produits = Product.query.options(
        joinedload(Product.images),
        joinedload(Product.badges)
    ).all()
    
    produits_vedette = [p for p in produits if p.featured]

    # --- JSON-LD AMÉLIORÉ POUR LE SITE WEB ---
    website_jsonld = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Digital Adept™",
        "url": url_for('home', _external=True),
        "description": "La meilleure boutique africaine de produits digitaux, logiciels, services et astuces pour booster, démarrer ou commencer votre business en ligne.",
        "inLanguage": "fr",
        # AJOUT : Indique à Google comment afficher une barre de recherche pour votre site
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": url_for('produits', _external=True) + "?q={search_term_string}"
            },
            "query-input": "required name=search_term_string"
        }
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
        og_image=url_for('static', filename='img/logo.webp', _external=True),
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
@cache.cached(timeout=300)
@app.route('/produits')
def produits():
    # --- OPTIMISATION : Chargement anticipé des relations ---
    produits = Product.query.options(
        joinedload(Product.images),
        joinedload(Product.badges)
    ).all()
    
    context = get_seo_context(
        meta_title="Tous les produits - Digital Adept™",
        meta_description="Liste complète de tous les produits digitaux, logiciels, ebooks et services disponibles.",
        og_image=url_for('static', filename='img/logo.webp', _external=True),
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
    
@cache.cached(timeout=300)
@app.route('/produit/<slug>')
def product_detail(slug):
    produit = Product.query.options(
        joinedload(Product.images),
        joinedload(Product.badges),
        joinedload(Product.faqs),
        joinedload(Product.comments)
    ).filter_by(slug=slug).first()

    if not produit:
        # ... (gestion 404)
        pass

    # Calcul de la note moyenne et du nombre d'avis
    produit_comments = produit.comments
    ratings = [c.rating for c in produit_comments if c.rating is not None]
    reviews_count = len(ratings)
    average_rating = round(sum(ratings) / reviews_count, 2) if reviews_count > 0 else 0

    produits = Product.query.all()

    context = get_seo_context(
        meta_title=f"{produit.name} - Digital Adept™",
        meta_description=produit.short_description or "Découvrez ce produit digital sur Digital Adept.",
        og_image=produit.images[0].url if produit.images else url_for('static', filename='img/logo.png', _external=True),
        meta_keywords=f"{produit.name}, digital, boutique",
        meta_jsonld={
            "@context": "https://schema.org",
            "@type": "Product",
            "name": produit.name,
            "image": [img.url for img in produit.images],
            "description": produit.short_description,
            "brand": "Digital Adept™",
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": average_rating,
                "reviewCount": reviews_count
            } if reviews_count > 0 else None,
            "offers": {
                "@type": "Offer",
                "price": produit.price,
                "priceCurrency": produit.currency,
                "availability": "https://schema.org/InStock" if produit.stock > 0 else "https://schema.org/OutOfStock"
            }
        },
        meta_breadcrumb_jsonld=make_breadcrumb(
            ("Accueil", url_for('home', _external=True)),
            ("Produits", url_for('produits', _external=True)),
            (produit.name, url_for('product_detail', slug=produit.slug, _external=True)),
        ),
        extra_vars={
            "produit": produit,
            "comments": produit_comments,
            "produits": produits,
            "rating": average_rating,
            "reviews_count": reviews_count
        }
    )
    return render_template('product.html', **context)


@app.route('/produit/<slug>/comment', methods=['POST'])
def add_comment(slug):
    produit = Product.query.filter_by(slug=slug).first_or_404()
    comment_text = request.form.get("comment")
    rating = request.form.get("rating")
    if not comment_text or not rating:
        abort(400, "Le commentaire et la note sont obligatoires.")

    comment = Comment(
        product_id=produit.id,
        comment=comment_text,
        rating=int(rating),
        date=datetime.now(timezone.utc)
    )
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('product_detail', slug=slug))

# --- Routes API ---
@app.route('/api/produits')
def api_produits():
    produits = Product.query.all()
    def product_to_dict(p):
        return {
            "id": p.id,
            "name": p.name,
            "short_description": p.short_description,
            "description": p.description,
            "price": p.price,
            "old_price": p.old_price,
            "currency": p.currency,
            "featured": p.featured,
            "category": p.category,
            "stock": p.stock,
            "sku": p.sku,
            "slug": p.slug,
            "images": [img.url for img in p.images],  # Si tu as une relation ProductImage
            "badges": [{"type": b.type, "text": b.text} for b in p.badges],
            "faq": [{"question": f.question, "answer": f.answer} for f in p.faqs],
            "resource_files": [{"type": r.type, "url": r.url, "file_id": r.file_id} for r in p.resource_files],
        }
    return jsonify([product_to_dict(produit) for produit in produits])

@app.route('/api/product/<int:product_id>/comments', methods=['GET'])
def get_product_comments(product_id):
    comments = Comment.query.filter_by(product_id=product_id).order_by(Comment.date.desc()).all()
    def comment_to_dict(c):
        return {
            "id": c.id,
            "product_id": c.product_id,
            "comment": c.comment,
            "rating": c.rating,
            "date": c.date.isoformat(),
        }
    return jsonify([comment_to_dict(comment) for comment in comments])
    
# NOUVELLE ROUTE API POUR LA NOTATION
@app.route('/api/produit/<int:product_id>/rate', methods=['POST'])
def rate_product(product_id):
    data = request.get_json()
    rating = data.get('rating')

    if not rating or not (1 <= int(rating) <= 5):
        return jsonify({"error": "Une note valide (1-5) est requise."}), 400

    produit = Product.query.get(product_id)
    if not produit:
        return jsonify({"error": "Produit introuvable."}), 404

    # CORRECTION: On utilise une chaîne vide au lieu de None pour respecter la contrainte NOT NULL
    new_rating = Comment(
        product_id=product_id,
        rating=int(rating),
        comment="",  # Correction ici
        date=datetime.now(timezone.utc)
    )
    db.session.add(new_rating)
    db.session.commit()

    # Recalculer la moyenne et le nombre d'avis
    all_ratings = [c.rating for c in produit.comments if c.rating is not None]
    reviews_count = len(all_ratings)
    average_rating = sum(all_ratings) / reviews_count if reviews_count > 0 else 0

    # Invalider le cache de la page produit pour refléter la nouvelle note
    cache.delete_memoized(product_detail, slug=produit.slug)

    return jsonify({
        "message": "Vote enregistré !",
        "average_rating": average_rating,
        "reviews_count": reviews_count
    })

@cache.cached(timeout=300)
@app.route('/contact')
def contact():
    context = get_seo_context(
        meta_title="Contactez-nous - Digital Adept™",
        meta_description="Besoin d'informations ou d'aide ? Contactez l'équipe Digital Adept™.",
        og_image=url_for('static', filename='img/logo.webp', _external=True),
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
    Reçoit les données du frontend, les transmet à MoneyFusion et renvoie la réponse.
    """
    data = request.json
    MONEYFUSION_API_URL = "https://www.pay.moneyfusion.net/Digital_Adept/a5f4d44ad70069fa/pay/"
    
    # Log pour voir ce qu'on envoie (utile pour le débogage)
    logging.info(f"Payload envoyé à MoneyFusion: {data}")

    try:
        response = requests.post(MONEYFUSION_API_URL, json=data, timeout=15)
        
        # Log de la réponse brute
        logging.info(f"Réponse brute de MoneyFusion: {response.status_code} '{response.text}'")

        response.raise_for_status()  # Lève une exception pour les erreurs HTTP (4xx, 5xx)
        response_data = response.json()

        # Si MoneyFusion renvoie un statut "false"
        if not response_data.get("statut"):
            return jsonify({"error": response_data.get("message", "Erreur inconnue de l'API de paiement.")}), 400
        
        # Si tout est OK, on renvoie la réponse complète de MoneyFusion
        return jsonify(response_data), 200

    except requests.exceptions.Timeout:
        logging.error("Timeout en contactant MoneyFusion.")
        return jsonify({"error": "Le service de paiement a mis trop de temps à répondre."}), 504
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur de connexion à MoneyFusion: {e}")
        return jsonify({"error": "Impossible de contacter le service de paiement."}), 503
    except json.JSONDecodeError:
        logging.error(f"Réponse non-JSON de MoneyFusion: {response.text}")
        return jsonify({"error": "Réponse invalide du service de paiement."}), 502
    except Exception as e:
        logging.error(f"Erreur inattendue dans /payer: {e}")
        return jsonify({"error": "Une erreur serveur interne est survenue."}), 500


@app.route('/api/checkout/prepare', methods=['POST'])
def prepare_checkout():
    data = request.json
    email = data.get('email')
    cart_items = data.get('cart')
    nom_client = data.get('nom_client')
    total_price = data.get('totalPrice')
    whatsapp = data.get('whatsapp') # <--- Nouvelle ligne

    if not email or not cart_items:
        return jsonify({"error": "Email et contenu du panier sont requis."}), 400

    # Enregistre le panier abandonné dans la base de données
    abandoned_cart = AbandonedCart(
        email=email,
        customer_name=nom_client,
        cart_content=cart_items,
        total_price=total_price,
        whatsapp_number=whatsapp  # <--- Nouvelle ligne
    )
    db.session.add(abandoned_cart)
    db.session.commit()

    # On renvoie un statut de succès pour que le frontend continue
    return jsonify({"status": "prepared", "cart_id": abandoned_cart.id}), 200

# --- WEBHOOK MIS À JOUR (LOGIQUE FIABLE) ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    # On vérifie que le paiement est réussi et qu'on a les infos nécessaires
    if data.get('statut') == 'paid' and 'personal_Info' in data:
        order_id_str = data['personal_Info'][0].get('orderId')
        
        if order_id_str and order_id_str.startswith('cart_'):
            try:
                cart_id = int(order_id_str.split('_')[1])
                cart = AbandonedCart.query.get(cart_id)

                # On vérifie que le panier existe et n'a pas déjà été traité
                if cart and cart.status != 'completed':
                    cart.status = 'completed' # On marque comme complété

                    # --- LOGIQUE DE GÉNÉRATION DES LIENS DE TÉLÉCHARGEMENT SÉCURISÉS ---
                    product_names = [item['name'] for item in cart.cart_content]
                    products_from_db = Product.query.filter(Product.name.in_(product_names)).all()
                    
                    download_links_html = ""
                    for product in products_from_db:
                        if product.resource_files:
                            # 1. Créer un token de téléchargement unique pour ce produit et cet achat
                            download_token = str(uuid.uuid4())
                            expiration_date = datetime.now(timezone.utc) + timedelta(days=7) # Liens valables 7 jours

                            new_download = DownloadLink(
                                product_id=product.id,
                                cart_id=cart.id,
                                token=download_token,
                                expires_at=expiration_date
                            )
                            db.session.add(new_download)
                            
                            # 2. Construire l'URL de téléchargement avec ce token
                            link_url = url_for('download_file', token=download_token, _external=True)
                            download_links_html += f"<li><b>{product.name}</b>: <a href='{link_url}'>Télécharger ici</a></li>"

                    db.session.commit() # On sauvegarde le nouveau statut du panier et les tokens de téléchargement

                    # 3. Envoyer l'e-mail avec les liens uniques générés
                    if download_links_html:
                        email_subject = "Confirmation de votre commande et liens de téléchargement"
                        email_body = f"""
                        <html>
                            <body style="font-family: Arial, sans-serif; color: #333;">
                                <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                                    <h1 style="color: #1976d2;">Merci pour votre achat !</h1>
                                    <p>Bonjour {cart.customer_name or 'cher client'},</p>
                                    <p>Votre commande a été validée. Vous pouvez accéder à vos produits en utilisant les liens ci-dessous. Ces liens sont personnels et valables 7 jours :</p>
                                    <ul style="list-style: none; padding: 0;">
                                        {download_links_html}
                                    </ul>
                                    <p>Conservez cet e-mail pour accéder à vos produits.</p>
                                    <p>L'équipe Digital Adept.</p>
                                </div>
                            </body>
                        </html>
                        """
                        threading.Thread(target=send_email, args=(cart.email, email_subject, email_body)).start()

            except Exception as e:
                logging.error(f"Erreur critique dans le webhook: {e}")
                db.session.rollback() # En cas d'erreur, on annule les changements
    
    return "", 200
    
@cache.cached(timeout=300)
@app.route("/callback")
def callback():
    """
    Page de retour générique après le paiement.
    Le traitement réel est géré par le webhook. Cette page informe simplement l'utilisateur.
    """
    # On peut récupérer le token pour l'afficher à l'utilisateur s'il a besoin de contacter le support
    transaction_token = request.args.get("token")

    context = get_seo_context(
        meta_title="Paiement en cours de validation - Digital Adept™",
        meta_description="Votre paiement est en cours de validation. Vous recevrez vos produits par e-mail dans quelques instants.",
        meta_robots="noindex, nofollow" # On ne veut pas que cette page soit indexée
    )
    # On passe le token au template, au cas où
    context['transaction_token'] = transaction_token 

    return render_template("callback.html", **context)
     
# --- NOUVELLE ROUTE POUR LE TÉLÉCHARGEMENT SÉCURISÉ ---
def get_telegram_file_link(file_id):
    """
    Récupère le lien de téléchargement temporaire d'un fichier depuis l'API Telegram.
    Ces liens sont généralement valables 1 heure.
    """
    token = os.environ.get('MESSAGES_BOT_TOKEN')
    if not token:
        logging.error("Token du bot Telegram (MESSAGES_BOT_TOKEN) manquant.")
        return None
    
    url = f"https://api.telegram.org/bot{token}/getFile"
    try:
        response = requests.post(url, json={"file_id": file_id}, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            file_path = data["result"]["file_path"]
            # Construit l'URL complète de téléchargement du fichier
            return f"https://api.telegram.org/file/bot{token}/{file_path}"
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur API Telegram pour getFile (file_id: {file_id}): {e}")
    return None


@app.route('/download/<token>')
def download_file(token):
    link = DownloadLink.query.filter_by(token=token).first()
    context = get_seo_context(
        meta_title="Votre téléchargement",
        meta_robots="noindex, nofollow"
    )

    if not link:
        context['error_message'] = "Ce lien de téléchargement est invalide ou n'existe plus."
        return render_template("download.html", **context), 404

    now_utc = datetime.now(timezone.utc)
    expires_at_aware = link.expires_at
    if expires_at_aware.tzinfo is None:
        expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc)

    if expires_at_aware < now_utc:
        context['error_message'] = f"Ce lien de téléchargement a expiré le {expires_at_aware.strftime('%d/%m/%Y')}."
        return render_template("download.html", **context), 410

    product = Product.query.get(link.product_id)
    if not product or not product.resource_files:
        context['error_message'] = "Le produit associé à ce lien est introuvable."
        return render_template("download.html", **context), 404

    link.download_count += 1
    db.session.commit()

    # --- OPTIMISATION : Requêtes parallèles vers Telegram ---
    download_urls = [None] * len(product.resource_files)
    threads = []

    def fetch_link(index, resource_file):
        temp_link = get_telegram_file_link(resource_file.file_id)
        if temp_link:
            file_name = product.name if len(product.resource_files) == 1 else f"{product.name} - Partie {index + 1}"
            download_urls[index] = {"name": file_name, "url": temp_link}

    for i, resource_file in enumerate(product.resource_files):
        thread = threading.Thread(target=fetch_link, args=(i, resource_file))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join() # On attend que toutes les requêtes finissent

    # Filtrer les résultats None si une requête a échoué
    final_download_urls = [url for url in download_urls if url is not None]
    # --- FIN DE L'OPTIMISATION ---

    if not final_download_urls:
        context['error_message'] = "Impossible de générer les liens de téléchargement pour le moment. Veuillez contacter le support."
        return render_template("download.html", **context), 500

    context['product'] = product
    context['download_urls'] = final_download_urls
    return render_template("download.html", **context)

@cache.cached(timeout=300)
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

# --- NOUVELLE FONCTION DE DÉMARRAGE POUR INITIALISER LES RÔLES/TUILES ---
def initialize_database():
    """Crée les rôles, tuiles, permissions et l'admin par défaut."""
    
    # 1. Créer le rôle super_admin (uniquement)
    if not Role.query.filter_by(name='super_admin').first():
        db.session.add(Role(name='super_admin'))
        db.session.commit()

    # 2. Créer les Tuiles par défaut
    default_tiles = [
        {'name': 'Produits', 'endpoint': 'admin_products_page', 'description': 'Gérer les produits du site.'},
        {'name': 'Annonces', 'endpoint': 'admin_announcements', 'description': 'Gérer les annonces et bannières.'},
        {'name': 'Marketing', 'endpoint': 'admin_marketing', 'description': 'Suivre les paniers abandonnés.'},
        {'name': 'Commentaires', 'endpoint': 'admin_comments_page', 'description': 'Modérer les commentaires.'},
        {'name': 'Suivi', 'endpoint': 'admin_suivi', 'description': "Voir le chiffre d'affaires."}
    ]
    for tile_data in default_tiles:
        if not Tile.query.filter_by(endpoint=tile_data['endpoint']).first():
            db.session.add(Tile(**tile_data))
    db.session.commit()

    # 3. Assigner TOUTES les tuiles au super_admin (manière robuste)
    super_admin_role = Role.query.filter_by(name='super_admin').first()
    if super_admin_role:
        all_tiles = Tile.query.all()
        # On utilise un set pour éviter les doublons et être efficace
        current_tile_ids = {tile.id for tile in super_admin_role.tiles}
        for tile in all_tiles:
            if tile.id not in current_tile_ids:
                super_admin_role.tiles.append(tile)
        db.session.commit()

    # 4. Créer l'utilisateur Super Admin 'k4d3t' s'il n'existe pas
    if not User.query.filter_by(username='k4d3t').first() and super_admin_role:
        hashed_password = bcrypt.hashpw("spacekali".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        admin_user = User(
            username='k4d3t', 
            password=hashed_password, 
            role_id=super_admin_role.id, 
            revenue_share_percentage=100
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Utilisateur super_admin 'k4d3t' créé avec succès.")

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
    return session.get('role') == 'super_admin'
    
@cache.cached(timeout=300)
@app.route('/k4d3t', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        flash("Vous êtes déjà connecté.", "info")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password.startswith('$2b$') and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            session['admin_logged_in'] = True
            session['username'] = user.username
            session['role'] = user.role.name
            flash("Connexion réussie !", "success")
            return redirect(url_for('admin_dashboard'))
        flash("Identifiants invalides. Réessayez.", "error")

    return render_template('admin_login.html')
    
@cache.cached(timeout=300)
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

@app.route('/k4d3t/settings', methods=['GET'])
def admin_settings():
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))
    # Affiche simplement la page de navigation des paramètres, sans charger de données.
    return render_template('admin_settings.html')


@app.route('/k4d3t/settings/users', methods=['GET', 'POST'])
def admin_settings_users():
    """
    Page pour gérer les administrateurs et leurs rôles.
    Accessible uniquement au super_admin.
    """
    if session.get('role') != 'super_admin':
        log_action("unauthorized_access_attempt", {"path": "/k4d3t/settings/users"})
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        # Récupérer les données du formulaire
        username = request.form.get('username')
        password = request.form.get('password')
        # CORRECTION : On récupère role_id, qui est un ID numérique
        role_id = request.form.get('role_id')
        revenue_share = request.form.get('revenue_share', 0)

        # Validation des champs
        if not username or not password or not role_id:
            flash("Nom d'utilisateur, mot de passe et rôle sont requis.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Ce nom d'utilisateur est déjà pris.", "error")
        else:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            # CORRECTION : On utilise role_id et revenue_share_percentage
            user = User(
                username=username, 
                password=hashed_password, 
                role_id=int(role_id),
                revenue_share_percentage=float(revenue_share)
            )
            db.session.add(user)
            db.session.commit()
            flash("Nouvel administrateur ajouté avec succès.", "success")
        
        # On redirige dans tous les cas après un POST pour éviter le re-POST au refresh
        return redirect(url_for('admin_settings_users'))

    users = User.query.options(joinedload(User.role)).all()
    # CORRECTION : On passe la liste des rôles au template pour le sélecteur
    roles = Role.query.order_by(Role.name).all()
    return render_template('admin_settings_users.html', users=users, roles=roles)

@app.route('/k4d3t/settings/users/edit/<username>', methods=['POST'])
def edit_user(username):
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        return {"status": "error", "message": "Accès non autorisé"}, 403
    data = request.json
    new_username = data.get('new_username')
    new_role = data.get('new_role')
    user = User.query.filter_by(username=username).first()
    if not user:
        return {"status": "error", "message": "Utilisateur introuvable"}, 404
    if not new_username or not new_role:
        return {"status": "error", "message": "Les champs nom d'utilisateur et rôle sont requis"}, 400
    if new_username != username and User.query.filter_by(username=new_username).first():
        return {"status": "error", "message": "Nom d'utilisateur déjà pris"}, 409
    user.username = new_username
    user.role = new_role
    db.session.commit()
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

@cache.cached(timeout=300)
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

# Dans project/site.py
# AJOUTEZ CETTE NOUVELLE ROUTE

@app.route('/k4d3t/relaunch-settings', methods=['GET', 'POST'])
def admin_relaunch_settings():
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        # Sauvegarde des données du formulaire
        for key, value in request.form.items():
            setting = SiteSetting.query.filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                db.session.add(SiteSetting(key=key, value=value))
        db.session.commit()
        flash("Paramètres de relance mis à jour.", "success")
        return redirect(url_for('admin_relaunch_settings'))

    # Affichage de la page avec les valeurs actuelles
    settings = {s.key: s.value for s in SiteSetting.query.all()}
    return render_template('admin_relaunch_settings.html', settings=settings)

@app.route('/k4d3t/settings/users/delete/<username>', methods=['POST'])
def delete_user(username):
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))
    user = User.query.filter_by(username=username).first()
    if not user:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for('admin_settings_users'))
    db.session.delete(user)
    db.session.commit()
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
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 401
    products = Product.query.all()
    def to_dict(p):
        return {
            "id": p.id,
            "name": p.name,
            "short_description": p.short_description,
            "description": p.description,
            "price": p.price,
            "old_price": p.old_price,
            "currency": p.currency,
            "featured": p.featured,
            "category": p.category,
            "stock": p.stock,
            "sku": p.sku,
            "slug": p.slug,
            "images": [img.url for img in p.images],  # Si tu as une relation ProductImage
            "badges": [{"type": b.type, "text": b.text} for b in p.badges],
            "faq": [{"question": f.question, "answer": f.answer} for f in p.faqs],
            "resource_files": [{"type": r.type, "url": r.url, "file_id": r.file_id} for r in p.resource_files],
        }
    return jsonify([to_dict(prod) for prod in products])
    
@cache.cached(timeout=300)
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
@cache.cached(timeout=300)
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
    
@cache.cached(timeout=300)
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
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 401
    product = Product.query.get_or_404(product_id)
    def to_dict(p):
        return {
            "id": p.id,
            "name": p.name,
            "short_description": p.short_description,
            "description": p.description,
            "price": p.price,
            "old_price": p.old_price,
            "currency": p.currency,
            "featured": p.featured,
            "category": p.category,
            "stock": p.stock,
            "sku": p.sku,
            "slug": p.slug,
            "images": [img.url for img in p.images],
            "badges": [{"type": b.type, "text": b.text} for b in p.badges],
            "faq": [{"question": f.question, "answer": f.answer} for f in p.faqs],
            "resource_files": [{"type": r.type, "url": r.url, "file_id": r.file_id} for r in p.resource_files],
        }
    return jsonify(to_dict(product)), 200

@app.route('/admin/products/manage/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403
    product = Product.query.get_or_404(product_id)
    data = request.form.to_dict()
    files = request.files.getlist("images")

    # Màj champs principaux
    for field in ['name', 'short_description', 'description', 'price', 'old_price', 'currency', 'featured', 'category', 'stock', 'sku']:
        if field in data:
            # Convert types si besoin
            if field in ['price', 'old_price', 'stock']:
                try:
                    setattr(product, field, int(data[field]))
                except Exception:
                    pass
            elif field == "featured":
                setattr(product, field, data[field] == "true" or data[field] == "on")
            else:
                setattr(product, field, data[field])
    # Slug : regénérer si name changé ou reçu explicitement
    if "slug" in data:
        product.slug = data["slug"]

    db.session.commit()

    # Images (ajout seulement)
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            url = f"{CDN_PREFIX}{filename}"
            image = ProductImage(product_id=product.id, url=url)
            db.session.add(image)

    # Badges (remplace tout)
    ProductBadge.query.filter_by(product_id=product.id).delete()
    try:
        badges = json.loads(data.get("badges", "[]"))
    except Exception:
        badges = []
    for badge in badges:
        db.session.add(ProductBadge(
            product_id=product.id,
            type=badge.get("type", ""),
            text=badge.get("text", "")
        ))

    # FAQ (remplace tout)
    ProductFAQ.query.filter_by(product_id=product.id).delete()
    try:
        faq = json.loads(data.get("faq", "[]"))
    except Exception:
        faq = []
    for item in faq:
        db.session.add(ProductFAQ(
            product_id=product.id,
            question=item.get("question", ""),
            answer=item.get("answer", "")
        ))

    # Resource Files (remplace tout)
    ProductResourceFile.query.filter_by(product_id=product.id).delete()
    try:
        resource_files = json.loads(data.get("resource_file_id", "[]"))
    except Exception:
        resource_files = []
    if not isinstance(resource_files, list):
        resource_files = [resource_files]
    for rf in resource_files:
        if isinstance(rf, dict):
            db.session.add(ProductResourceFile(
                product_id=product.id,
                type=rf.get('type'),
                url=rf.get('url'),
                file_id=rf.get('file_id')
            ))
        elif isinstance(rf, str) and rf.strip():
            db.session.add(ProductResourceFile(
                product_id=product.id,
                file_id=rf
            ))

    db.session.commit()
    return jsonify({"message": "Produit mis à jour avec succès"}), 200

import json
@cache.cached(timeout=300)
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
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403

    data = request.form.to_dict()
    files = request.files.getlist("images")
    required_fields = ['name', 'description', 'price', 'currency', 'category', 'stock']
    for field in required_fields:
        if not data.get(field):
            return jsonify({"error": f"Le champ '{field}' est requis."}), 400

    existing = Product.query.filter_by(slug=slugify(data['name'])).first()
    if existing:
        return jsonify({"error": f"Un produit avec le slug '{slugify(data['name'])}' existe déjà. Change le nom du produit."}), 400

    # Correction: bien parser featured (bool JS -> bool Python)
    featured = str(data.get('featured', '')).lower() in ['true', 'on', '1']

    produit = Product(
        name=data['name'],
        short_description=data.get('short_description', ''),
        description=data['description'],
        price=int(data['price']),
        old_price=int(data.get('old_price', 0)) if data.get('old_price') else None,
        currency=data['currency'],
        featured=featured,
        category=data['category'],
        stock=int(data['stock']),
        sku=data.get('sku', ''),
        slug=slugify(data['name'])
    )
    db.session.add(produit)
    db.session.flush()  # Pour récupérer produit.id sans commit

    # Images
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            url = f"{CDN_PREFIX}{filename}"
            image = ProductImage(product_id=produit.id, url=url)
            db.session.add(image)

    # Badges
    try:
        badges = json.loads(data.get('badges', '[]'))
    except Exception:
        badges = []
    for badge in badges:
        db.session.add(ProductBadge(
            product_id=produit.id,
            type=badge.get('type', ''),
            text=badge.get('text', '')
        ))

    # FAQ
    try:
        faqs = json.loads(data.get('faq', '[]'))
    except Exception:
        faqs = []
    for faq in faqs:
        db.session.add(ProductFAQ(
            product_id=produit.id,
            question=faq.get('question', ''),
            answer=faq.get('answer', '')
        ))

    # Resource files
    try:
        resource_files = json.loads(data.get('resource_file_id', '[]'))
    except Exception:
        resource_files = []
    if not isinstance(resource_files, list):
        resource_files = [resource_files]
    for rf in resource_files:
        if isinstance(rf, dict):
            db.session.add(ProductResourceFile(
                product_id=produit.id,
                type=rf.get('type'),
                url=rf.get('url'),
                file_id=rf.get('file_id')
            ))
        elif isinstance(rf, str) and rf.strip():
            db.session.add(ProductResourceFile(
                product_id=produit.id,
                file_id=rf
            ))

    db.session.commit()
    return jsonify({"message": "Produit ajouté avec succès.", "id": produit.id}), 201


@app.route('/admin/products/manage/<int:product_id>/image/delete', methods=['POST'])
def delete_product_image(product_id):
    """
    Supprime une image spécifique d'un produit (en base de données).
    """
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403

    from sqlalchemy.orm.exc import NoResultFound

    data = request.get_json()
    image_url = data.get('imageUrl')
    if not image_url:
        return jsonify({"error": "Aucune URL d'image fournie."}), 400

    # Vérifier que le produit existe
    produit = Product.query.get(product_id)
    if not produit:
        return jsonify({"error": "Produit introuvable"}), 404

    # Chercher l'image à supprimer
    image = ProductImage.query.filter_by(product_id=product_id, url=image_url).first()
    if not image:
        return jsonify({"error": "Image introuvable ou non associée à ce produit."}), 400

    try:
        db.session.delete(image)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur lors de la suppression de l'image : {str(e)}"}), 500

    return jsonify({"message": "Image supprimée avec succès."}), 200



@app.route('/admin/products/manage/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Produit supprimé avec succès"})

"""
FIN PRODUIT
"""

ANNOUNCEMENTS_URL = "https://6840a10f5b39a8039a58afb0.mockapi.io/api/externalapi/annoucements"

@app.route('/admin/marketing')
def admin_marketing():
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))

    # On récupère tous les paniers avec le statut "abandoned", les plus récents en premier
    abandoned_carts = AbandonedCart.query.filter_by(status='abandoned').order_by(AbandonedCart.created_at.desc()).all()

    return render_template('admin_marketing.html', carts=abandoned_carts)

@cache.cached(timeout=300, key_prefix="announcements")
@app.route('/api/announcements', methods=['GET'])
def api_announcements():
    """Récupère toutes les annonces depuis la base de données."""
    try:
        annonces = Announcement.query.order_by(Announcement.date.desc()).all()
        def to_dict(a):
            return {
                "id": a.id,
                "content": a.content,
                "date": a.date.isoformat(),
                "active": a.active,
                "type": a.type,
                "video_url": a.video_url,
                "btn_label": a.btn_label,
                "btn_url": a.btn_url
            }
        return jsonify([to_dict(a) for a in annonces])
    except Exception as e:
        logging.error(f"Erreur API GET annonces: {e}")
        return jsonify({"error": "Erreur serveur"}), 500
    
@app.route('/api/announcements/active', methods=['GET'])
@cache.cached(timeout=60) # On peut cacher cette route car elle est publique
def api_announcements_active():
    """Récupère uniquement les annonces actives."""
    try:
        annonces = Announcement.query.filter_by(active=True).order_by(Announcement.date.desc()).all()
        def to_dict(a):
            return {
                "id": a.id,
                "content": a.content,
                "date": a.date.isoformat(),
                "active": a.active,
                "type": a.type,
                "video_url": a.video_url,
                "btn_label": a.btn_label,
                "btn_url": a.btn_url
            }
        return jsonify([to_dict(a) for a in annonces])
    except Exception as e:
        logging.error(f"Erreur API GET annonces actives: {e}")
        return jsonify({"error": "Erreur serveur"}), 500
    
@cache.cached(timeout=300)
@app.route('/admin/announcements', methods=['GET'])
def admin_announcements():
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))

    annonces = Announcement.query.order_by(Announcement.date.desc()).all()
    return render_template('admin_announcements.html', annonces=annonces)

@app.route('/api/announcements', methods=['POST'])
def api_announcements_post():
    """Crée une nouvelle annonce dans la base de données."""
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403
    data = request.json
    if not data or not data.get('content'):
        return jsonify({"error": "Le contenu est obligatoire"}), 400
        
    annonce = Announcement(
        content=data.get("content"),
        date=datetime.now(timezone.utc),
        active=data.get("active", True),
        type=data.get("type", "info"),
        video_url=data.get("video_url"),
        btn_label=data.get("btn_label"),
        btn_url=data.get("btn_url")
    )
    db.session.add(annonce)
    db.session.commit()
    cache.delete_memoized(api_announcements_active) # Invalider le cache
    return jsonify({"message": "Annonce créée", "id": annonce.id}), 201


@app.route('/api/announcements/<int:id>', methods=['PUT'])
def api_announcements_put(id):
    """Met à jour une annonce existante."""
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403
    data = request.json
    annonce = Announcement.query.get_or_404(id)
    annonce.content = data.get("content", annonce.content)
    annonce.active = data.get("active", annonce.active)
    annonce.type = data.get("type", annonce.type)
    annonce.video_url = data.get("video_url", annonce.video_url)
    annonce.btn_label = data.get("btn_label", annonce.btn_label)
    annonce.btn_url = data.get("btn_url", annonce.btn_url)
    db.session.commit()
    cache.delete_memoized(api_announcements_active) # Invalider le cache
    return jsonify({"message": "Annonce mise à jour"})

@app.route('/api/announcements/<int:id>', methods=['DELETE'])
def api_announcements_delete(id):
    """Supprime une annonce."""
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403
    annonce = Announcement.query.get_or_404(id)
    db.session.delete(annonce)
    db.session.commit()
    cache.delete_memoized(api_announcements_active) # Invalider le cache
    return jsonify({"message": "Annonce supprimée"})
    
@cache.cached(timeout=300)
@app.route('/admin/comments')
def admin_comments_page():
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter pour accéder à cette page.", "error")
        return redirect(url_for('admin_login'))
    comments = Comment.query.order_by(Comment.date.desc()).all()
    log_action("view_comments", {"username": session.get('username')})
    return render_template('admin_comments.html', comments=comments)
    
@app.route('/admin/comments/data', methods=['GET'])
def admin_comments_data():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    filter_type = request.args.get('filter', 'all')
    page = int(request.args.get('page', 1))
    comments_per_page = 5

    query = Comment.query
    if filter_type == "unread":
        query = query.filter_by(is_read=False)
    elif filter_type == "read":
        query = query.filter_by(is_read=True)

    total = query.count()
    comments = query.order_by(Comment.date.desc()).offset((page - 1) * comments_per_page).limit(comments_per_page).all()

    def to_dict(comment):
        return {
            "id": comment.id,
            "product_id": comment.product_id,
            "content": comment.comment,
            "date": comment.date.isoformat(),
            "rating": comment.rating,
            "is_read": comment.is_read,
            "preview": (comment.comment or "")[:30] + "..."
        }

    return jsonify({"comments": [to_dict(c) for c in comments], "total": total})


@app.route('/admin/comments/<int:comment_id>', methods=['GET'])
def get_comment(comment_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    comment = Comment.query.get_or_404(comment_id)
    return jsonify({
        "id": comment.id,
        "product_id": comment.product_id,
        "content": comment.comment,
        "date": comment.date.isoformat(),
        "rating": comment.rating,
        "is_read": comment.is_read
    })
@app.route('/admin/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"message": "Commentaire supprimé avec succès"})


@app.route('/admin/comments/mark_as_read', methods=['POST'])
def mark_comment_as_read():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    comment_id = request.json.get("comment_id")
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"error": "Commentaire introuvable"}), 404
    comment.is_read = True
    db.session.commit()
    return jsonify({"message": "Commentaire marqué comme lu"})


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

# ... (à la place de votre fonction sitemap() actuelle) ...
@app.route('/sitemap.xml')
def sitemap():
    """
    Génère un sitemap.xml dynamique et complet à partir de la base de données.
    """
    pages = []
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # Pages statiques
    static_pages = ['home', 'produits', 'contact']
    for page_name in static_pages:
        pages.append({
            "loc": url_for(page_name, _external=True),
            "lastmod": now,
            "changefreq": "weekly",
            "priority": "0.8" if page_name != 'home' else "1.0"
        })

    # Pages des produits (dynamiques)
    produits = Product.query.order_by(Product.id.desc()).all()
    for produit in produits:
        entry = {
            "loc": url_for('product_detail', slug=produit.slug, _external=True),
            "changefreq": "monthly",
            "priority": "0.7"
        }
        # Si vous ajoutez une colonne `updated_at` à votre modèle Product,
        # vous pourrez l'utiliser ici pour une meilleure précision.
        # entry['lastmod'] = produit.updated_at.strftime('%Y-%m-%d')
        pages.append(entry)

    # Génération du XML
    sitemap_xml_content = render_template('sitemap.xml', pages=pages)
    return Response(sitemap_xml_content, mimetype="application/xml")


# ... (à la place de votre fonction robots_txt() actuelle) ...
@app.route('/robots.txt')
def robots_txt():
    """
    Génère un fichier robots.txt propre et sécurisé.
    """
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "# Pages d'administration à ne pas indexer",
        "Disallow: /k4d3t/",
        "Disallow: /admin/",
        "Disallow: /settings/",
        "",
        "# Fichiers sensibles",
        "Disallow: /*login",
        "Disallow: /*logout",
        "",
        f"Sitemap: {url_for('sitemap', _external=True)}"
    ]
    return Response("\n".join(lines), mimetype="text/plain")
@cache.cached(timeout=300)
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
@cache.cached(timeout=300)
@app.errorhandler(500)
def server_error(e):
    logging.error(f"500 Internal Server Error: {request.path}", exc_info=True)
    return render_template("500.html"), 500

@app.route('/health')
def health():
    return {"status": "ok", "uptime": "100%", "products_count": len(fetch_products())}, 200

# ... (n'importe où dans le fichier, par exemple après les autres routes admin)

# --- ROUTE DE RÉINITIALISATION (CORRIGÉE) ---
@app.route('/admin/settings/reset-database', methods=['POST'])
def reset_database_secure():
    if session.get('role') != 'super_admin':
        flash("Action non autorisée.", "error")
        return redirect(url_for('admin_dashboard'))

    try:
        db.drop_all()
        db.create_all()
        
        # CORRECTION : On appelle la fonction d'initialisation qui sait comment
        # créer les rôles, les tuiles ET l'utilisateur admin correctement.
        initialize_database()
        
        flash("La base de données a été réinitialisée avec succès.", "success")
        log_action("database_reset", {"user": session.get('username')})

    except Exception as e:
        logging.error(f"Erreur lors de la réinitialisation de la base de données : {e}", exc_info=True)
        flash(f"Une erreur est survenue lors de la réinitialisation : {e}", "error")

    return redirect(url_for('admin_settings'))

# Nouvelle fonction à ajouter
def send_email(receiver_email, subject, html_body):
    """Fonction centralisée pour envoyer des e-mails via l'API Brevo."""
    api_key = os.environ.get('BREVO_API_KEY')
    sender_email = os.environ.get('MAIL_USERNAME')

    if not api_key or not sender_email:
        logging.error("Configuration email (BREVO_API_KEY, MAIL_USERNAME) manquante.")
        return False

    api_url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    payload = {
        "sender": {"email": sender_email, "name": "Digital Adept"},
        "to": [{"email": receiver_email}],
        "subject": subject,
        "htmlContent": html_body
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()  # Lève une exception pour les erreurs HTTP (4xx ou 5xx)
        
        logging.info(f"Email envoyé via API à {receiver_email}. Statut: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur lors de l'envoi de l'email via API à {receiver_email}: {e}")
        if e.response is not None:
            logging.error(f"Détail de la réponse de l'API Brevo: {e.response.text}")
        return False

@app.route('/api/marketing/remind/<int:cart_id>', methods=['POST'])
def remind_abandoned_cart(cart_id):
    if not session.get('admin_logged_in'):
        return jsonify({"status": "error", "message": "Non autorisé"}), 403

    cart = db.session.get(AbandonedCart, cart_id)
    if not cart or cart.status == 'completed':
        return jsonify({"status": "error", "message": "Panier introuvable ou déjà complété"}), 404

    # Logique pour une seule relance manuelle
    cart_items_html = "".join([f"<li><b>{item['name']}</b> ({item['price']} XOF)</li>" for item in cart.cart_content])
    body_html = f"""
    <html><body>
        <h1>Votre panier vous attend !</h1>
        <p>Bonjour {cart.customer_name or 'cher client'},</p>
        <p>Nous avons remarqué que vous avez laissé ces articles dans votre panier :</p>
        <ul>{cart_items_html}</ul>
        <p><b>Total : {cart.total_price} XOF</b></p>
        <p><a href="{url_for('produits', _external=True)}">Finaliser ma commande</a></p>
    </body></html>
    """

    email_sent = send_email(cart.email, "Vous avez oublié quelque chose...", body_html)

    if email_sent:
        cart.relaunch_count += 1
        cart.last_relaunch_at = datetime.now(timezone.utc)
        db.session.add(EmailSendLog(recipient_email=cart.email))
        db.session.commit()
        return jsonify({"status": "success", "message": f"Email de relance envoyé (Relance #{cart.relaunch_count})."})
    else:
        return jsonify({"status": "error", "message": "Erreur lors de l'envoi de l'e-mail."}), 500
        

DAILY_EMAIL_LIMIT = 300

# Remplacez la fonction remind_all_abandoned_carts
@app.route('/api/marketing/remind/all', methods=['POST'])
def remind_all_abandoned_carts():
    if not session.get('admin_logged_in'):
        return jsonify({"status": "error", "message": "Non autorisé"}), 403

    try:
        # 1. Récupérer les paramètres de relance depuis la base de données
        settings = {s.key: s.value for s in SiteSetting.query.all()}
        max_relaunches = int(settings.get('MAX_RELAUNCHES_PER_CART', 2))
        relaunch_interval = int(settings.get('RELAUNCH_INTERVAL_HOURS', 12))
        
        if max_relaunches == 0:
            return jsonify({"status": "info", "message": "Les relances sont désactivées (max relances = 0)."}), 200

        # 2. Compter les emails envoyés globalement aujourd'hui
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        sent_today_count = EmailSendLog.query.filter(EmailSendLog.sent_at >= twenty_four_hours_ago).count()
        
        remaining_sends = 300 - sent_today_count
        if remaining_sends <= 0:
            return jsonify({"status": "info", "message": "Limite quotidienne de 300 e-mails atteinte."}), 429

        # 3. Trouver les candidats à la relance
        now = datetime.now(timezone.utc)
        interval_delta = timedelta(hours=relaunch_interval)
        
        # Critères :
        # - Statut "abandoned"
        # - Nombre de relances inférieur au max autorisé
        # - Jamais relancé OU dernière relance suffisamment ancienne
        carts_to_remind = db.session.query(AbandonedCart).filter(
            AbandonedCart.status == 'abandoned',
            AbandonedCart.relaunch_count < max_relaunches,
            (AbandonedCart.last_relaunch_at == None) | (AbandonedCart.last_relaunch_at < now - interval_delta)
        ).limit(remaining_sends).all()

        if not carts_to_remind:
            return jsonify({"status": "info", "message": "Aucun panier éligible à la relance pour le moment."}), 200

        sent_count = 0
        failed_count = 0

        # 4. Envoyer les e-mails
        for cart in carts_to_remind:
            body_html = f"..." # (Même corps d'e-mail que la fonction `remind_abandoned_cart`)
            
            if send_email(cart.email, "Vous avez oublié quelque chose...", body_html):
                cart.relaunch_count += 1
                cart.last_relaunch_at = now
                db.session.add(EmailSendLog(recipient_email=cart.email))
                sent_count += 1
            else:
                failed_count += 1
        
        db.session.commit()

        message = f"{sent_count} relance(s) envoyée(s) avec succès."
        if failed_count > 0: message += f" {failed_count} ont échoué."
        return jsonify({"status": "success", "message": message})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Erreur lors de la relance de masse : {e}")
        return jsonify({"status": "error", "message": "Une erreur serveur est survenue."}), 500


@app.route('/api/marketing/clear-all', methods=['POST'])
def clear_all_abandoned_carts():
    """Supprime TOUS les paniers abandonnés et leurs liens de téléchargement associés de manière optimisée."""
    if not session.get('admin_logged_in'):
        return jsonify({"status": "error", "message": "Non autorisé"}), 403

    try:
        # Récupère uniquement les IDs des paniers à supprimer, ce qui est plus léger en mémoire.
        cart_ids_to_delete = [c.id for c in AbandonedCart.query.with_entities(AbandonedCart.id).all()]
        num_deleted = len(cart_ids_to_delete)

        if num_deleted == 0:
            return jsonify({"status": "success", "message": "La liste est déjà vide."})

        # --- OPTIMISATION MAJEURE ---
        # Supprime tous les liens de téléchargement associés en UNE SEULE requête.
        db.session.query(DownloadLink).filter(DownloadLink.cart_id.in_(cart_ids_to_delete)).delete(synchronize_session=False)

        # Supprime tous les paniers en UNE SEULE requête.
        db.session.query(AbandonedCart).filter(AbandonedCart.id.in_(cart_ids_to_delete)).delete(synchronize_session=False)
        # --- FIN DE L'OPTIMISATION ---

        db.session.commit()
        
        message = f"{num_deleted} panier(s) abandonné(s) ont été supprimés."
        log_action("clear_abandoned_carts", {"count": num_deleted, "user": session.get('username')})
        
        return jsonify({"status": "success", "message": message})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erreur lors de la suppression optimisée des paniers : {e}")
        return jsonify({"status": "error", "message": "Une erreur serveur est survenue."}), 500

# Clé secrète pour le cron job (gardez-la secrète)
CRON_SECRET_KEY = os.environ.get('CRON_SECRET_KEY', 'une-cle-tres-secrete-par-defaut')

@app.route(f'/cron/trigger-relaunch/{CRON_SECRET_KEY}', methods=['POST'])
def trigger_relaunch_job():
    """
    Cette route est destinée à être appelée par un cron job (tâche planifiée).
    Elle exécute la même logique que le bouton "Relancer tout".
    """
    logging.info("Cron job de relance déclenché.")
    
    # On appelle directement la fonction de relance de masse
    response = remind_all_abandoned_carts()
    
    # On log le résultat
    try:
        data = response.get_json()
        logging.info(f"Résultat du cron job : {data.get('message')}")
    except Exception as e:
        logging.error(f"Erreur lors de la lecture du résultat du cron job : {e}")
        
    return response

# --- NOUVELLE ROUTE POUR LA TUILE "SUIVI" ---
@app.route('/k4d3t/suivi')
def admin_suivi():
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter.", "error")
        return redirect(url_for('admin_login'))

    user = User.query.filter_by(username=session.get('username')).first()
    if not user:
        abort(403)

    # Calcul du CA total réel (basé sur les paniers complétés)
    total_revenue = db.session.query(db.func.sum(AbandonedCart.total_price)).filter_by(status='completed').scalar() or 0

    user_revenue = 0
    if user.role.name == 'super_admin':
        user_revenue = total_revenue
    elif user.revenue_share_percentage > 0:
        user_revenue = total_revenue * (user.revenue_share_percentage / 100.0)

    # Données pour le graphique (par exemple, CA par mois)
    revenue_by_month = db.session.query(
        db.func.strftime('%Y-%m', AbandonedCart.created_at),
        db.func.sum(AbandonedCart.total_price)
    ).filter(
        AbandonedCart.status == 'completed'
    ).group_by(
        db.func.strftime('%Y-%m', AbandonedCart.created_at)
    ).order_by(
        db.func.strftime('%Y-%m', AbandonedCart.created_at)
    ).all()

    chart_labels = [row[0] for row in revenue_by_month]
    chart_data = [row[1] for row in revenue_by_month]

    return render_template('admin_suivi.html',
                           total_revenue=total_revenue,
                           user_revenue=user_revenue,
                           user_percentage=user.revenue_share_percentage,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           role=user.role.name)


# --- NOUVELLE ROUTE POUR GÉRER LES RÔLES ET PERMISSIONS ---
@app.route('/k4d3t/settings/roles', methods=['GET', 'POST'])
def admin_settings_roles():
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        # CAS 1 : Création d'un nouveau rôle
        role_name = request.form.get('role_name')
        if role_name:
            if not Role.query.filter_by(name=role_name).first():
                new_role = Role(name=role_name)
                db.session.add(new_role)
                db.session.commit()
                flash(f"Le rôle '{role_name}' a été créé.", "success")
            else:
                flash("Ce nom de rôle existe déjà.", "error")
            return redirect(url_for('admin_settings_roles'))

        # CAS 2 : Mise à jour des permissions
        permissions = request.form.getlist('permissions')
        all_roles = Role.query.options(joinedload(Role.tiles)).all()
        
        for role in all_roles:
            # On ne modifie pas les permissions du super_admin via ce formulaire
            if role.name == 'super_admin':
                continue

            # CORRECTION : La bonne façon de vider la relation est d'assigner une liste vide
            role.tiles = [] 
            
            # On ré-assigne les permissions cochées
            for perm_string in permissions:
                if perm_string.startswith(f'role_{role.id}_'):
                    tile_id = int(perm_string.split('_')[2])
                    tile_to_add = Tile.query.get(tile_id)
                    if tile_to_add:
                        role.tiles.append(tile_to_add)

        db.session.commit()
        flash("Permissions mises à jour avec succès.", "success")
        return redirect(url_for('admin_settings_roles'))

    # Logique GET (inchangée)
    roles = Role.query.order_by(Role.id).all()
    tiles = Tile.query.order_by(Tile.id).all()
    return render_template('admin_settings_roles.html', roles=roles, tiles=tiles)


# --- NOUVELLE ROUTE POUR SUPPRIMER UN RÔLE ---
@app.route('/k4d3t/settings/roles/delete/<int:role_id>', methods=['POST'])
def delete_role(role_id):
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        abort(403)
    
    role = Role.query.get(role_id)
    if role and role.name != 'super_admin' and not role.users:
        db.session.delete(role)
        db.session.commit()
        flash("Rôle supprimé.", "success")
    elif role.users:
        flash("Impossible de supprimer un rôle assigné à des utilisateurs.", "error")
    else:
        flash("Impossible de supprimer ce rôle.", "error")
        
    return redirect(url_for('admin_settings_roles'))

        
# --- MODIFICATION DANS LA FONCTION DE DÉMARRAGE `if __name__ == '__main__':` ---
# Remplacez votre bloc `if __name__ == '__main__':` par celui-ci pour tout initialiser correctement.
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        initialize_database() # Appel de la nouvelle fonction

        # On s'assure que l'utilisateur super_admin existe
        super_admin_user = User.query.filter_by(username='k4d3t').first()
        super_admin_role = Role.query.filter_by(name='super_admin').first()
        if not super_admin_user:
            hashed_password = bcrypt.hashpw("spacekali".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            new_super_admin = User(username='k4d3t', password=hashed_password, role_id=super_admin_role.id, revenue_share_percentage=100)
            db.session.add(new_super_admin)
            db.session.commit()
            print("Utilisateur super_admin 'k4d3t' créé avec succès.")
        elif super_admin_user.role.name != 'super_admin':
            # Assure que k4d3t est TOUJOURS super_admin
            super_admin_user.role_id = super_admin_role.id
            db.session.commit()

    port = int(os.environ.get('PORT', 5005))
    app.run(host='0.0.0.0', port=port)
