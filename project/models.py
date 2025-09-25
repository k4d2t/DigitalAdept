from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    short_description = db.Column(db.String(512))
    description = db.Column(db.Text)
    price = db.Column(db.Integer, nullable=False)
    old_price = db.Column(db.Integer)
    currency = db.Column(db.String(8))
    featured = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(128))
    stock = db.Column(db.Integer)
    sku = db.Column(db.String(64))
    slug = db.Column(db.String(256), unique=True, index=True)

    images = db.relationship("ProductImage", backref="product", cascade="all, delete-orphan")
    badges = db.relationship("ProductBadge", backref="product", cascade="all, delete-orphan")
    faqs = db.relationship("ProductFAQ", backref="product", cascade="all, delete-orphan")
    resource_files = db.relationship("ProductResourceFile", backref="product", cascade="all, delete-orphan")
    comments = db.relationship("Comment", backref="product", cascade="all, delete-orphan")

class ProductImage(db.Model):
    __tablename__ = "product_images"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    url = db.Column(db.String(512), nullable=False)

class ProductBadge(db.Model):
    __tablename__ = "product_badges"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    type = db.Column(db.String(64))
    text = db.Column(db.String(255))

class ProductFAQ(db.Model):
    __tablename__ = "product_faqs"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    question = db.Column(db.Text)
    answer = db.Column(db.Text)

class ProductResourceFile(db.Model):
    __tablename__ = "product_resource_files"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    file_id = db.Column(db.String(128))
    type = db.Column(db.String(32))
    url = db.Column(db.String(512))

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    is_read = db.Column(db.Boolean, default=False)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False)

class SiteSetting(db.Model):
    __tablename__ = "site_settings"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)

class Announcement(db.Model):
    tablename = "announcements"
    id = db.Column(db.Integer, primary_key=True)    
    video_url = db.Column(db.String(255), nullable=True)
    btn_label = db.Column(db.String(100), nullable=True)
    btn_url = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    active = db.Column(db.Boolean, default=True)
    type = db.Column(db.String(64), default="general")  # exemple : promo, info, etc.
    
class DownloadLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    cart_id = db.Column(db.Integer, db.ForeignKey('abandoned_cart.id'), nullable=False)
    token = db.Column(db.String(36), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    download_count = db.Column(db.Integer, default=0)

class AbandonedCart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), nullable=False, index=True)
    customer_name = db.Column(db.String(150), nullable=True)
    cart_content = db.Column(db.JSON, nullable=False) # Stocke les produits du panier
    total_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    status = db.Column(db.String(50), default='abandoned') # ex: 'abandoned', 'recovered', 'contacted'
