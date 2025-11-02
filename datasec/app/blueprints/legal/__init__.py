"""
Legal blueprint - Legal notices and privacy policy
"""
from flask import Blueprint, render_template, url_for
from app.extensions import cache

legal_bp = Blueprint('legal', __name__)


@legal_bp.route('/mentions-legales')
@cache.cached(timeout=86400)  # Cache for 24 hours
def legal_notice():
    """Legal notice page"""
    seo = {
        'title': 'Mentions Légales - DataSec',
        'description': 'Mentions légales du site DataSec.',
        'canonical': url_for('legal.legal_notice', _external=True),
        'robots': 'noindex, follow',
    }
    
    return render_template('legal/legal_notice.html', seo=seo)


@legal_bp.route('/politique-confidentialite')
@cache.cached(timeout=86400)  # Cache for 24 hours
def privacy_policy():
    """Privacy policy page"""
    seo = {
        'title': 'Politique de Confidentialité - DataSec',
        'description': 'Politique de confidentialité et protection des données personnelles - DataSec.',
        'canonical': url_for('legal.privacy_policy', _external=True),
        'robots': 'noindex, follow',
    }
    
    return render_template('legal/privacy_policy.html', seo=seo)


@legal_bp.route('/cgv')
@cache.cached(timeout=86400)  # Cache for 24 hours
def terms_of_service():
    """Terms of service page"""
    seo = {
        'title': 'Conditions Générales de Vente - DataSec',
        'description': 'Conditions générales de vente des services DataSec.',
        'canonical': url_for('legal.terms_of_service', _external=True),
        'robots': 'noindex, follow',
    }
    
    return render_template('legal/terms_of_service.html', seo=seo)
