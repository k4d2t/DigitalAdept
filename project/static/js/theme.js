// --- L'heure ---
document.addEventListener('DOMContentLoaded', () => {
    const gmtTimeElement = document.getElementById('gmt-time');
    if (gmtTimeElement) {
        function updateTimeInGMT() {
            const now = new Date();
            const gmtHours = now.getUTCHours().toString().padStart(2, '0');
            const gmtMinutes = now.getUTCMinutes().toString().padStart(2, '0');
            const gmtSeconds = now.getUTCSeconds().toString().padStart(2, '0');
            gmtTimeElement.textContent = `UTC: ${gmtHours}:${gmtMinutes}:${gmtSeconds}`;
        }
        setInterval(updateTimeInGMT, 1000);
        updateTimeInGMT();
    }
});

// --- Menu ---
document.addEventListener('DOMContentLoaded', () => {
    const burger = document.getElementById('burger');
    const mobileMenu = document.getElementById('mobile-menu');
    const closeMobileMenu = document.getElementById('close-mobile-menu');

    if (burger && mobileMenu) {
        burger.addEventListener('click', () => {
            burger.classList.add('active');
            mobileMenu.classList.add('show');
        });
    }

//Burger
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && mobileMenu && mobileMenu.classList.contains('show')) {
            burger.classList.remove('active');
            mobileMenu.classList.remove('show');
        }
    });

    if (closeMobileMenu) {
        closeMobileMenu.addEventListener('click', () => {
            burger.classList.remove('active');
            mobileMenu.classList.remove('show');
        });
    }

    if (mobileMenu && burger) {
        mobileMenu.addEventListener('click', e => {
            if (e.target === mobileMenu) {
                burger.classList.remove('active');
                mobileMenu.classList.remove('show');
            }
        });
    }

});


document.addEventListener('DOMContentLoaded', function() {
    const cartBubble = document.getElementById('cart-bubble');

    cartBubble.addEventListener('click', function(e) {
        // Fonction utilitaire pour détecter la page produit
        function isOnProductPage() {
            // Vérifie si l'URL correspond à une page produit spécifique
            const path = window.location.pathname;

            return (
                path.startsWith('/product/') || // Exemple : /product/{slug}
                path.startsWith('/produit/')    // Exemple : /produit/{slug}
            );
        }

        // Si l'utilisateur n'est pas sur la page produit
        if (!isOnProductPage()) {
            e.preventDefault();
            const cart = JSON.parse(localStorage.getItem('cart')) || [];
            if (cart.length > 0) {
                const lastProduct = cart[cart.length - 1];
                console.log("Last product in cart:", lastProduct); // Debugging output

                if (lastProduct && lastProduct.slug) {
                    // SPA : adapte cette ligne selon ton routeur si besoin
                    window.location.href = `/produit/${lastProduct.slug}`;
                } else {
                    console.error("The last product in the cart does not have a valid 'slug' field.");
                    showNotification('Impossible de rediriger vers le dernier produit.', 'error');
                }
            } else {
                showNotification('Votre panier est vide.', 'error');
            }
        } else {
            // Si l'utilisateur est sur la page produit
            const cartBar = document.getElementById('cart-bar');
            if (cartBar) {
                cartBar.classList.toggle('visible'); // Ouvre/ferme le panier

                // Gestion du focus sur le bouton cartBubble
                if (cartBar.classList.contains('visible')) {
                    cartBubble.focus(); // Garde le focus sur le bouton lorsque le panier est ouvert
                } else {
                    cartBubble.blur(); // Retire le focus lorsque le panier est fermé
                }
            }
        }
    });
});

