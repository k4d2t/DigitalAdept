"""
Main blueprint - Home, About, References pages
"""
from flask import Blueprint, render_template, url_for
from app.extensions import cache

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@cache.cached(timeout=300)
def index():
    """Homepage"""
    seo = {
        'title': 'DataSec - Expert en Cybersécurité et Solutions IA',
        'description': 'DataSec est votre partenaire de confiance en cybersécurité et solutions IA. Protégez votre entreprise avec nos services de sécurité informatique de pointe.',
        'keywords': 'cybersécurité, sécurité informatique, IA, intelligence artificielle, protection données, audit sécurité',
        'canonical': url_for('main.index', _external=True),
        'og_type': 'website',
        'og_image': url_for('static', filename='img/og-image.jpg', _external=True),
    }
    
    return render_template('main/index.html', seo=seo)


@main_bp.route('/about')
@cache.cached(timeout=300)
def about():
    """About page"""
    seo = {
        'title': 'À Propos - DataSec | Expert Cybersécurité',
        'description': 'Découvrez DataSec, votre expert en cybersécurité et solutions IA. Notre équipe d\'experts vous accompagne dans la sécurisation de votre infrastructure.',
        'keywords': 'à propos, équipe, expertise, cybersécurité, DataSec',
        'canonical': url_for('main.about', _external=True),
        'og_type': 'website',
    }
    
    return render_template('main/about.html', seo=seo)


@main_bp.route('/references')
@cache.cached(timeout=300)
def references():
    """References page"""
    seo = {
        'title': 'Références - Nos Clients et Projets | DataSec',
        'description': 'Découvrez les références de DataSec et les projets de cybersécurité que nous avons réalisés pour nos clients.',
        'keywords': 'références, clients, projets, réalisations, cybersécurité',
        'canonical': url_for('main.references', _external=True),
        'og_type': 'website',
    }
    
    # Sample references data
    references = [
        {
            'name': 'Entreprise A',
            'sector': 'Finance',
            'service': 'Audit de sécurité',
            'description': 'Audit complet de la sécurité informatique et mise en conformité RGPD.'
        },
        {
            'name': 'Entreprise B',
            'sector': 'E-commerce',
            'service': 'Protection DDoS',
            'description': 'Mise en place d\'une solution de protection contre les attaques DDoS.'
        },
        {
            'name': 'Entreprise C',
            'sector': 'Santé',
            'service': 'Sécurisation des données',
            'description': 'Sécurisation des données patients et conformité HDS.'
        },
    ]
    
    return render_template('main/references.html', seo=seo, references=references)
