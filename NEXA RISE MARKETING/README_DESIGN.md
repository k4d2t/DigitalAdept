# 🎨 Guide de Personnalisation - NEXA RISE MARKETING

## 📸 Mockups et Illustrations

### Mockups actuels
Les mockups sont créés avec du **CSS pur** (pas d'images) :

1. **Hero Mockup** (section accueil) :
   - Fichier : `style.css` lignes ~700-750
   - Classes : `.hero-mockup`, `.mockup-screen`, `.mockup-content`
   - Style : Écran avec bordures arrondies et ombres

2. **Portfolio Mockups** (section portfolio) :
   - Fichier : `style.css` lignes ~900-1000
   - Classes : `.portfolio-mockup`, `.mockup-browser`, `.browser-content`
   - Style : Navigateur avec points colorés et contenu simulé

### Comment les changer

#### Option 1 : Remplacer par de vraies images
```html
<!-- Dans index.html, remplacer : -->
<div class="hero-mockup">
    <div class="mockup-screen">
        <!-- contenu CSS -->
    </div>
</div>

<!-- Par : -->
<div class="hero-image">
    <img src="votre-mockup.jpg" alt="Mockup" class="real-mockup">
</div>
```

```css
/* Dans style.css, ajouter : */
.real-mockup {
    width: 100%;
    max-width: 500px;
    border-radius: var(--border-radius-xl);
    box-shadow: var(--shadow-xl);
}
```

#### Option 2 : Modifier les couleurs/styles CSS
```css
/* Changer les couleurs des mockups */
.mockup-screen {
    background: #votre-couleur; /* au lieu de var(--white) */
}

.mockup-content {
    background: #votre-couleur; /* au lieu de var(--gray-50) */
}
```

## 🎯 Icônes

### Icônes actuelles
Utilisation de **Font Awesome** :
- Service cards : `fas fa-bullhorn`, `fas fa-palette`, `fas fa-code`, `fas fa-chart-line`
- Contact : `fas fa-envelope`, `fas fa-phone`, `fas fa-map-marker-alt`, `fas fa-clock`
- Theme toggle : `fas fa-moon` / `fas fa-sun`

### Comment les changer

#### Option 1 : Changer les icônes Font Awesome
```html
<!-- Dans index.html, remplacer : -->
<i class="fas fa-bullhorn"></i>

<!-- Par : -->
<i class="fas fa-rocket"></i> <!-- ou toute autre icône FA -->
```

#### Option 2 : Utiliser vos propres icônes SVG
```html
<!-- Remplacer : -->
<i class="fas fa-bullhorn"></i>

<!-- Par : -->
<svg class="custom-icon" width="24" height="24" viewBox="0 0 24 24">
    <path d="votre-path-svg"/>
</svg>
```

```css
/* Dans style.css */
.custom-icon {
    width: 24px;
    height: 24px;
    fill: currentColor;
}
```

## 🎨 Couleurs et Thème

### Couleurs principales
```css
:root {
    --primary-color: #2563eb;    /* Bleu principal */
    --accent-color: #f59e0b;     /* Orange accent */
    --gray-50: #f8fafc;          /* Gris très clair */
    --gray-900: #0f172a;         /* Gris très foncé */
}
```

### Comment changer les couleurs
1. Modifier les variables CSS dans `:root`
2. Ou remplacer directement les couleurs dans les classes

## 🌊 Effets Vapeur

### Effets actuels
- **Titre principal** : Effet vapeur avec blur et text-shadow
- **Délimiteurs de sections** : Bordures animées avec effet vapeur
- **Stats section** : Bordures haut/bas avec animation

### Comment modifier
```css
/* Intensité de l'effet vapeur */
@keyframes vapor-effect {
    0%, 100% {
        filter: blur(0px);           /* ← Modifier ici */
        text-shadow: 0 0 5px rgba(148, 163, 184, 0.3);
    }
    50% {
        filter: blur(1px);           /* ← Modifier ici */
        text-shadow: 0 0 12px rgba(148, 163, 184, 0.5);
    }
}
```

## 📱 Responsive

### Breakpoints
- **Desktop** : > 1024px
- **Tablet** : 768px - 1024px  
- **Mobile** : < 768px

### Modifier le responsive
```css
@media (max-width: 768px) {
    /* Vos styles mobile ici */
}
```

## 🚀 Personnalisation Rapide

### Changer le logo
1. Remplacer `Logo/NEXA RISE LOGO N.png` par votre logo
2. Ajuster la taille dans `.nav-logo .logo { height: 40px; }`

### Changer les couleurs principales
1. Modifier `--primary-color` et `--accent-color` dans `:root`
2. Toutes les couleurs s'adapteront automatiquement

### Ajouter vos propres images
1. Créer un dossier `images/` 
2. Ajouter vos images
3. Remplacer les mockups CSS par `<img src="images/votre-image.jpg">`

---

💡 **Conseil** : Commencez par modifier les couleurs et icônes, puis passez aux mockups si nécessaire !
