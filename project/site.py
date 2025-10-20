from flask import Flask, render_template, jsonify, request, redirect, url_for, abort, session, flash, send_file, Response
import json
import os
from datetime import datetime, timezone, timedelta, date
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
from sqlalchemy import text 
from sqlalchemy.exc import ProgrammingError

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
    # Pour toutes les réponses API, ajoute un cache HTTP (sauf /api/locale)
    if request.path.startswith("/api/"):
        if request.path == "/api/locale":
            # Toujours frais, pour refléter la session courante immédiatement
            response.headers["Cache-Control"] = "no-store, must-revalidate"
            # Les proxies/balancers doivent varier selon le cookie de session
            response.headers["Vary"] = (response.headers.get("Vary", "") + ", Cookie").strip(", ")
        else:
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

# --- Bootstrap DB (une seule fois) ---
def bootstrap_db_once():
    if getattr(app, '_da_bootstrapped', False):
        return
    try:
        with app.app_context():
            ensure_admin_indexes()
            ensure_product_new_columns()
            db.create_all()
            initialize_database()
        app._da_bootstrapped = True
        logger.info("Bootstrap DB effectué.")
    except Exception as e:
        logger.warning(f"bootstrap_db_once: {e}")

# Flask 3: before_first_request supprimé -> on boote au premier request (une seule fois)
@app.before_request
def _bootstrap_guard():
    if not getattr(app, '_da_bootstrapped', False):
        bootstrap_db_once()
# --- Helper functions ---

LOGS_FILE = "data/logs.json"
COMMENTS_FILE = "data/comments.json"

# À coller sous: db.init_app(app)

# --- Helpers Visiteurs (analytics) ---
def _client_ip():
    try:
        xff = request.headers.get('X-Forwarded-For', '') or ''
        if xff:
            return xff.split(',')[0].strip()
        return request.remote_addr
    except Exception:
        return None

BOT_HINTS = ('bot', 'crawl', 'spider', 'curl', 'wget', 'httpclient', 'monitor', 'pingdom')
def _is_bot(ua: str):
    if not ua:
        return False
    ual = ua.lower()
    return any(b in ual for b in BOT_HINTS)

def _should_track_request():
    p = request.path or ''
    if request.method != 'GET':
        return False
    if p.startswith('/admin') or p.startswith('/k4d3t'):
        return False
    if p.startswith('/api/'):
        return False
    if p.startswith('/static/') or p.startswith('/favicon') or p.startswith('/robots') or p.startswith('/sitemap'):
        return False
    if p in ('/health', '/_debug/ip'):
        return False
    return True

def _ensure_device_cookie(response):
    try:
        if request.cookies.get('da_device_id'):
            return response
        import uuid as _uuid
        did = str(_uuid.uuid4())
        expires = datetime.utcnow() + timedelta(days=730)
        response.set_cookie('da_device_id', did, expires=expires, samesite='Lax', secure=False)
    except Exception:
        pass
    return response

@app.after_request
def track_visit(response):
    try:
        if _should_track_request():
            from models import VisitorEvent
            ua = request.headers.get('User-Agent', '') or ''
            ev = VisitorEvent(
                ts=datetime.now(timezone.utc),
                session_id=request.cookies.get('da_device_id'),
                ip=_client_ip(),
                user_agent=(ua[:255] if ua else None),
                path=(request.full_path[:255] if request.full_path else request.path[:255]),
                referrer=(request.referrer[:255] if request.referrer else None),
                country=(session.get('country') or None),
                is_bot=_is_bot(ua)
            )
            if not ev.is_bot:
                db.session.add(ev)
                db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.debug(f"track_visit skipped: {e}")
    return _ensure_device_cookie(response)

# --- Locale: mapping pays -> devise/lang (subset de pays/monnaies principales) ---
LOCALE_MAP = {
    # code pays: {name, flag (emoji/simple), currency, lang}
    "ci": {"name": "Côte d'Ivoire", "flag": "🇨🇮", "currency": "XOF", "lang": "fr"},
    "sn": {"name": "Sénégal", "flag": "🇸🇳", "currency": "XOF", "lang": "fr"},
    "fr": {"name": "France", "flag": "🇫🇷", "currency": "EUR", "lang": "fr"},
    "us": {"name": "United States", "flag": "🇺🇸", "currency": "USD", "lang": "en"},
    "gb": {"name": "United Kingdom", "flag": "🇬🇧", "currency": "GBP", "lang": "en"},
    "ae": {"name": "United Arab Emirates", "flag": "🇦🇪", "currency": "AED", "lang": "ar"},
    "ru": {"name": "Russia", "flag": "🇷🇺", "currency": "RUB", "lang": "ru"},
    "cn": {"name": "China", "flag": "🇨🇳", "currency": "CNY", "lang": "zh"},
    "jp": {"name": "Japan", "flag": "🇯🇵", "currency": "JPY", "lang": "ja"},
    "de": {"name": "Deutschland", "flag": "🇩🇪", "currency": "EUR", "lang": "de"},
    "ca": {"name": "Canada", "flag": "🇨🇦", "currency": "USD", "lang": "en"},  # simple
}

SUPPORTED_CURRENCIES = ["XOF", "USD", "EUR", "GBP", "AED", "RUB", "CNY", "JPY"]


def flag_emoji_from_code(code2):
    """
    Transforme un code pays ISO alpha-2 (ex: 'tg') en emoji drapeau (🇹🇬).
    """
    try:
        cc = (code2 or '').strip().upper()
        if len(cc) != 2: 
            return '🌐'
        return ''.join(chr(127397 + ord(c)) for c in cc)
    except Exception:
        return '🌐'
        
# Cache 6h des taux (base = XOF pour conversions via XOF)
@cache.cached(timeout=21600, key_prefix="fx_rates_xof_v2")
def get_fx_rates_base_xof():
    """
    Retourne un dict tel que: { 'XOF':1.0, 'USD': <valeur de 1 XOF en USD>, ... }
    1) Essaie base=XOF sans 'symbols', filtre aux devises supportées.
    2) Si incomplet, reconstitue base=XOF depuis base=USD: rate_XOF->cur = (USD->cur) / (USD->XOF).
    3) Fallback statique si tout échoue.
    """
    try:
        r = requests.get(
            "https://api.exchangerate.host/latest",
            params={"base": "XOF", "places": 6},
            timeout=8
        )
        r.raise_for_status()
        data = r.json()
        all_rates = data.get("rates") or {}
        out = {}
        for c in SUPPORTED_CURRENCIES:
            if c == "XOF":
                out["XOF"] = 1.0
            elif isinstance(all_rates.get(c), (int, float)):
                out[c] = float(all_rates[c])
        if len(out) > 1:
            return out
        logging.warning("FX base=XOF incomplet, tentative de reconstruction via base=USD…")
    except Exception as e:
        logging.warning(f"FX rates base=XOF erreur: {e}")

    # Reconstruction via base=USD
    try:
        r = requests.get(
            "https://api.exchangerate.host/latest",
            params={"base": "USD", "places": 6},
            timeout=8
        )
        r.raise_for_status()
        data = r.json()
        usd_rates = data.get("rates") or {}
        usd_to_xof = float(usd_rates.get("XOF") or 0)
        if usd_to_xof:
            out = {"XOF": 1.0}
            for c in SUPPORTED_CURRENCIES:
                if c == "XOF":
                    continue
                v = float(usd_rates.get(c) or 0)
                if v:
                    # 1 XOF = (USD->c) / (USD->XOF)
                    out[c] = v / usd_to_xof
            if len(out) > 1:
                return out
        logging.warning("FX reconstruction via USD échouée ou incomplète.")
    except Exception as e:
        logging.warning(f"FX rates base=USD erreur: {e}")

    # Fallback approximatif
    return {
        "XOF": 1.0,
        "USD": 0.0017,
        "EUR": 0.0015,
        "GBP": 0.0013,
        "AED": 0.0063,
        "RUB": 0.16,
        "CNY": 0.012,
        "JPY": 0.26,
    }

