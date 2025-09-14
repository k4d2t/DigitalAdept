// NEXA RISE MARKETING - JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Variables globales
    const navbar = document.querySelector('.navbar');
    const navMenu = document.querySelector('.nav-menu');
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.section');
    const contactForm = document.getElementById('contactForm');
    const themeToggle = document.getElementById('themeToggle');
    const body = document.body;
    
    // Configuration Telegram (à remplacer par vos vraies valeurs)
    const TELEGRAM_BOT_TOKEN = 'YOUR_BOT_TOKEN';
    const TELEGRAM_CHAT_ID = 'YOUR_CHAT_ID';
    
    // Navigation SPA
    function initSPANavigation() {
        navLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const targetSection = this.getAttribute('data-section');
                showSection(targetSection);
                updateActiveNavLink(this);
                closeMobileMenu();
            });
        });
        
        // Navigation par clavier
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeMobileMenu();
            }
        });
    }
    
    function showSection(sectionId) {
        sections.forEach(section => {
            section.classList.remove('active');
        });
        
        const targetSection = document.getElementById(sectionId);
        if (targetSection) {
            targetSection.classList.add('active');
            
            // Animation des éléments
            setTimeout(() => {
                animateSectionElements(targetSection);
            }, 100);
        }
        
        // Scroll vers le haut
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    
    function updateActiveNavLink(activeLink) {
        navLinks.forEach(link => {
            link.classList.remove('active');
        });
        activeLink.classList.add('active');
    }
    
    function animateSectionElements(section) {
        const animatedElements = section.querySelectorAll('.service-card, .portfolio-item, .stat-item');
        animatedElements.forEach((element, index) => {
            setTimeout(() => {
                element.style.opacity = '0';
                element.style.transform = 'translateY(30px)';
                element.style.transition = 'all 0.6s ease-out';
                
                setTimeout(() => {
                    element.style.opacity = '1';
                    element.style.transform = 'translateY(0)';
                }, 50);
            }, index * 100);
        });
    }
    
    // Menu mobile
    function initMobileMenu() {
        hamburger.addEventListener('click', function() {
            this.classList.toggle('active');
            navMenu.classList.toggle('active');
        });
        
        // Fermer le menu en cliquant sur un lien
        navLinks.forEach(link => {
            link.addEventListener('click', closeMobileMenu);
        });
        
        // Fermer le menu en cliquant à l'extérieur
        document.addEventListener('click', function(e) {
            if (!navbar.contains(e.target)) {
                closeMobileMenu();
            }
        });
    }
    
    function closeMobileMenu() {
        hamburger.classList.remove('active');
        navMenu.classList.remove('active');
    }
    
    // Effet de scroll sur la navbar
    function initScrollEffects() {
        let lastScrollTop = 0;
        
        window.addEventListener('scroll', function() {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            // Ajouter/supprimer la classe scrolled
            if (scrollTop > 100) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
            
            // Cacher/afficher la navbar selon la direction du scroll
            if (scrollTop > lastScrollTop && scrollTop > 200) {
                navbar.style.transform = 'translateY(-100%)';
            } else {
                navbar.style.transform = 'translateY(0)';
            }
            
            lastScrollTop = scrollTop;
        });
    }
    
    // Compteurs animés
    function initCounters() {
        const counters = document.querySelectorAll('.stat-number');
        let hasAnimated = false;
        
        function animateCounters() {
            if (hasAnimated) return;
            
            const statsSection = document.querySelector('.stats-section');
            if (!statsSection) return;
            
            const rect = statsSection.getBoundingClientRect();
            const isVisible = rect.top < window.innerHeight && rect.bottom > 0;
            
            if (isVisible) {
                hasAnimated = true;
                
                counters.forEach(counter => {
                    const target = parseInt(counter.textContent.replace(/[^\d]/g, ''));
                    const suffix = counter.textContent.replace(/[\d]/g, '');
                    let current = 0;
                    const increment = target / 50;
                    const duration = 2000; // 2 secondes
                    const stepTime = duration / 50;
                    
                    const timer = setInterval(() => {
                        current += increment;
                        if (current >= target) {
                            current = target;
                            clearInterval(timer);
                        }
                        counter.textContent = Math.floor(current) + suffix;
                    }, stepTime);
                });
            }
        }
        
        window.addEventListener('scroll', animateCounters);
        animateCounters(); // Vérifier au chargement
    }
    
    // Gestion du formulaire de contact
    function initContactForm() {
        if (!contactForm) return;
        
        contactForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const submitBtn = this.querySelector('.btn-submit');
            const btnText = submitBtn.querySelector('.btn-text');
            const btnLoading = submitBtn.querySelector('.btn-loading');
            
            // Validation du formulaire
            if (!validateForm()) {
                return;
            }
            
            // Afficher l'état de chargement
            submitBtn.classList.add('loading');
            submitBtn.disabled = true;
            
            try {
                // Préparer les données
                const formData = new FormData(this);
                const data = Object.fromEntries(formData.entries());
                
                // Envoyer à Telegram
                await sendToTelegram(data);
                
                // Succès
                showNotification('Message envoyé avec succès ! Nous vous recontacterons rapidement.', 'success');
                this.reset();
                
            } catch (error) {
                console.error('Erreur lors de l\'envoi:', error);
                showNotification('Erreur lors de l\'envoi du message. Veuillez réessayer.', 'error');
            } finally {
                // Réinitialiser le bouton
                submitBtn.classList.remove('loading');
                submitBtn.disabled = false;
            }
        });
    }
    
    function validateForm() {
        const requiredFields = contactForm.querySelectorAll('[required]');
        let isValid = true;
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                field.style.borderColor = '#ef4444';
                isValid = false;
            } else {
                field.style.borderColor = '';
            }
        });
        
        // Vérifier les services sélectionnés
        const services = contactForm.querySelectorAll('input[name="services"]:checked');
        if (services.length === 0) {
            showNotification('Veuillez sélectionner au moins un service.', 'warning');
            isValid = false;
        }
        
        return isValid;
    }
    
    async function sendToTelegram(data) {
        // Préparer le message pour Telegram
        const message = formatTelegramMessage(data);
        
        // URL de l'API Telegram
        const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                chat_id: TELEGRAM_CHAT_ID,
                text: message,
                parse_mode: 'HTML'
            })
        });
        
        if (!response.ok) {
            throw new Error('Erreur lors de l\'envoi à Telegram');
        }
        
        return response.json();
    }
    
    function formatTelegramMessage(data) {
        const services = Array.from(document.querySelectorAll('input[name="services"]:checked'))
            .map(cb => cb.nextElementSibling.textContent.trim())
            .join(', ');
        
        return `
🆕 <b>Nouveau message de contact</b>

👤 <b>Client:</b> ${data.firstName} ${data.lastName}
📧 <b>Email:</b> ${data.email}
📞 <b>Téléphone:</b> ${data.phone || 'Non renseigné'}
🏢 <b>Entreprise:</b> ${data.company || 'Non renseigné'}
🌐 <b>Site web:</b> ${data.website || 'Non renseigné'}

📋 <b>Type de client:</b> ${data.clientType}
💰 <b>Budget:</b> ${data.budget || 'Non renseigné'}
⏰ <b>Délai:</b> ${data.timeline || 'Non renseigné'}

🎯 <b>Services d'intérêt:</b>
${services}

💬 <b>Message:</b>
${data.message}

📧 <b>Newsletter:</b> ${data.newsletter ? 'Oui' : 'Non'}
        `.trim();
    }
    
    // Système de notifications
    function showNotification(message, type = 'info') {
        // Supprimer les notifications existantes
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(notification => notification.remove());
        
        // Créer la notification
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas fa-${getNotificationIcon(type)}"></i>
                <span>${message}</span>
                <button class="notification-close">&times;</button>
            </div>
        `;
        
        // Ajouter au DOM
        document.body.appendChild(notification);
        
        // Animation d'entrée
        setTimeout(() => {
            notification.classList.add('show');
        }, 100);
        
        // Fermer automatiquement après 5 secondes
        setTimeout(() => {
            closeNotification(notification);
        }, 5000);
        
        // Fermer au clic
        notification.querySelector('.notification-close').addEventListener('click', () => {
            closeNotification(notification);
        });
    }
    
    function closeNotification(notification) {
        notification.classList.remove('show');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }
    
    function getNotificationIcon(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
    
    // Gestion du thème
    function initThemeToggle() {
        // Charger le thème sauvegardé
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            body.classList.add(savedTheme);
            updateThemeIcon(savedTheme);
        }
        
        themeToggle.addEventListener('click', function() {
            body.classList.toggle('dark-theme');
            const isDark = body.classList.contains('dark-theme');
            
            // Sauvegarder le thème
            localStorage.setItem('theme', isDark ? 'dark-theme' : '');
            
            // Mettre à jour l'icône
            updateThemeIcon(isDark ? 'dark-theme' : '');
        });
    }
    
    function updateThemeIcon(theme) {
        const icon = themeToggle.querySelector('i');
        if (theme === 'dark-theme') {
            icon.className = 'fas fa-sun';
        } else {
            icon.className = 'fas fa-moon';
        }
    }
    
    // Intersection Observer pour les animations
    function initIntersectionObserver() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                }
            });
        }, observerOptions);
        
        // Observer les éléments à animer
        const elementsToAnimate = document.querySelectorAll('.service-card, .portfolio-item, .contact-item');
        elementsToAnimate.forEach(element => {
            observer.observe(element);
        });
    }
    
    // Gestion des erreurs globales
    function initErrorHandling() {
        window.addEventListener('error', function(e) {
            console.error('Erreur JavaScript:', e.error);
        });
        
        window.addEventListener('unhandledrejection', function(e) {
            console.error('Promesse rejetée:', e.reason);
        });
    }
    
    // Initialisation
    function init() {
        initSPANavigation();
        initMobileMenu();
        initScrollEffects();
        initCounters();
        initContactForm();
        initThemeToggle();
        initIntersectionObserver();
        initErrorHandling();
        
        // Afficher la première section
        showSection('accueil');
        
        console.log('NEXA RISE MARKETING - Site initialisé avec succès');
    }
    
    // Démarrer l'application
    init();
});

// Styles CSS pour les notifications (ajoutés dynamiquement)
const notificationStyles = `
<style>
.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
    border-left: 4px solid #3b82f6;
    z-index: 10000;
    max-width: 400px;
    transform: translateX(100%);
    transition: transform 0.3s ease;
}

.notification.show {
    transform: translateX(0);
}

.notification-success {
    border-left-color: #10b981;
}

.notification-error {
    border-left-color: #ef4444;
}

.notification-warning {
    border-left-color: #f59e0b;
}

.notification-content {
    padding: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.notification-content i {
    font-size: 20px;
}

.notification-success i {
    color: #10b981;
}

.notification-error i {
    color: #ef4444;
}

.notification-warning i {
    color: #f59e0b;
}

.notification-info i {
    color: #3b82f6;
}

.notification-content span {
    flex: 1;
    font-weight: 500;
    color: #374151;
}

.notification-close {
    background: none;
    border: none;
    font-size: 20px;
    color: #9ca3af;
    cursor: pointer;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.notification-close:hover {
    color: #374151;
}

.navbar.scrolled {
    background: rgba(255, 255, 255, 0.98);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.animate-in {
    animation: fadeInUp 0.6s ease-out forwards;
}

@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
</style>
`;

// Ajouter les styles au document
document.head.insertAdjacentHTML('beforeend', notificationStyles);