// --- Initialisation des produits et tri ---
window.initProductSearchSort = function () {
    const searchInput = document.getElementById('searchInput');
    const sortSelect = document.getElementById('sortSelect');
    const productsList = document.getElementById('productsList');
    if (!productsList) return;

    const allProducts = Array.from(productsList.querySelectorAll('.product-card'));
    const originalOrder = allProducts.slice();

    function filterAndSort() {
        const search = searchInput?.value.trim().toLowerCase() || "";
        const sort = sortSelect?.value || "";

        let filtered = originalOrder.filter(card =>
        card.textContent.toLowerCase().includes(search)
        );

        if (sort === 'date-desc') {
            // Ordre par défaut (plus récent en haut)
        } else if (sort === 'date-asc') {
            filtered = filtered.slice().reverse();
        } else if (sort === 'promo-first') {
            filtered.sort((a, b) => {
                const promoA = a.classList.contains('has-promo') || a.querySelector('.badge-promo') ? 1 : 0;
                const promoB = b.classList.contains('has-promo') || b.querySelector('.badge-promo') ? 1 : 0;
                return promoB - promoA;
            });
        } else if (sort === 'price-asc' || sort === 'price-desc') {
            filtered.sort((a, b) => {
                const priceA = parseFloat(a.querySelector('.product-price')?.textContent.replace(/[^\d.,]/g, '').replace(',', '.') || '0');
                const priceB = parseFloat(b.querySelector('.product-price')?.textContent.replace(/[^\d.,]/g, '').replace(',', '.') || '0');
                return sort === 'price-asc' ? priceA - priceB : priceB - priceA;
            });
        }

        productsList.innerHTML = '';
        filtered.forEach(card => productsList.appendChild(card));
    }

    searchInput?.addEventListener('input', filterAndSort);
    sortSelect?.addEventListener('change', filterAndSort);
    filterAndSort();
};

// --- Initialisation du filtre par catégories ---
window.initCategoryFilter = function () {

    const productsList = document.getElementById('productsList');
    const categoryFilter = document.getElementById('categoryFilter');

    if (!productsList || !categoryFilter) return;

    categoryFilter.innerHTML = '<option value="">Catégories</option>';

    const allProducts = Array.from(productsList.querySelectorAll('.product-card'));
    const categories = Array.from(new Set(
        allProducts
        .map(card => card.dataset.category)
        .filter(category => category && category.trim())
    ));

    if (categories.length === 0) {
        const noCategoryOption = document.createElement('option');
        noCategoryOption.textContent = 'Aucune catégorie disponible';
        noCategoryOption.disabled = true;
        categoryFilter.appendChild(noCategoryOption);
    } else {
        categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            categoryFilter.appendChild(option);
        });
    }

    categoryFilter.addEventListener('change', () => {
        const selectedCategory = categoryFilter.value;
        allProducts.forEach(card => {
            card.style.display = selectedCategory === "" || card.dataset.category === selectedCategory ? "" : "none";
        });
    });
};