def convert_amount(amount, from_cur, to_cur, rates_xof):
    if from_cur == to_cur:
        return float(amount)
    # Convertit via base XOF: from -> XOF -> to
    try:
        # from -> XOF
        if from_cur != "XOF":
            inv = rates_xof.get(from_cur, 0)
            if not inv:
                return float(amount)
            amount_in_xof = float(amount) / inv
        else:
            amount_in_xof = float(amount)
        # XOF -> to
        rate_to = rates_xof.get(to_cur, 0)
        if not rate_to:
            return float(amount_in_xof)
        return float(amount_in_xof * rate_to)
    except Exception:
        return float(amount)

@app.route('/api/locale', methods=['GET', 'POST'])
def api_locale():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        code = (data.get('country') or '').lower()
        currency = (data.get('currency') or '').upper()
        lang = (data.get('lang') or '').lower()

        entry = LOCALE_MAP.get(code)
        if entry:
            session['country'] = code
            session['currency'] = entry['currency']
            session['lang'] = entry['lang']
            return jsonify({"status":"success","country":code,"currency":entry['currency'],"lang":entry['lang']}), 200

        SUPPORTED = set(SUPPORTED_CURRENCIES)
        if currency in SUPPORTED and lang:
            session['country'] = code or 'ci'
            session['currency'] = currency
            session['lang'] = lang
            return jsonify({"status":"success","country": session['country'],"currency": currency,"lang": lang}), 200

        session['country'] = 'ci'
        session['currency'] = 'XOF'
        session['lang'] = 'fr'
        return jsonify({"status":"success","country":"ci","currency":"XOF","lang":"fr"}), 200

    # GET
    code = (session.get('country') or 'ci').lower()
    entry = LOCALE_MAP.get(code)
    # Utilise la session si non listé dans LOCALE_MAP
    currency = session.get('currency') or (entry['currency'] if entry else 'XOF')
    lang = session.get('lang') or (entry['lang'] if entry else 'fr')
    name = (entry['name'] if entry else code.upper())
    flag = (entry['flag'] if entry else flag_emoji_from_code(code))
    return jsonify({
        "status":"success",
        "country": code,
        "currency": currency,
        "lang": lang,
        "flag": flag,
        "name": name
    }), 200


@app.route('/api/fx-rates', methods=['GET'])
def api_fx_rates():
    return jsonify({"status":"success","base":"XOF","rates": get_fx_rates_base_xof()}), 200

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

    # WhatsApp: normalisation + lien wa.me
    whatsapp_raw = str(data.get("whatsapp", "")).strip()
    if whatsapp_raw.startswith("00"):
        whatsapp_raw = "+" + whatsapp_raw[2:]
    # Garde la version affichable échappée
    whatsapp_display = html.escape(whatsapp_raw)
    # Construit l'URL wa.me (chiffres uniquement, sans '+')
    wa_digits = re.sub(r"\D", "", whatsapp_raw)
    wa_link = f"https://wa.me/{wa_digits}" if wa_digits else ""

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
        f"📱 WhatsApp : {wa_link} {f'({whatsapp_display})' if whatsapp_display else ''}\n\n"
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
    try:
        produits = Product.query.options(
            joinedload(Product.images),
            joinedload(Product.badges)
        ).all()
    except ProgrammingError:
        db.session.rollback()
        try:
            ensure_product_new_columns()
        except Exception:
            pass
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
    try:
        produits = Product.query.options(
            joinedload(Product.images),
            joinedload(Product.badges)
        ).all()
    except ProgrammingError:
        db.session.rollback()
        try:
            ensure_product_new_columns()
        except Exception:
            pass
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
    try:
        produit = Product.query.options(
            joinedload(Product.images),
            joinedload(Product.badges),
            joinedload(Product.faqs),
            joinedload(Product.comments)
        ).filter_by(slug=slug).first()
    except ProgrammingError as e:
        # Colonnes manquantes -> on répare puis on réessaie
        db.session.rollback()
        try:
            ensure_product_new_columns()
        except Exception:
            pass
        produit = Product.query.options(
            joinedload(Product.images),
            joinedload(Product.badges),
            joinedload(Product.faqs),
            joinedload(Product.comments)
        ).filter_by(slug=slug).first()

    if not produit:
        abort(404)

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
            "hero_title": getattr(p, "hero_title", None),
            "hero_subtitle": getattr(p, "hero_subtitle", None),
            "hero_cta_label": getattr(p, "hero_cta_label", None),
            "demo_video_url": getattr(p, "demo_video_url", None),
            "demo_video_text": getattr(p, "demo_video_text", None),
            "final_cta_title": getattr(p, "final_cta_title", None),
            "final_cta_label": getattr(p, "final_cta_label", None),
            "benefits": getattr(p, "benefits", None),
            "includes": getattr(p, "includes", None),
            "guarantees": getattr(p, "guarantees", None),
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
    data = request.get_json(silent=True) or {}
    rating = data.get('rating')

    try:
        rating = int(rating)
    except Exception:
        rating = None
    if not rating or not (1 <= rating <= 5):
        return jsonify({"error": "Une note valide (1-5) est requise."}), 400

    produit = Product.query.get(product_id)
    if not produit:
        return jsonify({"error": "Produit introuvable."}), 404

    # 1) Récupérer le device_id (cookie > header > body), sinon en générer un
    device_id = request.cookies.get('da_device_id') \
        or request.headers.get('X-DA-Device') \
        or (data.get('device_id') if isinstance(data.get('device_id'), str) else None)
    new_cookie_needed = False
    if not device_id:
        device_id = str(uuid.uuid4())
        new_cookie_needed = True

    # 2) Upsert: si un vote existe pour (product_id, device_id) => UPDATE; sinon INSERT
    existing = Comment.query.filter_by(product_id=product_id, device_id=device_id).first()
    action = "created"
    if existing:
        existing.rating = rating
        existing.date = datetime.now(timezone.utc)
        action = "updated"
    else:
        new_rating = Comment(
            product_id=product_id,
            rating=rating,
            comment="",                   # champ NOT NULL
            date=datetime.now(timezone.utc),
            device_id=device_id
        )
        db.session.add(new_rating)

    db.session.commit()

    # 3) Recalculer la moyenne et le nombre d'avis
    all_ratings = [c.rating for c in produit.comments if c.rating is not None]
    reviews_count = len(all_ratings)
    average_rating = sum(all_ratings) / reviews_count if reviews_count > 0 else 0.0

    # 4) Invalider le cache de la page produit
    cache.delete_memoized(product_detail, slug=produit.slug)

    resp = jsonify({
        "message": "Vote enregistré !" if action == "created" else "Votre note a été mise à jour.",
        "average_rating": round(average_rating, 2),
        "reviews_count": reviews_count,
        "action": action
    })
    # 5) Si cookie manquant, le poser maintenant (durée 2 ans)
    if new_cookie_needed:
        expires = datetime.utcnow() + timedelta(days=730)
        resp.set_cookie(
            'da_device_id',
            device_id,
            expires=expires,
            samesite='Lax',
            secure=False   # mets True si HTTPS partout
        )
    return resp, 200

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
    Reçoit les données du frontend, NORMALISE en XOF (sans jamais reconvertir),
    et transmet à MoneyFusion.
    """
    data = request.json
    MONEYFUSION_API_URL = "https://www.pay.moneyfusion.net/Digital_Adept/a5f4d44ad70069fa/pay/"

    logging.info(f"Payload reçu du frontend: {data}")

    try:
        # 1) Reconstruire l'objet article en XOF et le total en XOF (blindé)
        #    On ne fait AUCUNE conversion ici: on suppose que le front envoie déjà des montants base XOF.
        article_in = (data.get("article") or [])
        first_map = article_in[0] if (article_in and isinstance(article_in, list) and isinstance(article_in[0], dict)) else {}
        article_xof = {}
        total_xof = 0.0
        for k, v in (first_map.items() if isinstance(first_map, dict) else []):
            try:
                amount = float(v) or 0.0
            except Exception:
                amount = 0.0
            # XOF = monnaie entière
            article_xof[k] = round(amount)
            total_xof += amount

        total_xof = round(total_xof)

        # 2) Forcer le payload provider en XOF strict
        data["article"] = [article_xof]
        data["totalPrice"] = total_xof
        data["currency"] = "XOF"

        logging.info(f"Payload normalisé (XOF) vers MoneyFusion: {data}")

        response = requests.post(MONEYFUSION_API_URL, json=data, timeout=15)
        logging.info(f"Réponse brute de MoneyFusion: {response.status_code} '{response.text}'")
        response.raise_for_status()
        response_data = response.json()

        if not response_data.get("statut"):
            return jsonify({"error": response_data.get("message", "Erreur inconnue de l'API de paiement.")}), 400

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
    data = request.json or {}
    email = data.get('email')
    cart_items = data.get('cart') or []
    nom_client = data.get('nom_client')

    # Recalcule TOUJOURS le total en XOF à partir des lignes (ne fait confiance à rien d'autre)
    total_price = 0.0
    for it in cart_items:
        try:
            price = float(it.get('price') or 0.0)
            qty = float(it.get('quantity') or 1.0)
            total_price += price * qty
        except Exception:
            pass
    total_price = round(total_price)

    whatsapp = data.get('whatsapp')
    sel_currency = (data.get('currency') or 'XOF').upper()  # choix visuel utilisateur (analytics/relance)

    if not email or not cart_items:
        return jsonify({"error": "Email et contenu du panier sont requis."}), 400

    abandoned_cart = AbandonedCart(
        email=email,
        customer_name=nom_client,
        cart_content=cart_items,           # tel quel
        total_price=total_price,           # XOF RECONSTRUIT
        whatsapp_number=whatsapp,
        currency=sel_currency              # conserve le choix utilisateur (affichage e-mails)
    )
    db.session.add(abandoned_cart)
    db.session.commit()

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

# --- Initialisation BDD: rôles, tuiles, admin par défaut (avec "Retrait") ---
def initialize_database():
    """Crée les rôles, tuiles, permissions et l'admin par défaut."""
    # 1) super_admin
    if not Role.query.filter_by(name='super_admin').first():
        db.session.add(Role(name='super_admin'))
        db.session.commit()

    # 2) Tuiles (incluant "Retrait")
    default_tiles = [
        {'name': 'Produits',     'endpoint': 'admin_products_page',   'description': 'Gérer les produits du site.'},
        {'name': 'Annonces',     'endpoint': 'admin_announcements',   'description': 'Gérer les annonces et bannières.'},
        {'name': 'Marketing',    'endpoint': 'admin_marketing',       'description': 'Suivre les paniers abandonnés.'},
        {'name': 'Commentaires', 'endpoint': 'admin_comments_page',   'description': 'Modérer les commentaires.'},
        {'name': 'Suivi',        'endpoint': 'admin_suivi',           'description': "Voir le chiffre d'affaires."},
        {'name': 'Retrait',      'endpoint': 'admin_payout',          'description': "Demander un retrait d'argent."},
    ]
    for tile_data in default_tiles:
        if not Tile.query.filter_by(endpoint=tile_data['endpoint']).first():
            db.session.add(Tile(**tile_data))
    db.session.commit()

    # 3) Assigner toutes les tuiles au super_admin (y compris Retrait)
    super_admin_role = Role.query.filter_by(name='super_admin').first()
    if super_admin_role:
        all_tiles = Tile.query.all()
        try:
            current_tiles = super_admin_role.tiles.all()
        except Exception:
            current_tiles = list(super_admin_role.tiles)
        current_ids = {t.id for t in current_tiles}

        for tile in all_tiles:
            if tile.id not in current_ids:
                super_admin_role.tiles.append(tile)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logging.exception("initialize_database: échec commit (assignation tuiles super_admin)")

    # 4) Créer l'utilisateur super_admin "k4d3t" si absent
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
    
