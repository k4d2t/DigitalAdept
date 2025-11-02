"""
Flask application factory
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request
from config.config import config
from .extensions import init_extensions, db
from .models import PageView


def create_app(config_name=None):
    """Application factory pattern"""
    
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Initialize extensions
    init_extensions(app)
    
    # Configure logging
    configure_logging(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register context processors
    register_context_processors(app)
    
    # Register before/after request handlers
    register_request_handlers(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app


def configure_logging(app):
    """Configure application logging"""
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/datasec.log',
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('DataSec startup')


def register_blueprints(app):
    """Register application blueprints"""
    from .blueprints.main import main_bp
    from .blueprints.services import services_bp
    from .blueprints.solutions import solutions_bp
    from .blueprints.contact import contact_bp
    from .blueprints.legal import legal_bp
    from .blueprints.utils import utils_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(services_bp, url_prefix='/services')
    app.register_blueprint(solutions_bp, url_prefix='/solutions')
    app.register_blueprint(contact_bp, url_prefix='/contact')
    app.register_blueprint(legal_bp, url_prefix='/legal')
    app.register_blueprint(utils_bp)


def register_error_handlers(app):
    """Register error handlers"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(429)
    def ratelimit_error(error):
        return render_template('errors/429.html'), 429


def register_context_processors(app):
    """Register template context processors"""
    
    @app.context_processor
    def inject_globals():
        """Inject global variables into templates"""
        return {
            'site_name': 'DataSec',
            'current_year': __import__('datetime').datetime.now().year,
            'languages': app.config.get('LANGUAGES', ['fr', 'en']),
        }


def register_request_handlers(app):
    """Register before/after request handlers"""
    
    @app.before_request
    def log_request_info():
        """Log request information"""
        if not app.debug:
            app.logger.info(f'{request.method} {request.path}')
    
    @app.after_request
    def track_page_view(response):
        """Track page views for analytics"""
        if request.endpoint and not request.endpoint.startswith('static'):
            try:
                # Only track GET requests with 200 status
                if request.method == 'GET' and response.status_code == 200:
                    page_view = PageView(
                        path=request.path,
                        referrer=request.referrer,
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent', '')[:255],
                        language=request.accept_languages.best_match(app.config.get('LANGUAGES', ['fr']))
                    )
                    db.session.add(page_view)
                    db.session.commit()
            except Exception as e:
                app.logger.error(f'Error tracking page view: {e}')
                db.session.rollback()
        
        return response
    
    @app.after_request
    def add_security_headers(response):
        """Add additional security headers"""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        return response