// --- Initialisation de la page produit et du panier digital ---
window.initProductPage = function () {
    // --- Galerie produit ---
    const gallery = document.querySelector(".product-gallery");
    if (gallery) {
        const mainImages = gallery.querySelectorAll(".gallery-img");
        const thumbnails = gallery.querySelectorAll(".gallery-thumb");
        const prevArrow = gallery.querySelector(".gallery-arrow.left");
        const nextArrow = gallery.querySelector(".gallery-arrow.right");
        let currentIndex = 0;
        let autoScrollInterval;
        let isZooming = false;

        function updateGallery(index) {
            mainImages.forEach((img, i) => img.classList.toggle("active", i === index));
            thumbnails.forEach((thumb, i) => thumb.classList.toggle("active", i === index));
            currentIndex = index;
        }

        function startAutoScroll() {
            if (autoScrollInterval) clearInterval(autoScrollInterval);
            if (mainImages.length > 1 && !isZooming) {
                autoScrollInterval = setInterval(() => {
                    updateGallery((currentIndex + 1) % mainImages.length);
                }, 3000);
            }
        }

        function stopAutoScroll() {
            if (autoScrollInterval) clearInterval(autoScrollInterval);
        }

        thumbnails.forEach((thumb, index) => {
            thumb.addEventListener("click", () => {
                stopAutoScroll();
                updateGallery(index);
                startAutoScroll();
            });
        });

        if (prevArrow) {
            prevArrow.addEventListener("click", () => {
                stopAutoScroll();
                updateGallery((currentIndex - 1 + mainImages.length) % mainImages.length);
                startAutoScroll();
            });
        }

        if (nextArrow) {
            nextArrow.addEventListener("click", () => {
                stopAutoScroll();
                updateGallery((currentIndex + 1) % mainImages.length);
                startAutoScroll();
            });
        }

        startAutoScroll();

        // --- Gestion du zoom au survol ---
        mainImages.forEach((img) => {
            img.addEventListener("mousemove", (e) => {
                const rect = img.getBoundingClientRect();
                const x = ((e.clientX - rect.left) / rect.width) * 102;
                const y = ((e.clientY - rect.top) / rect.height) * 102;
                img.style.transformOrigin = `${x}% ${y}%`;
                img.classList.add("zoomed");
                isZooming = true; // Indique qu'un zoom est en cours
                stopAutoScroll(); // Arrête l'auto-scroll pendant le zoom
            });

            img.addEventListener("mouseleave", () => {
                img.classList.remove("zoomed");
                img.style.transformOrigin = "center center";
                isZooming = false; // Indique que le zoom est terminé
                startAutoScroll(); // Redémarre l'auto-scroll après le zoom
            });
        });
    }

    // --- Gestion des étoiles dynamiques ---
    document.querySelectorAll(".stars").forEach(starElement => {
        const stars = parseFloat(starElement.getAttribute("data-stars") || 0);
        starElement.innerHTML = "";
        for (let i = 0; i < Math.floor(stars); i++) {
            const star = document.createElement("span");
            star.textContent = "★";
            star.style.color = "#FFD600";
            starElement.appendChild(star);
        }
        for (let i = Math.floor(stars); i < 5; i++) {
            const emptyStar = document.createElement("span");
            emptyStar.textContent = "☆";
            emptyStar.style.color = "#bdbdbd";
            starElement.appendChild(emptyStar);
        }
    });


    //SHARE BUTTON//

    function initShareButton() {
        const shareBtn = document.getElementById('share-btn');
        if (!shareBtn) return;

        // Overlay
        let overlay = document.getElementById('share-modal-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'share-modal-overlay';
            document.body.appendChild(overlay);
        }

        // Modale
        let modal = document.getElementById('share-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'share-modal';
            document.body.appendChild(modal);
        }

        // SVG Icônes
        const iconApp = `<svg width="22" height="22" fill="none" stroke="#222" stroke-width="1.7"><path d="M14.5 8V3.5a1.5 1.5 0 0 0-1.5-1.5h-7A1.5 1.5 0 0 0 4.5 3.5v13A1.5 1.5 0 0 0 6 18h7a1.5 1.5 0 0 0 1.5-1.5V12"/><polyline points="17 7 12 2 7 7"/><line x1="12" y1="2" x2="12" y2="15"/></svg>`;
        const iconCopy = `<svg width="18" height="18" fill="none" stroke="#333" stroke-width="1.5"><rect x="3" y="3" width="12" height="12" rx="2"/><path d="M6 3V2a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1"/></svg>`;
        const iconWhatsapp = `<svg width="22" height="22" viewBox="0 0 256 256"><g fill="none"><circle cx="128" cy="128" r="128" fill="#25D366"/><path fill="#fff" d="M128 48c44.2 0 80 35.8 80 80 0 18.5-6.8 35.4-18.1 48.7l8.2 38.6-39.4-8.2C161.3 211.1 145.2 216 128 216c-44.2 0-80-35.8-80-80s35.8-80 80-80zm36.6 109.2c-1.6-.8-9.3-4.6-10.8-5.2-1.4-.6-2.4-.8-3.3.8-1 1.6-3.8 5.2-4.7 6.2-.9 1-1.7 1.2-3.3.4-1.6-.8-6.6-2.4-12.5-7.5-4.6-4.1-7.7-9.1-8.6-10.7-.9-1.6-.1-2.4.7-3.2.7-.7 1.6-1.8 2.3-2.7.8-.9 1-1.6 1.6-2.7.6-1.1.3-2-.1-2.8-.5-.8-3.3-8-4.5-11-1.2-2.9-2.4-2.5-3.3-2.5-.8 0-1.9-.1-2.9-.1-1 0-2.7.4-4.1 1.8-1.4 1.4-5.4 5.3-5.4 12.9 0 7.7 5.5 15.1 6.2 16.1.8 1.1 10.9 16.6 26.3 22.6 15.4 6 15.4 4 18.2 3.7 2.8-.3 9.3-3.8 10.6-7.5 1.3-3.7 1.3-6.8.9-7.5z"/></g></svg>`;
        const iconFacebook = `<svg width="22" height="22" viewBox="0 0 32 32"><circle cx="16" cy="16" r="16" fill="#1877F3"/><path d="M21.5 16h-3v9h-4v-9h-2v-4h2v-1.5C14.5 8.6 15.6 7 18 7h2.5v4H19c-.6 0-1 .4-1 1V12h4l-.5 4z" fill="#fff"/></svg>`;
        const iconTwitter = `<svg width="22" height="22" viewBox="0 0 32 32"><circle cx="16" cy="16" r="16" fill="#000"/><path fill="#fff" d="M25.3 12.1c.01.15.01.3.01.46 0 4.7-3.57 10.1-10.1 10.1-2 0-3.88-.59-5.46-1.6.28.03.56.05.85.05 1.65 0 3.17-.56 4.38-1.51a3.56 3.56 0 0 1-3.33-2.47c.22.04.44.07.67.07.32 0 .64-.04.94-.12a3.55 3.55 0 0 1-2.85-3.48v-.04c.48.27 1.04.44 1.63.46a3.54 3.54 0 0 1-1.58-2.95c0-.65.18-1.25.49-1.77a10.1 10.1 0 0 0 7.34 3.72c-.06-.26-.1-.54-.1-.82a3.55 3.55 0 0 1 6.14-2.43 7.06 7.06 0 0 0 2.25-.86 3.56 3.56 0 0 1-1.56 1.97 7.1 7.1 0 0 0 2.04-.56 7.65 7.65 0 0 1-1.78 1.85z"/></svg>`;
        const iconMail = `<svg width="22" height="22" viewBox="0 0 32 32"><circle cx="16" cy="16" r="16" fill="#e4405f"/><path fill="#fff" d="M23.61 10.22H8.39a1.17 1.17 0 0 0-1.17 1.17v9.22a1.17 1.17 0 0 0 1.17 1.17h15.22a1.17 1.17 0 0 0 1.17-1.17v-9.22a1.17 1.17 0 0 0-1.17-1.17zm-.41 2.34l-6.57 4.11a.5.5 0 0 1-.54 0l-6.57-4.11v-.4l6.84 4.29a1.5 1.5 0 0 0 1.65 0l6.84-4.29z"/></svg>`;

        function openModal() {
            const url = window.location.href;
            modal.innerHTML = `
            <button class="close-share-modal" aria-label="Fermer">&times;</button>
            <h3>Partager ce lien</h3>
            <div class="share-actions">
            ${navigator.share ? `
                <button class="share-btn" id="share-native">${iconApp}Via une appli</button>
                ` : ""}
                <button class="share-btn" id="share-copy">${iconCopy}Copier le lien</button>
                <a class="share-btn whatsapp" href="https://wa.me/?text=${encodeURIComponent(url)}" target="_blank" rel="noopener">${iconWhatsapp}WhatsApp</a>
                <a class="share-btn facebook" href="https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}" target="_blank" rel="noopener">${iconFacebook}Facebook</a>
                <a class="share-btn twitter" href="https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}" target="_blank" rel="noopener">${iconTwitter}X/Twitter</a>
                <a class="share-btn email" href="mailto:?body=${encodeURIComponent(url)}" target="_blank" rel="noopener">${iconMail}E-mail</a>
                </div>
                <div class="share-urlbox">
                <span class="share-url" id="share-url">${url}</span>
                <button class="share-copy-mini" id="share-copy-mini" title="Copier">${iconCopy}</button>
                <span class="share-feedback">Copié !</span>
                </div>
                `;
                overlay.style.display = 'block';
                modal.style.display = 'block';

                // Close modale
                modal.querySelector('.close-share-modal').onclick = closeModal;
                overlay.onclick = function(e) {
                    if (e.target === overlay) closeModal();
                };

                    // Web Share API
                    const nativeBtn = document.getElementById('share-native');
                    if (nativeBtn && navigator.share) {
                        nativeBtn.onclick = async () => {
                            try {
                                await navigator.share({url, title: document.title, text: document.title});
                                closeModal();
                            } catch(e) { /* Annulé ou erreur */ }
                        };
                    }

                    // Copier (gros bouton)
                    document.getElementById('share-copy').onclick = () => doCopy(url, modal);
                    // Copier (mini bouton)
                    document.getElementById('share-copy-mini').onclick = () => doCopy(url, modal);
        }

        function closeModal() {
            modal.style.display = 'none';
            overlay.style.display = 'none';
        }

        function doCopy(url, context) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(url)
                .then(() => showCopyFeedback(context))
                .catch(() => fallbackCopy(url, context));
            } else {
                fallbackCopy(url, context);
            }
        }
        function fallbackCopy(text, context) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                showCopyFeedback(context);
            } catch (err) {
                showNotification('Impossible de copier automatiquement. Copiez à la main : ' + text, 'error');
            }
            document.body.removeChild(textarea);
        }
        function showCopyFeedback(context) {
            const feedback = context.querySelector('.share-feedback');
            if (feedback) {
                feedback.style.display = 'inline';
                setTimeout(() => { feedback.style.display = 'none'; }, 1200);
            }
        }

        shareBtn.addEventListener('click', openModal);
    }
        initShareButton();




        // --- PANIER DIGITAL GLOBAL ---
        function initCartDigital() {
            const cartBar = document.getElementById('cart-bar');
            const cartItemsContainer = document.getElementById('cart-items');
            const cartTotalElement = document.getElementById('cart-total');
            const addToCartButtons = document.querySelectorAll('.add-to-cart');
            const closeCartButton = document.getElementById('close-cart');
            const cartBubble = document.getElementById('cart-bubble');
            const cartBadge = document.querySelector('.cart-badge');
            const buyFromCartButton = document.getElementById('buy-from-cart');
            const buyDirectlyButtons = document.querySelectorAll('.btn-buy');

            let cart = JSON.parse(localStorage.getItem('cart')) || [];

            function updateCartBadge(animated) {
                if (!cartBadge) return;
                const itemCount = cart.length;
                cartBadge.textContent = itemCount;
                cartBadge.style.display = itemCount > 0 ? 'inline-block' : 'none';
                if (animated) {
                    cartBadge.classList.remove('pop');
                    // Force reflow to restart animation
                    void cartBadge.offsetWidth;
                    cartBadge.classList.add('pop');
                }
            }

            function saveCart() {
                localStorage.setItem('cart', JSON.stringify(cart));
                updateCartBadge(false);
            }

            function calculateTotal() {
                return cart.reduce((total, item) => total + item.price, 0);
            }

            function renderCart() {
                if (!cartItemsContainer || !cartTotalElement) return;
                cartItemsContainer.innerHTML = '';
                if (cart.length === 0) {
                    cartItemsContainer.innerHTML = '<p>Votre panier est vide.</p>';
                } else {
                    cart.forEach((item, index) => {
                        const itemElement = document.createElement('div');
                        itemElement.className = 'cart-item';
                        itemElement.innerHTML = `
                        <span>${item.name}</span>&ensp;
                        <span>${item.price} XOF</span>
                        <button class="remove-item" data-index="${index}">⛌</button>
                        `;
                        cartItemsContainer.appendChild(itemElement);
                    });
                }
                cartTotalElement.textContent = calculateTotal();

                cartItemsContainer.querySelectorAll('.remove-item').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const index = parseInt(e.target.dataset.index);
                        cart.splice(index, 1);
                        saveCart();
                        renderCart();
                        updateAddToCartButtons();
                        updateCartBadge(true);
                    });
                });
            }

            function updateAddToCartButtons() {
                addToCartButtons.forEach(button => {
                    const productId = button.getAttribute('data-id');
                    const found = cart.find(item => item.id === productId);
                    button.classList.remove('added', 'already-added');
                    button.disabled = false;
                    if (found) {
                        button.textContent = "Déjà ajouté";
                        button.classList.add('already-added');
                        button.disabled = true;
                    } else {
                        button.textContent = "Ajouter au panier";
                    }
                });
            }

            function slugify(text) {
                // Supprime les accents et transforme en ASCII
                text = text.normalize('NFKD').replace(/[\u0300-\u036f]/g, '');

                // Supprime les caractères spéciaux et met en minuscule
                text = text.replace(/[^\w\s-]/g, '').trim().toLowerCase();

                // Remplace les espaces et tirets multiples par un seul tiret
                return text.replace(/[\s]+/g, '-');
            }

            addToCartButtons.forEach(button => {
                button.addEventListener('click', () => {
                    const productId = button.getAttribute('data-id');
                    const productName = button.getAttribute('data-name');
                    const productPrice = parseFloat(button.getAttribute('data-price'));
                    const productSlug = slugify(productName);

                    // Verifie si le produit est déjà dans le panier
                    const found = cart.find(item => item.id === productId);
                    if (!found) {
                        cart.push({ id: productId, name: productName, price: productPrice, slug: productSlug });
                        saveCart();
                        renderCart();
                        updateAddToCartButtons();
                        if (cartBar) cartBar.classList.add('visible');
                        // Badge animation
                        updateCartBadge(true);
                        // Bouton feedback visuel
                        button.textContent = "OK !";
                        button.classList.add('added');
                        showNotification(` Ajouté avec succès.`, 'success');
                        setTimeout(() => {
                            button.textContent = "Déjà ajouté";
                            button.classList.remove('added');
                            button.classList.add('already-added');
                            button.disabled = true;
                        }, 700);
                    } else {
                        button.textContent = "Déjà ajouté";
                        button.classList.remove('added');
                        button.classList.add('already-added');
                        button.disabled = true;
                    }
                });
            });


            // Fonction de redirection vers le paiement avec encodage
            function redirectToPayment(amount, productNames) {
                // Combiner les détails dans une chaîne brute
                const rawDetails = `${amount}:${productNames.join(',')}:${Date.now()}`;

                // Encoder les détails (par exemple, via un hash SHA-256 ou base64)
                const encodedKey = btoa(rawDetails); // Encodage Base64 (simple et lisible)

                // Construire l'URL de redirection avec la clé encodée
                const paymentUrl = `https://digitaladept.onrender.com:5000/payment/${encodedKey}`;
                console.log("[Site] Redirection vers :", paymentUrl);

                // Rediriger vers l'URL de paiement
                window.location.href = paymentUrl;
            }

            // --- Gestion des achats directs ("Acheter maintenant") ---
            buyDirectlyButtons.forEach(button => {
                button.addEventListener('click', () => {
                    const productPrice = parseFloat(button.getAttribute('data-price'));
                    const productName = button.getAttribute('data-name');
                    console.log(`[Site] Achat direct - Produit : ${productName}, Montant : ${productPrice}`);
                    redirectToPayment(productPrice, [productName]);
                });
            });

            // --- Gestion des achats depuis le panier ---
            if (buyFromCartButton) {
                buyFromCartButton.addEventListener('click', () => {
                    const total = calculateTotal();
                    const productNames = cart.map(item => item.name);
                    if (total > 0) {
                        console.log(`[Site] Paiement du panier - Produits : ${productNames.join(', ')}, Montant : ${total}`);
                        redirectToPayment(total, productNames);
                    } else {
                        showNotification("Votre panier est vide. Ajoutez des articles pour continuer.", 'error');
                    }
                });
            }

            // Ouvre/ferme le panier avec le bouton close
            if (closeCartButton && cartBar) {
                closeCartButton.addEventListener('click', () => {
                    cartBar.classList.toggle('visible');
                });
            }

            // Animation badge au chargement si panier non vide
            updateCartBadge(false);
            renderCart();
            updateAddToCartButtons();
        }

        // Initialiser le panier sur toutes les pages (SPA-friendly)
        initCartDigital();

    // --- Gestion du bouton "Voir plus" pour les commentaires ---
    const commentSection = document.querySelector('.comments-section');
    if (commentSection) {
        const commentList = commentSection.querySelector('.comment-list');
        const comments = Array.from(commentList.querySelectorAll('.comment'));
        const showMoreButton = document.createElement('button');
        showMoreButton.className = 'btn-show-more';
        showMoreButton.textContent = 'Voir plus';
        let visibleCount = 3;

        function updateCommentsVisibility() {
            comments.forEach((comment, index) => {
                comment.style.display = index < visibleCount ? 'block' : 'none';
            });

            showMoreButton.style.display = visibleCount >= comments.length ? 'none' : 'block';
        }

        showMoreButton.addEventListener('click', () => {
            visibleCount += 3;
            updateCommentsVisibility();
        });

        commentList.insertAdjacentElement('afterend', showMoreButton);
        updateCommentsVisibility();
    }

    // --- Gestion des interactions avec la FAQ ---
    document.querySelectorAll(".faq-item").forEach((faqItem) => {
        const question = faqItem.querySelector(".faq-question");
        question.addEventListener("click", () => {
            faqItem.classList.toggle("closed");
        });
    });

};

// --- Initialisation globale ---
document.addEventListener('DOMContentLoaded', () => {
    window.initProductSearchSort();
    window.initCategoryFilter();
    window.initProductPage();
});