# --- Dashboard: tuiles via JOIN (1 requête, plus rapide) ---
@cache.cached(timeout=300)
@app.route('/k4d3t/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter.", "error")
        return redirect(url_for('admin_login'))

    user = User.query.options(joinedload(User.role)).filter_by(username=session.get('username')).first()
    if not user:
        session.clear()
        flash("Session invalide, veuillez vous reconnecter.", "error")
        return redirect(url_for('admin_login'))

    # 1 seule requête pour charger les tuiles du rôle
    user_tiles = (
        db.session.query(Tile)
        .join(role_tiles, role_tiles.c.tile_id == Tile.id)
        .join(Role, Role.id == role_tiles.c.role_id)
        .filter(Role.id == user.role_id)
        .order_by(Tile.id)
        .all()
    )

    log_action("access_dashboard", {"role": session.get('role')})
    return render_template('admin_dashboard.html', user_tiles=user_tiles)

@app.route('/k4d3t/settings', methods=['GET'])
def admin_settings():
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))
    # Affiche simplement la page de navigation des paramètres, sans charger de données.
    return render_template('admin_settings.html')


# --- Ajouter un utilisateur: empêche de dépasser 100% hors super_admin ---
# Page Users (GET) servie via cache 60s
@cache.cached(timeout=60)
def cached_admin_settings_users_page():
    users = User.query.options(joinedload(User.role)).all()
    roles = Role.query.order_by(Role.name).all()
    return render_template('admin_settings_users.html', users=users, roles=roles)

@app.route('/k4d3t/settings/users', methods=['GET', 'POST'])
def admin_settings_users():
    if session.get('role') != 'super_admin':
        log_action("unauthorized_access_attempt", {"path": "/k4d3t/settings/users"})
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role_id = request.form.get('role_id')
        revenue_share = request.form.get('revenue_share', 0)

        if not username or not password or not role_id:
            flash("Nom d'utilisateur, mot de passe et rôle sont requis.", "error")
            return redirect(url_for('admin_settings_users'))

        if User.query.filter_by(username=username).first():
            flash("Ce nom d'utilisateur est déjà pris.", "error")
            return redirect(url_for('admin_settings_users'))

        role = Role.query.get(int(role_id))
        try:
            new_share = float(revenue_share or 0)
        except Exception:
            new_share = 0.0

        if role and role.name != 'super_admin':
            total_after = get_non_super_total_percentage() + new_share
            if total_after > 100.0 + 1e-9:
                flash(f"Le total des commissions (hors super_admin) dépasserait 100% (demande: +{new_share}%, actuel: {total_after - new_share:.1f}%).", "error")
                return redirect(url_for('admin_settings_users'))

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = User(
            username=username,
            password=hashed_password,
            role_id=int(role_id),
            revenue_share_percentage=new_share
        )
        db.session.add(user)
        db.session.commit()
        # Invalider le cache de la page Users
        try:
            cache.delete_memoized(cached_admin_settings_users_page)
        except Exception:
            pass
        flash("Nouvel administrateur ajouté avec succès.", "success")
        return redirect(url_for('admin_settings_users'))

    # GET
    return cached_admin_settings_users_page()
    
