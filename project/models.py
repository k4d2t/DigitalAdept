import os
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

# --- NOUVEAU : Table d'association pour la relation Many-to-Many ---
role_tiles = db.Table('role_tiles',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('tile_id', db.Integer, db.ForeignKey('tile.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    
    # --- MODIFIÉ : Le rôle est maintenant une relation ---
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    role = db.relationship('Role', back_populates='users')

    # --- NOUVEAU : Pourcentage de commission pour le CA ---
    revenue_share_percentage = db.Column(db.Float, nullable=False, default=0)
    # Historique des retraits
    payouts = db.relationship('Payout', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

# --- NOUVEAU : Modèle pour les Rôles ---
class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    
    users = db.relationship('User', back_populates='role')
    tiles = db.relationship('Tile', secondary=role_tiles, back_populates='roles', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'

# --- NOUVEAU : Modèle pour les Tuiles du Dashboard ---
class Tile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    endpoint = db.Column(db.String(120), unique=True, nullable=False) # ex: 'admin_products_page'
    description = db.Column(db.String(200))
    icon_svg = db.Column(db.Text, nullable=True) # Optionnel: pour une icône
    
    roles = db.relationship('Role', secondary=role_tiles, back_populates='tiles', lazy='dynamic')

    def __repr__(self):
        return f'<Tile {self.name}>'

# (Le reste de vos modèles : Product, ProductImage, etc. reste inchangé)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    short_description = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    old_price = db.Column(db.Integer, nullable=True)
    currency = db.Column(db.String(10), nullable=False, default='XOF')
    featured = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(100), nullable=True)
    stock = db.Column(db.Integer, default=0)
    sku = db.Column(db.String(100), unique=True, nullable=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    
    images = db.relationship('ProductImage', backref='product', lazy=True, cascade="all, delete-orphan")
    badges = db.relationship('ProductBadge', backref='product', lazy=True, cascade="all, delete-orphan")
    faqs = db.relationship('ProductFAQ', backref='product', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='product', lazy=True, cascade="all, delete-orphan")
    resource_files = db.relationship('ProductResourceFile', backref='product', lazy=True, cascade="all, delete-orphan")
    download_links = db.relationship('DownloadLink', backref='product', lazy=True, cascade="all, delete-orphan")

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    url = db.Column(db.String(255), nullable=False)

class ProductBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    text = db.Column(db.String(100), nullable=False)

class ProductFAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)

class ProductResourceFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    type = db.Column(db.String(50))
    url = db.Column(db.String(255))
    file_id = db.Column(db.String(255))

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    type = db.Column(db.String(50), default='info')
    video_url = db.Column(db.String(255), nullable=True)
    btn_label = db.Column(db.String(100), nullable=True)
    btn_url = db.Column(db.String(255), nullable=True)

class AbandonedCart(db.Model):
    __table_args__ = (
        db.Index('ix_ab_cart_status', 'status'),
        db.Index('ix_ab_cart_created_at', 'created_at'),
        db.Index('ix_ab_cart_status_created', 'status', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    customer_name = db.Column(db.String(120), nullable=True)
    cart_content = db.Column(db.JSON, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='abandoned') # abandoned, completed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    whatsapp_number = db.Column(db.String(32), nullable=True)  # élargi à 32
    relaunch_count = db.Column(db.Integer, default=0)
    last_relaunch_at = db.Column(db.DateTime, nullable=True)
    # NOUVEAU: devise d’origine du client (affichage emails, analytics)
    currency = db.Column(db.String(10), nullable=False, default='XOF')

    download_links = db.relationship('DownloadLink', backref='cart', lazy=True, cascade="all, delete-orphan")


class DownloadLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    cart_id = db.Column(db.Integer, db.ForeignKey('abandoned_cart.id'), nullable=False)
    token = db.Column(db.String(36), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    download_count = db.Column(db.Integer, default=0)

class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)

class EmailSendLog(db.Model):
    __table_args__ = (db.Index('ix_email_sendlog_sent_at', 'sent_at'),)
    id = db.Column(db.Integer, primary_key=True)
    recipient_email = db.Column(db.String(120), nullable=False)
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# --- NEW: Historique des retraits ---
class Payout(db.Model):
    __table_args__ = (
        db.Index('ix_payout_user_status', 'user_id', 'status'),
        db.Index('ix_payout_external_id', 'external_id'),
        db.Index('ix_payout_created_at', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default='XOF')
    country_code = db.Column(db.String(5), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    mode = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, completed, cancelled, failed
    external_id = db.Column(db.String(120), nullable=True)  # tokenPay / reference MoneyFusion
    provider_payload = db.Column(db.JSON, nullable=True)     # réponse brute du provider
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
