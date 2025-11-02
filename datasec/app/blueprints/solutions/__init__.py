"""
Solutions blueprint - Cybersecurity solutions pages
"""
from flask import Blueprint, render_template, url_for, abort
from app.extensions import cache

solutions_bp = Blueprint('solutions', __name__)


# Solutions data structure
SOLUTIONS = {
    'protection-infrastructure': {
        'title': 'Protection d\'Infrastructure',
        'short_description': 'Sécurisez votre infrastructure IT',
        'description': 'Solution complète pour protéger votre infrastructure contre les menaces modernes.',
        'features': [
            'Firewall nouvelle génération',
            'Protection anti-DDoS',
            'Segmentation réseau',
            'Monitoring en temps réel',
        ],
        'benefits': [
            'Réduction des risques de cyberattaque',
            'Conformité réglementaire',
            'Amélioration de la disponibilité',
            'ROI mesurable',
        ],
        'icon': 'server',
    },
    'securite-cloud': {
        'title': 'Sécurité Cloud',
        'short_description': 'Sécurisez vos environnements cloud',
        'description': 'Solutions de sécurité adaptées aux environnements cloud AWS, Azure, GCP.',
        'features': [
            'CASB (Cloud Access Security Broker)',
            'Sécurité multi-cloud',
            'Chiffrement des données',
            'Gestion des identités (IAM)',
        ],
        'benefits': [
            'Protection des données sensibles',
            'Visibilité complète',
            'Conformité cloud',
            'Réduction de la surface d\'attaque',
        ],
        'icon': 'cloud',
    },
    'ia-detection': {
        'title': 'Détection par IA',
        'short_description': 'Intelligence artificielle pour la cybersécurité',
        'description': 'Utilisez l\'IA pour détecter et prévenir les menaces avancées en temps réel.',
        'features': [
            'Machine Learning',
            'Détection d\'anomalies',
            'Analyse comportementale',
            'Prédiction des menaces',
        ],
        'benefits': [
            'Détection précoce des menaces',
            'Réduction des faux positifs',
            'Automatisation de la réponse',
            'Amélioration continue',
        ],
        'icon': 'cpu-chip',
    },
    'zero-trust': {
        'title': 'Architecture Zero Trust',
        'short_description': 'Ne faites confiance à personne par défaut',
        'description': 'Implémentation d\'une architecture Zero Trust pour une sécurité maximale.',
        'features': [
            'Authentification forte (MFA)',
            'Micro-segmentation',
            'Least privilege access',
            'Surveillance continue',
        ],
        'benefits': [
            'Protection contre les menaces internes',
            'Réduction de la surface d\'attaque',
            'Conformité renforcée',
            'Flexibilité pour le télétravail',
        ],
        'icon': 'lock-closed',
    },
}


@solutions_bp.route('/')
@cache.cached(timeout=300)
def index():
    """Solutions overview page"""
    seo = {
        'title': 'Nos Solutions - DataSec | Protection Infrastructure & Cloud',
        'description': 'Découvrez nos solutions de cybersécurité : protection d\'infrastructure, sécurité cloud, détection IA et Zero Trust.',
        'keywords': 'solutions cybersécurité, protection infrastructure, sécurité cloud, IA, Zero Trust',
        'canonical': url_for('solutions.index', _external=True),
        'og_type': 'website',
    }
    
    return render_template('solutions/index.html', seo=seo, solutions=SOLUTIONS)


@solutions_bp.route('/<slug>')
@cache.cached(timeout=300)
def detail(slug):
    """Individual solution detail page"""
    solution = SOLUTIONS.get(slug)
    
    if not solution:
        abort(404)
    
    seo = {
        'title': f'{solution["title"]} - DataSec',
        'description': solution['short_description'],
        'keywords': f'{solution["title"]}, cybersécurité, DataSec',
        'canonical': url_for('solutions.detail', slug=slug, _external=True),
        'og_type': 'article',
    }
    
    return render_template('solutions/detail.html', seo=seo, solution=solution, slug=slug)