# --- Inline edit: empêche de dépasser 100% hors super_admin ---
# --- Utilisateurs: édition inline (username/role/commission) avec plafond % ---
@app.route('/api/admin/users/<int:user_id>', methods=['PATCH'])
def api_admin_update_user(user_id):
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        return jsonify({"status": "error", "message": "Accès non autorisé"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "Utilisateur introuvable"}), 404

    data = request.get_json(silent=True) or {}
    new_username = data.get('username')
    new_role_id = data.get('role_id')
    new_share = data.get('revenue_share_percentage')

    if new_username is not None:
        new_username = str(new_username).strip()
        if not new_username:
            return jsonify({"status": "error", "message": "Nom d'utilisateur invalide"}), 400
        if new_username != user.username and User.query.filter_by(username=new_username).first():
            return jsonify({"status": "error", "message": "Nom d'utilisateur déjà pris"}), 409
        user.username = new_username

    target_role_id = int(new_role_id) if new_role_id is not None else user.role_id
    target_role = Role.query.get(target_role_id)

    target_share = float(new_share) if new_share is not None else float(user.revenue_share_percentage or 0.0)

    if target_role and target_role.name != 'super_admin':
        total_after = get_non_super_total_percentage(exclude_user_id=user.id) + target_share
        if total_after > 100.0 + 1e-9:
            return jsonify({
                "status": "error",
                "message": f"Le total des commissions (hors super_admin) dépasserait 100% (demande: {target_share}%, actuel hors cet utilisateur: {total_after - target_share:.1f}%)."
            }), 400

    user.role_id = target_role_id
    user.revenue_share_percentage = target_share

    db.session.commit()
    try:
        cache.delete_memoized(cached_admin_settings_users_page)
    except Exception:
        pass
    return jsonify({"status": "success", "message": "Utilisateur mis à jour"}), 200
    
