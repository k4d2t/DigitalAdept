"""
Utility routes - robots.txt, sitemap.xml, health check
"""
from flask import Blueprint, render_template, make_response, url_for, current_app
from datetime import datetime

utils_bp = Blueprint('utils', __name__)


@utils_bp.route('/robots.txt')
def robots():
    """robots.txt for SEO"""
    content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/

Sitemap: {url_for('utils.sitemap', _external=True)}
"""
    response = make_response(content)
    response.headers['Content-Type'] = 'text/plain'
    return response


@utils_bp.route('/sitemap.xml')
def sitemap():
    """Dynamic sitemap.xml for SEO"""
    from app.blueprints.services import SERVICES
    from app.blueprints.solutions import SOLUTIONS
    
    pages = []
    
    # Static pages
    static_pages = [
        ('main.index', '1.0', 'daily'),
        ('main.about', '0.8', 'weekly'),
        ('main.references', '0.7', 'weekly'),
        ('services.index', '0.9', 'weekly'),
        ('solutions.index', '0.9', 'weekly'),
        ('contact.index', '0.8', 'monthly'),
        ('legal.legal_notice', '0.3', 'yearly'),
        ('legal.privacy_policy', '0.3', 'yearly'),
        ('legal.terms_of_service', '0.3', 'yearly'),
    ]
    
    for endpoint, priority, changefreq in static_pages:
        try:
            url = url_for(endpoint, _external=True)
            pages.append({
                'loc': url,
                'lastmod': datetime.now().strftime('%Y-%m-%d'),
                'priority': priority,
                'changefreq': changefreq,
            })
        except Exception:
            pass
    
    # Service pages
    for slug in SERVICES.keys():
        try:
            url = url_for('services.detail', slug=slug, _external=True)
            pages.append({
                'loc': url,
                'lastmod': datetime.now().strftime('%Y-%m-%d'),
                'priority': '0.8',
                'changefreq': 'monthly',
            })
        except Exception:
            pass
    
    # Solution pages
    for slug in SOLUTIONS.keys():
        try:
            url = url_for('solutions.detail', slug=slug, _external=True)
            pages.append({
                'loc': url,
                'lastmod': datetime.now().strftime('%Y-%m-%d'),
                'priority': '0.8',
                'changefreq': 'monthly',
            })
        except Exception:
            pass
    
    sitemap_xml = render_template('sitemap.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response


@utils_bp.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}, 200
