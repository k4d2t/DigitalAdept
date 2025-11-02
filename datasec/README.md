# DataSec - Cybersecurity Company Website

Site vitrine professionnel pour DataSec, entreprise spécialisée en cybersécurité et solutions IA. Application Flask modulaire, sécurisée et scalable, prête pour déploiement MVP sur Railway avec possibilité de migration vers VPS.

## 🚀 Caractéristiques

### Architecture
- **App Factory Pattern** : Architecture modulaire et testable
- **Blueprints** : Organisation par fonctionnalité (main, services, solutions, contact, legal)
- **Configuration séparée** : Environnements dev/prod distincts
- **Base de données** : SQLite pour MVP, extensible PostgreSQL

### Sécurité
- **Headers HTTP strictes** : CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- **HTTPS obligatoire** en production (Flask-Talisman)
- **CSRF Protection** (Flask-WTF)
- **Rate Limiting** (Flask-Limiter)
- **Validation serveur** complète des formulaires
- **hCaptcha/Turnstile** : Protection anti-spam
- **Secrets en variables d'environnement**

### SEO & Performance
- **Structure sémantique HTML5** (header, main, article, footer)
- **Meta tags complets** : OG, Twitter Card, hreflang FR/EN
- **Canonical URLs** automatiques
- **robots.txt** et **sitemap.xml** dynamiques
- **Lazy loading** des images
- **Compression** (Flask-Compress)
- **Cache** (Flask-Caching)
- **Core Web Vitals** optimisés

### Frontend
- **TailwindCSS** : Design responsive et moderne
- **Alpine.js** : Interactivité légère sans framework lourd
- **Psychologie des couleurs** : Bleu (confiance), gris (professionnalisme), blanc (clarté)
- **Animations sobres** : Transitions fluides
- **Mobile-first** : Responsive sur tous écrans

### Fonctionnalités
- **Formulaire de contact** : Validation côté serveur + client
- **Intégration Telegram Bot API** : Notifications instantanées
- **Fallback email** : Si Telegram indisponible
- **Analytics simples** : Tracking des pages vues
- **Multi-langue** : Structure prête FR/EN

## 📁 Structure du Projet

```
datasec/
├── app/
│   ├── __init__.py              # App factory
│   ├── models.py                # Modèles de base de données
│   ├── extensions.py            # Extensions Flask
│   ├── blueprints/
│   │   ├── main/                # Pages principales (home, about, references)
│   │   ├── services/            # Services cybersécurité (6 pages)
│   │   ├── solutions/           # Solutions (4 pages)
│   │   ├── contact/             # Formulaire de contact
│   │   ├── legal/               # Pages légales
│   │   └── utils.py             # Routes utilitaires (robots, sitemap)
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   └── templates/
│       ├── base.html            # Template de base
│       ├── main/
│       ├── services/
│       ├── solutions/
│       ├── contact/
│       ├── legal/
│       ├── errors/
│       ├── components/
│       └── sitemap.xml
├── config/
│   ├── __init__.py
│   └── config.py                # Configuration par environnement
├── instance/                    # Données locales (gitignored)
├── migrations/                  # Migrations de base de données
├── logs/                        # Fichiers de logs
├── .env.example                 # Template de variables d'environnement
├── requirements.txt             # Dépendances Python
├── wsgi.py                      # Point d'entrée WSGI
├── Procfile                     # Configuration Railway/Heroku
├── runtime.txt                  # Version Python
└── README.md                    # Documentation
```

## 🛠️ Installation

### Prérequis
- Python 3.11+
- PostgreSQL (pour production) ou SQLite (pour MVP)
- Redis (optionnel, pour rate limiting)

### Installation locale

1. **Cloner le repository**
```bash
git clone <repository-url>
cd datasec
```

2. **Créer un environnement virtuel**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

4. **Configuration**
```bash
cp .env.example .env
# Éditer .env et configurer vos variables d'environnement
```

5. **Initialiser la base de données**
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

6. **Lancer l'application**
```bash
# Mode développement
flask run

# Ou avec gunicorn (production)
gunicorn wsgi:app
```

L'application sera accessible sur `http://localhost:5000`

## 🔧 Configuration

### Variables d'environnement obligatoires

```env
# Flask
SECRET_KEY=your-super-secret-key-change-this-in-production
FLASK_ENV=production

# Base de données
DATABASE_URL=postgresql://user:password@host:port/database

# Telegram (notifications de contact)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# hCaptcha (anti-spam)
HCAPTCHA_SITE_KEY=your_site_key
HCAPTCHA_SECRET_KEY=your_secret_key
```