@app.route('/api/admin/users/<int:user_id>/password', methods=['POST'])
def api_admin_update_user_password(user_id):
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        return jsonify({"status": "error", "message": "Accès non autorisé"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "Utilisateur introuvable"}), 404

    data = request.get_json(silent=True) or {}
    new_password = data.get('new_password')
    if not new_password or len(new_password) < 6:
        return jsonify({"status": "error", "message": "Mot de passe trop court (min 6 caractères)"}), 400

    user.password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.session.commit()
    return jsonify({"status": "success", "message": "Mot de passe mis à jour"}), 200

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
    try:
        cache.delete_memoized(cached_admin_settings_users_page)
    except Exception:
        pass
    flash("Utilisateur supprimé avec succès.", "success")
    return redirect(url_for('admin_settings_users'))
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
            #NOUVEAU:
            "hero_title": getattr(p, "hero_title", None),
            "hero_subtitle": getattr(p, "hero_subtitle", None),
            "hero_cta_label": getattr(p, "hero_cta_label", None),
            "demo_video_url": getattr(p, "demo_video_url", None),
            "demo_video_text": getattr(p, "demo_video_text", None),
            "final_cta_title": getattr(p, "final_cta_title", None),
            "final_cta_label": getattr(p, "final_cta_label", None),
            "benefits": getattr(p, "benefits", None),
            "includes": getattr(p, "includes", None),
            "guarantees": getattr(p, "guarantees", None),
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
            "hero_title": getattr(p, "hero_title", None),
            "hero_subtitle": getattr(p, "hero_subtitle", None),
            "hero_cta_label": getattr(p, "hero_cta_label", None),
            "demo_video_url": getattr(p, "demo_video_url", None),
            "demo_video_text": getattr(p, "demo_video_text", None),
            "final_cta_title": getattr(p, "final_cta_title", None),
            "final_cta_label": getattr(p, "final_cta_label", None),
            "benefits": getattr(p, "benefits", None),
            "includes": getattr(p, "includes", None),
            "guarantees": getattr(p, "guarantees", None),
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
    for field in ['name', 'short_description', 'description', 'price', 'old_price', 'currency', 'featured', 'category', 'stock', 'sku','hero_title','hero_subtitle','hero_cta_label',
        'demo_video_url','demo_video_text','final_cta_title','final_cta_label']:
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
                
    if 'benefits' in data:
        try: product.benefits = json.loads(data.get('benefits','[]'))
        except Exception: product.benefits = []
    if 'includes' in data:
        try: product.includes = json.loads(data.get('includes','[]'))
        except Exception: product.includes = []
    if 'guarantees' in data:
        try: product.guarantees = json.loads(data.get('guarantees','[]'))
        except Exception: product.guarantees = []
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
        slug=slugify(data['name']),
        hero_title=data.get('hero_title') or None,
        hero_subtitle=data.get('hero_subtitle') or None,
        hero_cta_label=data.get('hero_cta_label') or None,
        demo_video_url=data.get('demo_video_url') or None,
        demo_video_text=data.get('demo_video_text') or None,
        final_cta_title=data.get('final_cta_title') or None,
        final_cta_label=data.get('final_cta_label') or None,
    )
    # NOUVEAU: listes JSON
    try:
        produit.benefits = json.loads(data.get('benefits', '[]'))
    except Exception:
        produit.benefits = []
    try:
        produit.includes = json.loads(data.get('includes', '[]'))
    except Exception:
        produit.includes = []
    try:
        produit.guarantees = json.loads(data.get('guarantees', '[]'))
    except Exception:
        produit.guarantees = []
        
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
    """Met à jour une annonce existante et bump la date (nouvelle version)."""
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Non autorisé"}), 403
    data = request.json or {}
    annonce = Announcement.query.get_or_404(id)
    annonce.content = data.get("content", annonce.content)
    annonce.active = data.get("active", annonce.active)
    annonce.type = data.get("type", annonce.type)
    annonce.video_url = data.get("video_url", annonce.video_url)
    annonce.btn_label = data.get("btn_label", annonce.btn_label)
    annonce.btn_url = data.get("btn_url", annonce.btn_url)
    # BUMP DATE pour signaler une nouvelle version au front
    annonce.date = datetime.now(timezone.utc)
    db.session.commit()
    cache.delete_memoized(api_announcements_active)
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
        meta_description="Raté! Cette page n’existe pas. Elle a peut-être été supprimée",
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

    client_currency = getattr(cart, 'currency', None) or 'XOF'

    cart_items_html = "".join([
        f"<li><b>{item.get('name')}</b> ({item.get('price')} {client_currency})</li>"
        for item in cart.cart_content
    ])

    body_html = f"""
    <html><body>
        <h1>Votre panier vous attend !</h1>
        <p>Bonjour {cart.customer_name or 'cher client'},</p>
        <p>Vous avez laissé ces articles dans votre panier :</p>
        <ul>{cart_items_html}</ul>
        <p><b>Total (base XOF pour traitement): {round(float(cart.total_price or 0), 2)} XOF</b></p>
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
        
# --- Helper commissions (hors super_admin) ---
def get_non_super_total_percentage(exclude_user_id=None):
    q = db.session.query(
        db.func.coalesce(db.func.sum(User.revenue_share_percentage), 0.0)
    ).join(Role, User.role_id == Role.id).filter(Role.name != 'super_admin')
    if exclude_user_id:
        q = q.filter(User.id != exclude_user_id)
    return float(q.scalar() or 0.0)

# --- NOUVELLE ROUTE POUR LA TUILE "SUIVI" ---
# --- Suivi (page) avec périodes + % super_admin = 100 - somme autres ---
@app.route('/k4d3t/suivi')
def admin_suivi():
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter.", "error")
        return redirect(url_for('admin_login'))

    user = User.query.filter_by(username=session.get('username')).first_or_404()

    period = request.args.get('period', 'this_month')
    today = date.today()
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if period == 'today':
        start_date = today; end_date = today + timedelta(days=1)
        group_by_format = 'YYYY-MM-DD HH24'; chart_label_format = '%H:00'
    elif period == 'last_7_days':
        start_date = today - timedelta(days=6); end_date = today + timedelta(days=1)
        group_by_format = 'YYYY-MM-DD'; chart_label_format = '%d %b'
    elif period == 'last_30_days':
        start_date = today - timedelta(days=29); end_date = today + timedelta(days=1)
        group_by_format = 'YYYY-MM-DD'; chart_label_format = '%d %b'
    elif period == 'this_month':
        start_date = today.replace(day=1); end_date = (start_date + timedelta(days=32)).replace(day=1)
        group_by_format = 'YYYY-MM-DD'; chart_label_format = '%d %b'
    elif period == 'last_month':
        end_of_last_month = today.replace(day=1) - timedelta(days=1)
        start_date = end_of_last_month.replace(day=1); end_date = today.replace(day=1)
        group_by_format = 'YYYY-MM-DD'; chart_label_format = '%d %b'
    elif period == 'custom' and start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)
        group_by_format = 'YYYY-MM-DD'; chart_label_format = '%d %b %Y'
    else:
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1)
        period = 'this_month'; group_by_format = 'YYYY-MM-DD'; chart_label_format = '%d %b'

    base_query = AbandonedCart.query.filter(
        AbandonedCart.status == 'completed',
        AbandonedCart.created_at >= start_date,
        AbandonedCart.created_at < end_date
    )
    total_revenue = base_query.with_entities(db.func.sum(AbandonedCart.total_price)).scalar() or 0.0

    if user.role and user.role.name == 'super_admin':
        other_pct = get_non_super_total_percentage()
        effective_pct = max(0.0, 100.0 - other_pct)
    else:
        effective_pct = float(user.revenue_share_percentage or 0.0)

    user_revenue = total_revenue * (effective_pct / 100.0)

    revenue_by_time = base_query.with_entities(
        db.func.to_char(AbandonedCart.created_at, group_by_format),
        db.func.sum(AbandonedCart.total_price)
    ).group_by(
        db.func.to_char(AbandonedCart.created_at, group_by_format)
    ).order_by(
        db.func.to_char(AbandonedCart.created_at, group_by_format)
    ).all()

    chart_labels = [
        datetime.strptime(r[0], '%Y-%m-%d' if 'HH24' not in group_by_format else '%Y-%m-%d %H').strftime(chart_label_format)
        for r in revenue_by_time
    ]
    chart_data = [float(r[1]) for r in revenue_by_time]

    return render_template(
        'admin_suivi.html',
        total_revenue=total_revenue,
        user_revenue=user_revenue,
        user_percentage=effective_pct,
        chart_labels=chart_labels,
        chart_data=chart_data,
        role=(user.role.name if user.role else None),
        selected_period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=(end_date - timedelta(days=1)).strftime('%Y-%m-%d')
    )

    
# --- Suivi (API AJAX): même logique, pas de reload page ---
@app.route('/api/admin/suivi/metrics', methods=['GET'])
def api_admin_suivi_metrics():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401

    user = User.query.filter_by(username=session.get('username')).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    period = request.args.get('period', 'this_month')
    today = date.today()
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if period == 'today':
        start_date = today; end_date = today + timedelta(days=1)
        group_by_format = 'YYYY-MM-DD HH24'; label_in = '%Y-%m-%d %H'; label_out = '%H:00'
    elif period == 'last_7_days':
        start_date = today - timedelta(days=6); end_date = today + timedelta(days=1)
        group_by_format = 'YYYY-MM-DD'; label_in = '%Y-%m-%d'; label_out = '%d %b'
    elif period == 'last_30_days':
        start_date = today - timedelta(days=29); end_date = today + timedelta(days=1)
        group_by_format = 'YYYY-MM-DD'; label_in = '%Y-%m-%d'; label_out = '%d %b'
    elif period == 'this_month':
        start_date = today.replace(day=1); end_date = (start_date + timedelta(days=32)).replace(day=1)
        group_by_format = 'YYYY-MM-DD'; label_in = '%Y-%m-%d'; label_out = '%d %b'
    elif period == 'last_month':
        end_of_last_month = today.replace(day=1) - timedelta(days=1)
        start_date = end_of_last_month.replace(day=1); end_date = today.replace(day=1)
        group_by_format = 'YYYY-MM-DD'; label_in = '%Y-%m-%d'; label_out = '%d %b'
    elif period == 'custom' and start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400
        group_by_format = 'YYYY-MM-DD'; label_in = '%Y-%m-%d'; label_out = '%d %b %Y'
    else:
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1)
        period = 'this_month'; group_by_format = 'YYYY-MM-DD'; label_in = '%Y-%m-%d'; label_out = '%d %b'

    base_query = AbandonedCart.query.filter(
        AbandonedCart.status == 'completed',
        AbandonedCart.created_at >= start_date,
        AbandonedCart.created_at < end_date
    )
    total_revenue = base_query.with_entities(db.func.sum(AbandonedCart.total_price)).scalar() or 0.0

    if user.role and user.role.name == 'super_admin':
        other_pct = get_non_super_total_percentage()
        effective_pct = max(0.0, 100.0 - other_pct)
    else:
        effective_pct = float(user.revenue_share_percentage or 0.0)

    user_revenue = total_revenue * (effective_pct / 100.0)

    rows = base_query.with_entities(
        db.func.to_char(AbandonedCart.created_at, group_by_format),
        db.func.sum(AbandonedCart.total_price)
    ).group_by(
        db.func.to_char(AbandonedCart.created_at, group_by_format)
    ).order_by(
        db.func.to_char(AbandonedCart.created_at, group_by_format)
    ).all()

    labels, data = [], []
    for key, amount in rows:
        try:
            dt = datetime.strptime(key, label_in)
            labels.append(dt.strftime(label_out))
        except Exception:
            labels.append(key)
        data.append(float(amount or 0))

    return jsonify({
        "period": period,
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": (end_date - timedelta(days=1)).strftime('%Y-%m-%d'),
        "total_revenue": float(total_revenue),
        "user_revenue": float(user_revenue),
        "user_percentage": float(effective_pct),
        "role": user.role.name if user.role else None,
        "labels": labels,
        "data": data
    }), 200

# À coller vers la fin du fichier (après vos routes /k4d3t/suivi et /api/admin/suivi/metrics)

def _parse_period(period, start_date_str=None, end_date_str=None):
    today = date.today()
    if period == 'today':
        start_date = today
        end_date = today + timedelta(days=1)
        grp = 'YYYY-MM-DD HH24'
        fmt_in = '%Y-%m-%d %H'
        fmt_out = '%H:00'
    elif period == 'last_7_days':
        start_date = today - timedelta(days=6)
        end_date = today + timedelta(days=1)
        grp = 'YYYY-MM-DD'
        fmt_in = '%Y-%m-%d'
        fmt_out = '%d %b'
    elif period == 'last_30_days':
        start_date = today - timedelta(days=29)
        end_date = today + timedelta(days=1)
        grp = 'YYYY-MM-DD'
        fmt_in = '%Y-%m-%d'
        fmt_out = '%d %b'
    elif period == 'last_month':
        end_of_last_month = today.replace(day=1) - timedelta(days=1)
        start_date = end_of_last_month.replace(day=1)
        end_date = today.replace(day=1)
        grp = 'YYYY-MM-DD'
        fmt_in = '%Y-%m-%d'
        fmt_out = '%d %b'
    elif period == 'custom' and start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)
        grp = 'YYYY-MM-DD'
        fmt_in = '%Y-%m-%d'
        fmt_out = '%d %b %Y'
    else:
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1)
        grp = 'YYYY-MM-DD'
        fmt_in = '%Y-%m-%d'
        fmt_out = '%d %b'
    return start_date, end_date, grp, fmt_in, fmt_out

@app.route('/api/admin/suivi/visitors/summary', methods=['GET'])
def api_admin_visitors_summary():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    from models import VisitorEvent
    period = request.args.get('period', 'this_month')
    s = request.args.get('start_date')
    e = request.args.get('end_date')
    start_date, end_date, grp, _, _ = _parse_period(period, s, e)
    q = VisitorEvent.query.filter(VisitorEvent.ts >= start_date, VisitorEvent.ts < end_date, VisitorEvent.is_bot == False)
    pageviews = q.count()
    visitors = db.session.query(db.func.count(db.func.distinct(VisitorEvent.session_id))).filter(
        VisitorEvent.ts >= start_date, VisitorEvent.ts < end_date, VisitorEvent.is_bot == False
    ).scalar() or 0
    now = datetime.now(timezone.utc)
    active_5m = db.session.query(db.func.count(db.func.distinct(VisitorEvent.session_id))).filter(
        VisitorEvent.ts >= (now - timedelta(minutes=5)), VisitorEvent.is_bot == False
    ).scalar() or 0
    return jsonify({"pageviews": int(pageviews), "visitors": int(visitors), "active_5m": int(active_5m)}), 200

@app.route('/api/admin/suivi/visitors/timeseries', methods=['GET'])
def api_admin_visitors_timeseries():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    from models import VisitorEvent
    period = request.args.get('period', 'this_month')
    s = request.args.get('start_date')
    e = request.args.get('end_date')
    start_date, end_date, grp, fmt_in, fmt_out = _parse_period(period, s, e)
    rows = db.session.query(
        db.func.to_char(VisitorEvent.ts, grp),
        db.func.count(VisitorEvent.id),
        db.func.count(db.func.distinct(VisitorEvent.session_id))
    ).filter(
        VisitorEvent.ts >= start_date, VisitorEvent.ts < end_date, VisitorEvent.is_bot == False
    ).group_by(
        db.func.to_char(VisitorEvent.ts, grp)
    ).order_by(
        db.func.to_char(VisitorEvent.ts, grp)
    ).all()
    labels, pv, uv = [], [], []
    for k, c_pv, c_uv in rows:
        try:
            dt = datetime.strptime(k, fmt_in)
            labels.append(dt.strftime(fmt_out))
        except Exception:
            labels.append(k)
        pv.append(int(c_pv or 0))
        uv.append(int(c_uv or 0))
    return jsonify({"labels": labels, "pageviews": pv, "visitors": uv}), 200

@app.route('/api/admin/suivi/visitors/top-pages', methods=['GET'])
def api_admin_visitors_top_pages():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    from models import VisitorEvent
    period = request.args.get('period', 'this_month')
    s = request.args.get('start_date')
    e = request.args.get('end_date')
    start_date, end_date, _, _, _ = _parse_period(period, s, e)
    rows = db.session.query(
        VisitorEvent.path, db.func.count(VisitorEvent.id)
    ).filter(
        VisitorEvent.ts >= start_date, VisitorEvent.ts < end_date, VisitorEvent.is_bot == False
    ).group_by(VisitorEvent.path).order_by(db.func.count(VisitorEvent.id).desc()).limit(10).all()
    out = [{"path": (r[0] or "/"), "pageviews": int(r[1] or 0)} for r in rows]
    return jsonify(out), 200

@cache.cached(timeout=60)
def cached_admin_settings_roles_page():
    suivi_tile = Tile.query.filter((Tile.endpoint == 'admin_suivi') | (Tile.name == 'Suivi')).first()
    payout_tile = Tile.query.filter_by(endpoint='admin_payout').first()

    roles = Role.query.order_by(Role.id).all()
    changed = False
    # Auto-réparation Suivi/Retrait: forcer pour TOUS les rôles
    for r in roles:
        if suivi_tile:
            try:
                present = any(t.id == suivi_tile.id for t in (r.tiles.all() if hasattr(r.tiles, 'all') else r.tiles))
            except Exception:
                present = False
            if not present:
                r.tiles.append(suivi_tile); changed = True

        if payout_tile:
            try:
                present_p = any(t.id == payout_tile.id for t in (r.tiles.all() if hasattr(r.tiles, 'all') else r.tiles))
            except Exception:
                present_p = False
            if not present_p:
                r.tiles.append(payout_tile); changed = True

    if changed:
        db.session.commit()

    tiles = Tile.query.order_by(Tile.id).all()
    pairs = db.session.query(role_tiles.c.role_id, role_tiles.c.tile_id).all()
    role_tiles_map = {r.id: [] for r in roles}
    for rid, tid in pairs:
        if rid in role_tiles_map:
            role_tiles_map[rid].append(tid)

    return render_template(
        'admin_settings_roles.html',
        roles=roles,
        tiles=tiles,
        suivi_tile_id=(suivi_tile.id if suivi_tile else None),
        payout_tile_id=(payout_tile.id if payout_tile else None),
        role_tiles_map=role_tiles_map
    )

# --- NOUVELLE ROUTE POUR GÉRER LES RÔLES ET PERMISSIONS ---
# --- Rôles & Permissions: "Suivi" forcé pour tous, "Retrait" forcé pour ≠ super_admin ---
@app.route('/k4d3t/settings/roles', methods=['GET', 'POST'])
def admin_settings_roles():
    if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))

    suivi_tile = Tile.query.filter((Tile.endpoint == 'admin_suivi') | (Tile.name == 'Suivi')).first()
    payout_tile = Tile.query.filter_by(endpoint='admin_payout').first()

    if request.method == 'POST':
        # Création d'un rôle
        role_name = request.form.get('role_name')
        if role_name:
            if not Role.query.filter_by(name=role_name).first():
                new_role = Role(name=role_name)
                db.session.add(new_role)
                db.session.commit()
                if suivi_tile:
                    new_role.tiles.append(suivi_tile)
                if payout_tile and role_name != 'super_admin':
                    new_role.tiles.append(payout_tile)
                db.session.commit()
                flash(f"Le rôle '{role_name}' a été créé.", "success")
            else:
                flash("Ce nom de rôle existe déjà.", "error")
            return redirect(url_for('admin_settings_roles'))

        # Mise à jour des permissions
        permissions = request.form.getlist('permissions')
        all_roles = Role.query.all()

        for role in all_roles:
            # Récup tuiles actuelles
            try:
                current_tiles = role.tiles.all()
            except Exception:
                current_tiles = list(role.tiles)

            # 1) retirer toutes les tuiles sauf Suivi et Retrait si rôle ≠ super_admin
            for t in list(current_tiles):
                must_keep = (suivi_tile and t.id == suivi_tile.id) or (payout_tile and t.id == payout_tile.id and role.name != 'super_admin')
                if not must_keep:
                    try:
                        # retire uniquement si présent (évite StaleDataError)
                        try:
                            present = any(tt.id == t.id for tt in (role.tiles.all() if hasattr(role.tiles, 'all') else role.tiles))
                        except Exception:
                            present = True
                        if present:
                            role.tiles.remove(t)
                    except Exception:
                        pass

            # 2) réassigner selon formulaire (ignorer Suivi/Retrait qui sont forcées)
            for perm_string in permissions:
                if perm_string.startswith(f'role_{role.id}_'):
                    try:
                        tile_id = int(perm_string.split('_')[2])
                    except Exception:
                        continue
                    if (suivi_tile and tile_id == suivi_tile.id) or (payout_tile and tile_id == payout_tile.id):
                        continue
                    tile_to_add = Tile.query.get(tile_id)
                    if tile_to_add:
                        try:
                            role.tiles.append(tile_to_add)
                        except Exception:
                            pass

            # 3) forcer Suivi pour tous
            if suivi_tile:
                try:
                    present_suivi = any(t.id == suivi_tile.id for t in (role.tiles.all() if hasattr(role.tiles, 'all') else role.tiles))
                except Exception:
                    present_suivi = False
                if not present_suivi:
                    role.tiles.append(suivi_tile)

            # 4) forcer Retrait pour ≠ super_admin, et l’enlever pour super_admin
            if payout_tile:
                if role.name != 'super_admin':
                    try:
                        present_payout = any(t.id == payout_tile.id for t in (role.tiles.all() if hasattr(role.tiles, 'all') else role.tiles))
                    except Exception:
                        present_payout = False
                    if not present_payout:
                        role.tiles.append(payout_tile)
                else:
                    # enlever "Retrait" de super_admin seulement si présent
                    try:
                        present_payout = any(t.id == payout_tile.id for t in (role.tiles.all() if hasattr(role.tiles, 'all') else role.tiles))
                    except Exception:
                        present_payout = False
                    if present_payout:
                        try:
                            role.tiles.remove(payout_tile)
                        except Exception:
                            pass

        db.session.commit()
        try:
            cache.delete_memoized(cached_admin_settings_roles_page)
        except Exception:
            pass
        flash("Permissions mises à jour avec succès.", "success")
        return redirect(url_for('admin_settings_roles'))

    # GET via cache
    return cached_admin_settings_roles_page()
    # GET: auto-réparation Suivi/Retrait par rôle
    roles = Role.query.order_by(Role.id).all()
    changed = False
    for r in roles:
        if suivi_tile:
            try:
                present = any(t.id == suivi_tile.id for t in (r.tiles.all() if hasattr(r.tiles, 'all') else r.tiles))
            except Exception:
                present = False
            if not present:
                r.tiles.append(suivi_tile); changed = True

        if payout_tile:
            try:
                present_p = any(t.id == payout_tile.id for t in (r.tiles.all() if hasattr(r.tiles, 'all') else r.tiles))
            except Exception:
                present_p = False
            if r.name != 'super_admin' and not present_p:
                r.tiles.append(payout_tile); changed = True
            if r.name == 'super_admin' and present_p:
                try:
                    r.tiles.remove(payout_tile); changed = True
                except Exception:
                    pass
    if changed:
        db.session.commit()

    tiles = Tile.query.order_by(Tile.id).all()
    # NOUVEAU: role_tiles_map via 1 seul SELECT sur l’association (pas de .tiles.all() par rôle)
    pairs = db.session.query(role_tiles.c.role_id, role_tiles.c.tile_id).all()
    role_tiles_map = {}
    for r in roles:
        role_tiles_map[r.id] = []
    for rid, tid in pairs:
        if rid in role_tiles_map:
            role_tiles_map[rid].append(tid)

    return render_template(
        'admin_settings_roles.html',
        roles=roles,
        tiles=tiles,
        suivi_tile_id=(suivi_tile.id if suivi_tile else None),
        payout_tile_id=(payout_tile.id if payout_tile else None),
        role_tiles_map=role_tiles_map
    )
@app.route('/k4d3t/payout', methods=['GET'])
def admin_payout():
    if not session.get('admin_logged_in'):
        flash("Veuillez vous connecter.", "error")
        return redirect(url_for('admin_login'))
    # Autoriser TOUS les rôles admin, y compris super_admin
    user = User.query.filter_by(username=session.get('username')).first()
    if not user or not user.role:
        flash("Accès non autorisé.", "error")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_payout.html')
    
# --- Helper: solde disponible pour un utilisateur (commission - retraits déjà payés) ---
# --- Helper: solde disponible pour un utilisateur (commission - retraits déjà payés) ---
def get_user_available_balance(user):
    """
    Calcule le solde disponible = (Total CA complété × % commission du user) - retraits déjà 'completed'.
    Pour super_admin: % = 100 - somme des % des autres utilisateurs (≠ super_admin).
    """
    if not user or not user.role:
        return 0.0

    # 1) Total CA complété (toutes périodes)
    total_completed_revenue = db.session.query(
        db.func.coalesce(db.func.sum(AbandonedCart.total_price), 0.0)
    ).filter(AbandonedCart.status == 'completed').scalar() or 0.0

    # 2) Pourcentage effectif
    if user.role.name == 'super_admin':
        other_pct = get_non_super_total_percentage()
        user_pct = max(0.0, 100.0 - other_pct)
    else:
        user_pct = float(user.revenue_share_percentage or 0.0)

    gross_commission = total_completed_revenue * (user_pct / 100.0)

    # 3) Total déjà retiré par CET utilisateur (statut 'completed')
    withdrawn_total = db.session.query(
        db.func.coalesce(db.func.sum(Payout.amount), 0.0)
    ).filter(
        Payout.user_id == user.id,
        Payout.status == 'completed'
    ).scalar() or 0.0

    available = max(0.0, gross_commission - withdrawn_total)
    return float(available)

    # --- API: solde disponible du user connecté pour la tuile Retrait ---
@app.route('/api/payout/balance', methods=['GET'])
def api_payout_balance():
    if not session.get('admin_logged_in'):
        return jsonify({"status": "error", "message": "Non autorisé"}), 403
    user = User.query.filter_by(username=session.get('username')).first()
    if not user or not user.role:
        return jsonify({"status": "error", "message": "Non autorisé"}), 403

    available = get_user_available_balance(user)
    return jsonify({
        "status": "success",
        "available": round(float(available), 2),
        "currency": "XOF"
    }), 200

# --- Historique des retraits (user courant) AVEC tri/offset/limit ---
@app.route('/api/payout/history', methods=['GET'])
def api_payout_history():
    if not session.get('admin_logged_in'):
        return jsonify({"status": "error", "message": "Non autorisé"}), 403
    user = User.query.filter_by(username=session.get('username')).first()
    # Autoriser TOUS les rôles (y compris super_admin)
    if not user or not user.role:
        return jsonify({"status": "error", "message": "Non autorisé"}), 403

    # Params: limit/offset triés et sécurisés
    try:
        limit = int(request.args.get('limit', 10))
    except Exception:
        limit = 10
    limit = max(1, min(limit, 50))  # entre 1 et 50

    try:
        offset = int(request.args.get('offset', 0))
    except Exception:
        offset = 0
    offset = max(0, offset)

    sort_by = (request.args.get('sort_by') or 'created_at').lower()
    sort_dir = (request.args.get('sort_dir') or 'desc').lower()
    sort_dir = 'asc' if sort_dir == 'asc' else 'desc'

    # Mapping de tri sécurisé
    sort_map = {
        'created_at': Payout.created_at,
        'amount': Payout.amount,
        'status': Payout.status,
        'external_id': Payout.external_id
    }
    order_col = sort_map.get(sort_by, Payout.created_at)
    order_clause = order_col.asc() if sort_dir == 'asc' else order_col.desc()

    base_q = Payout.query.filter_by(user_id=user.id)
    total_count = base_q.count()

    rows = base_q.order_by(order_clause).offset(offset).limit(limit).all()

    def short_id(x):
        if not x: return None
        return x if len(x) <= 10 else f"{x[:4]}…{x[-4:]}"
    items = [{
        "id": p.id,
        "date": p.created_at.strftime('%Y-%m-%d %H:%M'),
        "amount": float(p.amount),
        "currency": p.currency or "XOF",
        "status": p.status,
        "reference": p.external_id,
        "reference_short": short_id(p.external_id),
        "phone": p.phone,
        "mode": p.mode
    } for p in rows]

    next_offset = offset + len(items)
    has_more = next_offset < total_count

    return jsonify({
        "status": "success",
        "items": items,
        "total": total_count,
        "has_more": has_more,
        "next_offset": next_offset
    }), 200
    
@app.route('/api/payout/withdraw', methods=['POST'])
def api_payout_withdraw():
    if not session.get('admin_logged_in'):
        return jsonify({"status": "error", "message": "Non autorisé"}), 403
    user = User.query.filter_by(username=session.get('username')).first()
    if not user or not user.role or user.role.name == 'super_admin':
        return jsonify({"status": "error", "message": "Non autorisé"}), 403

    data = request.get_json(silent=True) or {}
    countryCode = (data.get('countryCode') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    withdraw_mode = (data.get('withdraw_mode') or '').strip().lower()
    try:
        amount = float(data.get('amount'))
    except Exception:
        amount = 0.0

    if not countryCode or not phone or not withdraw_mode or amount <= 0:
        return jsonify({"status": "error", "message": "Paramètres invalides"}), 400

    # Validation côté serveur: ne pas dépasser le solde disponible
    available = get_user_available_balance(user)
    if amount > available + 1e-9:
        return jsonify({
            "status": "error",
            "message": f"Montant supérieur au solde disponible. Solde: {round(float(available),2)} XOF."
        }), 400

    private_key = os.environ.get('MONEYFUSION_PRIVATE_KEY')
    if not private_key:
        return jsonify({"status": "error", "message": "Clé API Money Fusion manquante (MONEYFUSION_PRIVATE_KEY)"}), 500

    payload = {
        "countryCode": countryCode,
        "phone": phone,
        "amount": amount,
        "withdraw_mode": withdraw_mode,
        "webhook_url": url_for('api_withdraw_callback', _external=True)
    }

    def pick_external_id(res_json):
        # Essaie différents champs possibles
        for k in ("tokenPay", "token", "reference", "ref", "transaction_id"):
            v = res_json.get(k)
            if v: return v
        data = res_json.get("data") or {}
        for k in ("tokenPay", "token", "reference", "ref", "transaction_id"):
            v = (data.get(k) if isinstance(data, dict) else None)
            if v: return v
        return None

    try:
        r = requests.post(
            "https://pay.moneyfusion.net/api/v1/withdraw",
            json=payload,
            headers={
                "moneyfusion-private-key": private_key,
                "Content-Type": "application/json"
            },
            timeout=20
        )
        r.raise_for_status()
        res = r.json()
        statut_ok = bool(res.get("statut"))
        ext_id = pick_external_id(res) if statut_ok else None

        # Enregistrer la demande de retrait
        payout = Payout(
            user_id=user.id,
            amount=amount,
            currency="XOF",
            country_code=countryCode,
            phone=phone,
            mode=withdraw_mode,
            status='pending' if statut_ok else 'failed',
            external_id=ext_id,
            provider_payload=res
        )
        db.session.add(payout)
        db.session.commit()

        # Log + réponse
        log_action("payout_initiated", {
            "username": session.get('username'),
            "payload": payload,
            "response": res,
            "payout_id": payout.id
        })

        # Renvoie statut HTTP 200 si statut_ok sinon 400
        return jsonify(res), 200 if statut_ok else 400
    except requests.exceptions.RequestException as e:
        # Enregistrer l'échec
        payout = Payout(
            user_id=user.id,
            amount=amount,
            currency="XOF",
            country_code=countryCode,
            phone=phone,
            mode=withdraw_mode,
            status='failed',
            external_id=None,
            provider_payload={"error": str(e)}
        )
        db.session.add(payout)
        db.session.commit()
        return jsonify({"status": "error", "message": f"Erreur API: {e}"}), 502


@app.route('/api/withdraw/callback', methods=['POST'])
def api_withdraw_callback():
    """
    Webhook de Money Fusion pour les retraits.
    Attend event: payout.session.completed | payout.session.cancelled
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return "", 400

    event = (data.get("event") or "").lower()
    tokenPay = data.get("tokenPay") or (data.get("data", {}) if isinstance(data.get("data"), dict) else {}).get("tokenPay")

    new_status = None
    if "completed" in event:
        new_status = "completed"
    elif "cancel" in event or "failed" in event or "error" in event:
        new_status = "cancelled"

    updated = False
    if tokenPay and new_status:
        payout = Payout.query.filter_by(external_id=tokenPay).order_by(Payout.id.desc()).first()
        if payout:
            payout.status = new_status
            payout.updated_at = datetime.now(timezone.utc)
            # merge/append webhook payload
            try:
                existing = payout.provider_payload or {}
                if isinstance(existing, dict):
                    existing["webhook_last"] = data
                    payout.provider_payload = existing
            except Exception:
                payout.provider_payload = data
            db.session.commit()
            updated = True

    log_action("payout_webhook", {"event": event, "tokenPay": tokenPay, "updated": updated, "payload": data})
    return "", 200

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

