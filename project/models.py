ifrom flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='editor')

class SiteSetting(db.Model):
    __tablename__ = 'site_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_description = db.Column(db.String(255))
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    old_price = db.Column(db.Integer)
    currency = db.Column(db.String(10), nullable=False, default='XOF')
    featured = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(50))
    stock = db.Column(db.Integer, default=0)
    sku = db.Column(db.String(50), unique=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    images = db.relationship('ProductImage', backref='product', lazy=True, cascade="all, delete-orphan")
    badges = db.relationship('ProductBadge', backref='product', lazy=True, cascade="all, delete-orphan")
    faqs = db.relationship('ProductFAQ', backref='product', lazy=True, cascade="all, delete-orphan")
    resource_files = db.relationship('ProductResourceFile', backref='product', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='product', lazy=True, cascade="all, delete-orphan")

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    url = db.Column(db.String(255), nullable=False)

class ProductBadge(db.Model):
    __tablename__ = 'product_badges'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    type = db.Column(db.String(50))
    text = db.Column(db.String(50))

class ProductFAQ(db.Model):
    __tablename__ = 'product_faqs'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    question = db.Column(db.String(255), nullable=False)
    answer = db.Column(db.Text, nullable=False)

class ProductResourceFile(db.Model):
    __tablename__ = 'product_resource_files'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    type = db.Column(db.String(50))
    url = db.Column(db.String(255))
    file_id = db.Column(db.String(255))

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)

class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    active = db.Column(db.Boolean, default=True)
    type = db.Column(db.String(50), default='info')
    video_url = db.Column(db.String(255))
    btn_label = db.Column(db.String(50))
    btn_url = db.Column(db.String(255))

class AbandonedCart(db.Model):
    __tablename__ = 'abandoned_carts'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    customer_name = db.Column(db.String(255))
    whatsapp_number = db.Column(db.String(50), nullable=True)
    cart_content = db.Column(db.JSON, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='abandoned')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    relaunch_count = db.Column(db.Integer, default=0)
    last_relaunch_at = db.Column(db.DateTime, nullable=True)
    downloads = db.relationship('DownloadLink', backref='cart', lazy=True, cascade="all, delete-orphan")

class DownloadLink(db.Model):
    __tablename__ = 'download_links'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    cart_id = db.Column(db.Integer, db.ForeignKey('abandoned_carts.id'), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    download_count = db.Column(db.Integer, default=0)

class EmailSendLog(db.Model):
    __tablename__ = 'email_send_logs'
    id = db.Column(db.Integer, primary_key=True)
    sent_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    recipient_email = db.Column(db.String(255), nullable=False)