### Variables d'environnement optionnelles

```env
# Redis (pour rate limiting et cache)
REDIS_URL=redis://localhost:6379

# Email (fallback)
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your_email
MAIL_PASSWORD=your_password

# Logs
LOG_LEVEL=INFO
```

## 🚢 Déploiement

### Déploiement sur Railway

1. **Créer un nouveau projet sur Railway**
   - Se connecter sur [Railway.app](https://railway.app)
   - Cliquer sur "New Project"

2. **Connecter le repository GitHub**
   - Sélectionner le repository
   - Railway détectera automatiquement le Procfile

3. **Configurer les variables d'environnement**
   - Dans les paramètres du projet, ajouter toutes les variables d'environnement
   - Railway fournira automatiquement DATABASE_URL pour PostgreSQL

4. **Ajouter PostgreSQL**
   - Cliquer sur "New" -> "Database" -> "Add PostgreSQL"
   - Railway configurera automatiquement DATABASE_URL

5. **Déployer**
   - Railway déploiera automatiquement à chaque push sur la branche principale
   - L'application sera accessible sur l'URL fournie par Railway

### Migration vers VPS

Pour migrer vers un VPS après le MVP :

1. **Configurer le serveur**
```bash
# Installer les dépendances système
sudo apt update
sudo apt install python3 python3-pip python3-venv nginx postgresql

# Créer l'utilisateur applicatif
sudo useradd -m -s /bin/bash datasec

# Configurer PostgreSQL
sudo -u postgres createuser datasec
sudo -u postgres createdb datasec_db
sudo -u postgres psql -c "ALTER USER datasec WITH PASSWORD 'secure_password';"
```

2. **Déployer l'application**
```bash
# Se connecter en tant qu'utilisateur datasec
sudo su - datasec

# Cloner et installer
git clone <repository-url> /home/datasec/app
cd /home/datasec/app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurer l'environnement
cp .env.example .env
nano .env  # Éditer les variables

# Initialiser la base de données
flask db upgrade
```

3. **Configurer Gunicorn avec systemd**
```bash
sudo nano /etc/systemd/system/datasec.service
```

```ini
[Unit]
Description=DataSec Gunicorn Service
After=network.target

[Service]
User=datasec
Group=datasec
WorkingDirectory=/home/datasec/app
Environment="PATH=/home/datasec/app/venv/bin"
ExecStart=/home/datasec/app/venv/bin/gunicorn --workers 4 --bind unix:datasec.sock wsgi:app

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl start datasec
sudo systemctl enable datasec
```

4. **Configurer Nginx**
```bash
sudo nano /etc/nginx/sites-available/datasec
```

```nginx
server {
    listen 80;
    server_name datasec.fr www.datasec.fr;

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/datasec/app/datasec.sock;
    }

    location /static {
        alias /home/datasec/app/app/static;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/datasec /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

5. **Configurer SSL avec Let's Encrypt**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d datasec.fr -d www.datasec.fr
```

## 📊 Pages

### Pages principales (3)
- **Accueil** (`/`) : Page d'accueil avec présentation des services
- **À propos** (`/about`) : Présentation de l'entreprise
- **Références** (`/references`) : Projets et clients

### Services (6 + index)
- **Index** (`/services`) : Vue d'ensemble
- **Audit de sécurité** (`/services/audit-securite`)
- **Tests d'intrusion** (`/services/pentest`)
- **Formation** (`/services/formation`)
- **SOC** (`/services/soc`)
- **Conformité RGPD & ISO** (`/services/conformite`)
- **Réponse aux incidents** (`/services/incident-response`)

### Solutions (4 + index)
- **Index** (`/solutions`) : Vue d'ensemble
- **Protection d'infrastructure** (`/solutions/protection-infrastructure`)
- **Sécurité Cloud** (`/solutions/securite-cloud`)
- **Détection par IA** (`/solutions/ia-detection`)
- **Zero Trust** (`/solutions/zero-trust`)

### Contact & Légal (4)
- **Contact** (`/contact`) : Formulaire de contact
- **Mentions légales** (`/legal/mentions-legales`)
- **Politique de confidentialité** (`/legal/politique-confidentialite`)
- **CGV** (`/legal/cgv`)

### Utilitaires
- **robots.txt** (`/robots.txt`)
- **sitemap.xml** (`/sitemap.xml`)
- **Health check** (`/health`)

**Total : 20+ pages**

## 🔐 Sécurité

### Headers HTTP

L'application configure automatiquement les headers de sécurité :
- **Content-Security-Policy** : Prévient les attaques XSS
- **Strict-Transport-Security** : Force HTTPS
- **X-Frame-Options: DENY** : Prévient le clickjacking
- **X-Content-Type-Options: nosniff** : Prévient le MIME sniffing
- **Referrer-Policy: strict-origin-when-cross-origin** : Contrôle le referrer

### Protection CSRF

Tous les formulaires sont protégés contre les attaques CSRF grâce à Flask-WTF.

### Rate Limiting

L'API de contact est limitée à 5 requêtes par heure par IP pour prévenir le spam.

### Validation

Toute entrée utilisateur est validée côté serveur avec WTForms.

## 🧪 Tests

```bash
# Lancer les tests (à implémenter)
pytest

# Avec coverage
pytest --cov=app
```

## 📝 Développement

### Ajouter une nouvelle page

1. Créer la route dans le blueprint approprié
2. Créer le template dans `app/templates/`
3. Ajouter l'entrée dans le sitemap (si nécessaire)

### Ajouter un nouveau service/solution

1. Ajouter l'entrée dans le dictionnaire `SERVICES` ou `SOLUTIONS`
2. Le slug sera automatiquement disponible
3. Le sitemap sera mis à jour automatiquement

## 📚 Technologies

- **Flask 3.1** : Framework web
- **SQLAlchemy** : ORM
- **PostgreSQL/SQLite** : Base de données
- **TailwindCSS** : Framework CSS
- **Alpine.js** : Framework JavaScript léger
- **Gunicorn** : Serveur WSGI
- **Nginx** : Reverse proxy (VPS)

## 📄 Licence

Propriétaire - © 2025 DataSec. Tous droits réservés.

## 👥 Support

Pour toute question ou assistance :
- Email : contact@datasec.fr
- Téléphone : +33 1 23 45 67 89

## 🎯 Roadmap

- [x] Structure modulaire Flask
- [x] Blueprints (main, services, solutions, contact, legal)
- [x] Templates SEO-ready
- [x] Sécurité (CSRF, rate limiting, headers)
- [x] Formulaire de contact avec Telegram
- [x] robots.txt et sitemap.xml
- [ ] Tests unitaires
- [ ] Admin panel pour gestion du contenu
- [ ] Blog pour articles de cybersécurité
- [ ] Portfolio projets détaillés
- [ ] Système de devis en ligne
- [ ] Chatbot IA pour support

## ⚠️ Production Optimizations (Before Going Live)

### Required for Production

1. **Environment Variables**
   - Set strong `SECRET_KEY` (use `python -c "import secrets; print(secrets.token_hex(32))"`)
   - Configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
   - Configure `HCAPTCHA_SITE_KEY` and `HCAPTCHA_SECRET_KEY`
   - Set `FLASK_ENV=production`

2. **Database**
   - Use PostgreSQL instead of SQLite
   - Configure regular backups
   - Set up connection pooling limits

3. **Security**
   - Enable rate limiting with Redis backend
   - Make hCaptcha mandatory (currently optional for MVP)
   - Review and tighten CSP policy for your specific needs
   - Add integrity checks (SRI) to CDN resources

4. **Performance**
   - Build TailwindCSS for production (removes unused CSS)
   - Use Redis for caching instead of filesystem
   - Optimize images and add lazy loading
   - Consider CDN for static assets

5. **Monitoring**
   - Set up error tracking (Sentry, etc.)
   - Configure uptime monitoring
   - Set up log aggregation
   - Monitor Core Web Vitals

### Recommended Optimizations

1. **TailwindCSS Production Build**
   ```bash
   # Install Tailwind CLI
   npm install -D tailwindcss
   npx tailwindcss -i ./app/static/css/style.css -o ./app/static/css/output.css --minify
   ```
   Then update templates to use `output.css` instead of CDN.

2. **Alpine.js with Build Step**
   - Download Alpine.js locally or use npm
   - Add integrity attribute to script tag
   - Consider using Alpine.js build mode

3. **Security Headers Enhancement**
   ```python
   # In production, tighten CSP by removing 'unsafe-inline'
   # Use nonce-based CSP or external scripts only
   ```

4. **Rate Limiting with Redis**
   ```python
   # In .env
   REDIS_URL=redis://your-redis-url
   ```

5. **Content Optimization**
   - Compress and optimize images
   - Use WebP format with fallbacks
   - Implement proper lazy loading
   - Minify CSS and JavaScript