@app.route('/_debug/ip')
def debug_ip():
    if not session.get('admin_logged_in'):  # simple protection
        return "Unauthorized", 403
    try:
        ip = requests.get('https://api.ipify.org', timeout=5).text.strip()
        return f"Egress IP: {ip}"
    except Exception as e:
        return f"Error: {e}", 500
        


# --- Création des index en prod si manquants (PostgreSQL) ---
def ensure_admin_indexes():
    try:
        if db.engine.dialect.name in ('postgresql', 'postgres'):
            with db.engine.connect() as conn:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ab_cart_status ON abandoned_cart (status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ab_cart_created_at ON abandoned_cart (created_at)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ab_cart_status_created ON abandoned_cart (status, created_at)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_email_sendlog_sent_at ON email_send_log (sent_at)"))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_user_role_id ON \"user\" (role_id)'))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_role_tiles_role ON role_tiles (role_id)"))
    except Exception as e:
        logging.warning(f"ensure_admin_indexes: {e}")

def ensure_product_new_columns():
    try:
        dialect = db.engine.dialect.name
        stmts_pg = [
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS hero_title VARCHAR(255)",
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS hero_subtitle TEXT",
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS hero_cta_label VARCHAR(80)",
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS demo_video_url VARCHAR(255)",
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS demo_video_text VARCHAR(255)",
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS final_cta_title VARCHAR(255)",
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS final_cta_label VARCHAR(80)",
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS benefits JSONB",
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS includes JSONB",
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS guarantees JSONB",
        ]
        stmts_generic = [
            "ALTER TABLE product ADD COLUMN hero_title TEXT",
            "ALTER TABLE product ADD COLUMN hero_subtitle TEXT",
            "ALTER TABLE product ADD COLUMN hero_cta_label TEXT",
            "ALTER TABLE product ADD COLUMN demo_video_url TEXT",
            "ALTER TABLE product ADD COLUMN demo_video_text TEXT",
            "ALTER TABLE product ADD COLUMN final_cta_title TEXT",
            "ALTER TABLE product ADD COLUMN final_cta_label TEXT",
            "ALTER TABLE product ADD COLUMN benefits JSON",
            "ALTER TABLE product ADD COLUMN includes JSON",
            "ALTER TABLE product ADD COLUMN guarantees JSON",
        ]
        stmts = stmts_pg if dialect in ('postgresql', 'postgres') else stmts_generic
        with db.engine.connect() as conn:
            for sql in stmts:
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass
    except Exception as e:
        logging.warning(f"ensure_product_new_columns: {e}")
        
        
# --- MODIFICATION DANS LA FONCTION DE DÉMARRAGE `if __name__ == '__main__':` ---
# Remplacez votre bloc `if __name__ == '__main__':` par celui-ci pour tout initialiser correctement.
if __name__ == '__main__':
    with app.app_context():

        try:
            ip = requests.get('https://api.ipify.org', timeout=5).text.strip()
            logger.info(f"Egress IP (public): {ip}")
        except Exception as e:
            logger.warning(f"Impossible de récupérer l’IP publique: {e}")
        ensure_admin_indexes() 
        ensure_product_new_columns()
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
