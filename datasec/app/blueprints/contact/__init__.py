"""
Contact blueprint - Contact form with validation and Telegram/Email integration
"""
import os
import requests
from flask import Blueprint, render_template, url_for, request, flash, redirect, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Length, Optional
from app.extensions import limiter, db
from app.models import ContactMessage

contact_bp = Blueprint('contact', __name__)


class ContactForm(FlaskForm):
    """Contact form with validation"""
    name = StringField(
        'Nom complet',
        validators=[
            DataRequired(message='Le nom est requis'),
            Length(min=2, max=100, message='Le nom doit contenir entre 2 et 100 caractères')
        ]
    )
    email = StringField(
        'Email',
        validators=[
            DataRequired(message='L\'email est requis'),
            Email(message='Email invalide'),
            Length(max=120)
        ]
    )
    phone = StringField(
        'Téléphone',
        validators=[
            Optional(),
            Length(max=20, message='Numéro de téléphone trop long')
        ]
    )
    company = StringField(
        'Entreprise',
        validators=[
            Optional(),
            Length(max=100, message='Nom d\'entreprise trop long')
        ]
    )
    subject = SelectField(
        'Sujet',
        choices=[
            ('audit', 'Demande d\'audit de sécurité'),
            ('pentest', 'Tests d\'intrusion'),
            ('formation', 'Formation en cybersécurité'),
            ('soc', 'SOC - Surveillance'),
            ('conformite', 'Conformité RGPD/ISO'),
            ('incident', 'Réponse aux incidents'),
            ('autre', 'Autre demande'),
        ],
        validators=[DataRequired(message='Le sujet est requis')]
    )
    message = TextAreaField(
        'Message',
        validators=[
            DataRequired(message='Le message est requis'),
            Length(min=10, max=5000, message='Le message doit contenir entre 10 et 5000 caractères')
        ]
    )


def verify_hcaptcha(response_token):
    """Verify hCaptcha response"""
    secret_key = current_app.config.get('HCAPTCHA_SECRET_KEY')
    
    if not secret_key:
        current_app.logger.warning('hCaptcha secret key not configured')
        # In production, you should make CAPTCHA mandatory
        # For development/MVP without CAPTCHA configured, we allow it
        # TODO: Make CAPTCHA mandatory in production
        return True  # Skip verification if not configured
    
    # Check if response_token exists and is not empty
    if not response_token:
        current_app.logger.warning('hCaptcha response token is empty')
        return False
    
    try:
        verify_response = requests.post(
            'https://hcaptcha.com/siteverify',
            data={
                'secret': secret_key,
                'response': response_token,
            },
            timeout=10
        )
        result = verify_response.json()
        return result.get('success', False)
    except Exception as e:
        current_app.logger.error(f'hCaptcha verification error: {e}')
        return False


def send_telegram_notification(data):
    """Send contact form notification to Telegram"""
    bot_token = current_app.config.get('TELEGRAM_BOT_TOKEN')
    chat_id = current_app.config.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        current_app.logger.warning('Telegram credentials not configured')
        return False
    
    message = f"""
📩 *Nouveau message de contact*

👤 *Nom:* {data['name']}
✉️ *Email:* {data['email']}
📱 *Téléphone:* {data.get('phone', 'N/A')}
🏢 *Entreprise:* {data.get('company', 'N/A')}
📋 *Sujet:* {data['subject']}

💬 *Message:*
{data['message']}
"""
    
    try:
        response = requests.post(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown',
            },
            timeout=10
        )
        return response.ok
    except Exception as e:
        current_app.logger.error(f'Telegram notification error: {e}')
        return False


def send_email_notification(data):
    """Send contact form notification via email (fallback)"""
    # This would use Flask-Mail or similar
    # For now, just log
    current_app.logger.info(f'Email notification would be sent for contact from {data["email"]}')
    return True


@contact_bp.route('/', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def index():
    """Contact page with form"""
    form = ContactForm()
    
    if form.validate_on_submit():
        # Verify hCaptcha
        captcha_response = request.form.get('h-captcha-response')
        if not verify_hcaptcha(captcha_response):
            flash('Échec de la vérification CAPTCHA. Veuillez réessayer.', 'error')
            return render_template('contact/index.html', form=form)
        
        # Save to database
        contact_message = ContactMessage(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            company=form.company.data,
            subject=form.subject.data,
            message=form.message.data,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:255]
        )
        
        try:
            db.session.add(contact_message)
            db.session.commit()
            
            # Send notification
            notification_data = {
                'name': form.name.data,
                'email': form.email.data,
                'phone': form.phone.data,
                'company': form.company.data,
                'subject': form.subject.data,
                'message': form.message.data,
            }
            
            # Try Telegram first, fallback to email
            if not send_telegram_notification(notification_data):
                send_email_notification(notification_data)
            
            flash('Votre message a été envoyé avec succès. Nous vous répondrons dans les plus brefs délais.', 'success')
            return redirect(url_for('contact.index'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error saving contact message: {e}')
            flash('Une erreur est survenue. Veuillez réessayer.', 'error')
    
    seo = {
        'title': 'Contact - DataSec | Contactez nos Experts',
        'description': 'Contactez DataSec pour discuter de vos besoins en cybersécurité. Notre équipe d\'experts est à votre écoute.',
        'keywords': 'contact, DataSec, cybersécurité, devis, consultation',
        'canonical': url_for('contact.index', _external=True),
        'og_type': 'website',
    }
    
    hcaptcha_site_key = current_app.config.get('HCAPTCHA_SITE_KEY')
    
    return render_template('contact/index.html', form=form, seo=seo, hcaptcha_site_key=hcaptcha_site_key)
