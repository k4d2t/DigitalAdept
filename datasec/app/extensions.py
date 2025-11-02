"""
Flask extensions initialization
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_compress import Compress
from flask_caching import Cache

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)
talisman = Talisman()
compress = Compress()
cache = Cache()


def init_extensions(app):
    """Initialize Flask extensions"""
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    compress.init_app(app)
    cache.init_app(app)
    
    # Configure Talisman for security headers
    csp = {
        'default-src': ["'self'"],
        'script-src': [
            "'self'",
            "'unsafe-inline'",  # For Alpine.js inline scripts
            "https://cdn.jsdelivr.net",  # CDN for Alpine.js
            "https://unpkg.com",  # CDN for libraries
        ],
        'style-src': [
            "'self'",
            "'unsafe-inline'",  # For Tailwind inline styles
            "https://cdn.jsdelivr.net",
        ],
        'img-src': [
            "'self'",
            "data:",
            "https:",
        ],
        'font-src': [
            "'self'",
            "data:",
            "https://fonts.gstatic.com",
        ],
        'connect-src': [
            "'self'",
        ],
        'frame-src': ["'none'"],
        'object-src': ["'none'"],
        'base-uri': ["'self'"],
        'form-action': ["'self'"],
    }
    
    talisman.init_app(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=['script-src'],
        force_https=app.config.get('PREFERRED_URL_SCHEME') == 'https',
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        strict_transport_security_include_subdomains=True,
        frame_options='DENY',
        referrer_policy='strict-origin-when-cross-origin',
    )
