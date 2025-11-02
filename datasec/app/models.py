"""
Database models for DataSec application
"""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class ContactMessage(db.Model):
    """Contact form submissions"""
    __tablename__ = 'contact_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    company = db.Column(db.String(100), nullable=True)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='new')  # new, in_progress, closed
    
    def __repr__(self):
        return f'<ContactMessage {self.email}>'


class Subscriber(db.Model):
    """Newsletter subscribers"""
    __tablename__ = 'subscribers'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    subscribed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    unsubscribed_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Subscriber {self.email}>'


class PageView(db.Model):
    """Analytics - Page views"""
    __tablename__ = 'page_views'
    
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(255), nullable=False)
    referrer = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    language = db.Column(db.String(5), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        db.Index('ix_page_views_created_at', 'created_at'),
        db.Index('ix_page_views_path', 'path'),
    )
    
    def __repr__(self):
        return f'<PageView {self.path}>'


class SiteSettings(db.Model):
    """Site configuration settings"""
    __tablename__ = 'site_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<SiteSettings {self.key}>'
