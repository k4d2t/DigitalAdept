import os
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

# --- Table d'association Many-to-Many pour Rôles <-> Tuiles ---
role_tiles = db.Table(
    'role_tiles',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('tile_id', db.Integer, db.ForeignKey('tile.id'), primary_key=True)
)

# --- Utilisateurs ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    # Relation rôle
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    role = db.relationship('Role', back_populates='users')

    # Commission (%) sur le CA
    revenue_share_percentage = db.Column(db.Float, nullable=False, default=0.0)

    # Historique des retraits
    payouts = db.relationship('Payout', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

# --- Rôles ---
class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    users = db.relationship('User', back_populates='role')
    tiles = db.relationship('Tile', secondary=role_tiles, back_populates='roles', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'

# --- Tuiles du dashboard ---
class Tile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    endpoint = db.Column(db.String(120), unique=True, nullable=False)  # ex: 'admin_products_page'
    description = db.Column(db.String(200))
    icon_svg = db.Column(db.Text, nullable=True)

    roles = db.relationship('Role', secondary=role_tiles, back_populates='roles', lazy='dynamic')

    def __repr__(self):
        return f'<Tile {self.name}>'

# --- Produit ---
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

    # Champs dynamiques pour la page produit (Hero, vidéo, CTA)
    hero_title = db.Column(db.String(255), nullable=True)
    hero_subtitle = db.Column(db.Text, nullable=True)
    hero_cta_label = db.Column(db.String(80), nullable=True)
    demo_video_url = db.Column(db.String(255), nullable=True)
    demo_video_text = db.Column(db.String(255), nullable=True)
    final_cta_title = db.Column(db.String(255), nullable=True)
    final_cta_label = db.Column(db.String(80), nullable=True)

    # Sections liste (JSON)
    benefits = db.Column(db.JSON, nullable=True, default=list)
    includes = db.Column(db.JSON, nullable=True, default=list)
    guarantees = db.Column(db.JSON, nullable=True, default=list)

    # Relations
    images = db.relationship('ProductImage', backref='product', lazy=True, cascade="all, delete-orphan")
    badges = db.relationship('ProductBadge', backref='product', lazy=True, cascade="all, delete-orphan")
    faqs = db.relationship('ProductFAQ', backref='product', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='product', lazy=True, cascade="all, delete-orphan")
    resource_files = db.relationship('ProductResourceFile', backref='product', lazy=True, cascade="all, delete-orphan")
    download_links = db.relationship('DownloadLink', backref='product', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Product {self.name}>'

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
    device_id = db.Column(db.String(64), nullable=True)

class ProductResourceFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    type = db.Column(db.String(50))
    url = db.Column(db.String(255))
    file_id = db.Column(db.String(255))

# --- Annonces ---
class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    type = db.Column(db.String(50), default='info')
    video_url = db.Column(db.String(255), nullable=True)
    btn_label = db.Column(db.String(100), nullable=True)
    btn_url = db.Column(db.String(255), nullable=True)

# --- Panier abandonné ---
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
    status = db.Column(db.String(20), default='abandoned')  # abandoned, completed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    whatsapp_number = db.Column(db.String(32), nullable=True)
    relaunch_count = db.Column(db.Integer, default=0)
    last_relaunch_at = db.Column(db.DateTime, nullable=True)
    currency = db.Column(db.String(10), nullable=False, default='XOF')  # devise d’origine choisie

    download_links = db.relationship('DownloadLink', backref='cart', lazy=True, cascade="all, delete-orphan")

class DownloadLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    cart_id = db.Column(db.Integer, db.ForeignKey('abandoned_cart.id'), nullable=False)
    token = db.Column(db.String(36), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    download_count = db.Column(db.Integer, default=0)

# --- Paramètres site ---
class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)

# --- Logs envois email ---
class EmailSendLog(db.Model):
    __table_args__ = (db.Index('ix_email_sendlog_sent_at', 'sent_at'),)
    id = db.Column(db.Integer, primary_key=True)
    recipient_email = db.Column(db.String(120), nullable=False)
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# --- Retraits ---
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
    provider_payload = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
