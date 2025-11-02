"""
Services blueprint - Cybersecurity services pages
"""
from flask import Blueprint, render_template, url_for, abort
from app.extensions import cache

services_bp = Blueprint('services', __name__)


# Service data structure
SERVICES = {
    'audit-securite': {
        'title': 'Audit de Sécurité',
        'short_description': 'Évaluation complète de votre infrastructure',
        'description': 'Nos experts réalisent un audit approfondi de votre infrastructure pour identifier les vulnérabilités et proposer des solutions adaptées.',
        'features': [
            'Analyse de vulnérabilités',
            'Tests d\'intrusion',
            'Audit de configuration',
            'Rapport détaillé avec recommandations',
        ],
        'icon': 'shield-check',
    },
    'pentest': {
        'title': 'Tests d\'Intrusion (Pentest)',
        'short_description': 'Simulation d\'attaques réelles',
        'description': 'Nos ethical hackers simulent des attaques réelles pour tester la résilience de vos systèmes.',
        'features': [
            'Pentest externe et interne',
            'Tests d\'applications web',
            'Tests d\'applications mobiles',
            'Social engineering',
        ],
        'icon': 'bug',
    },
    'formation': {
        'title': 'Formation en Cybersécurité',
        'short_description': 'Sensibilisation et formation',
        'description': 'Formez vos équipes aux bonnes pratiques de cybersécurité et aux menaces actuelles.',
        'features': [
            'Sensibilisation des employés',
            'Formation technique',
            'Simulations de phishing',
            'Certification',
        ],
        'icon': 'academic-cap',
    },
    'soc': {
        'title': 'SOC - Security Operations Center',
        'short_description': 'Surveillance 24/7',
        'description': 'Notre SOC assure une surveillance continue de votre infrastructure pour détecter et répondre aux menaces.',
        'features': [
            'Surveillance 24/7',
            'Détection des menaces',
            'Réponse aux incidents',
            'Rapports réguliers',
        ],
        'icon': 'eye',
    },
    'conformite': {
        'title': 'Conformité RGPD & ISO',
        'short_description': 'Mise en conformité réglementaire',
        'description': 'Nous vous accompagnons dans votre mise en conformité RGPD, ISO 27001 et autres normes.',
        'features': [
            'Audit de conformité',
            'Documentation',
            'Plan d\'action',
            'Accompagnement certification',
        ],
        'icon': 'document-check',
    },
    'incident-response': {
        'title': 'Réponse aux Incidents',
        'short_description': 'Intervention rapide en cas de cyberattaque',
        'description': 'Notre équipe d\'urgence intervient rapidement pour contenir et résoudre les incidents de sécurité.',
        'features': [
            'Intervention d\'urgence 24/7',
            'Analyse forensique',
            'Containment et éradication',
            'Plan de remédiation',
        ],
        'icon': 'fire',
    },
}


@services_bp.route('/')
@cache.cached(timeout=300)
def index():
    """Services overview page"""
    seo = {
        'title': 'Nos Services - DataSec | Cybersécurité & IA',
        'description': 'Découvrez nos services de cybersécurité : audit, pentest, formation, SOC, conformité RGPD et réponse aux incidents.',
        'keywords': 'services cybersécurité, audit sécurité, pentest, formation, SOC, RGPD, ISO 27001',
        'canonical': url_for('services.index', _external=True),
        'og_type': 'website',
    }
    
    return render_template('services/index.html', seo=seo, services=SERVICES)


@services_bp.route('/<slug>')
@cache.cached(timeout=300)
def detail(slug):
    """Individual service detail page"""
    service = SERVICES.get(slug)
    
    if not service:
        abort(404)
    
    seo = {
        'title': f'{service["title"]} - DataSec',
        'description': service['short_description'],
        'keywords': f'{service["title"]}, cybersécurité, DataSec',
        'canonical': url_for('services.detail', slug=slug, _external=True),
        'og_type': 'article',
    }
    
    return render_template('services/detail.html', seo=seo, service=service, slug=slug, SERVICES=SERVICES)
