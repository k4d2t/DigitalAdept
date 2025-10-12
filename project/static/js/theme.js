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
        function isOnProductPage() {
            const path = window.location.pathname;
            return (path.startsWith('/product/') || path.startsWith('/produit/'));
        }

        if (!isOnProductPage()) {
            e.preventDefault();
            const cart = JSON.parse(localStorage.getItem('cart')) || [];
            if (cart.length > 0) {
                const lastProduct = cart[cart.length - 1];
                if (lastProduct && lastProduct.slug) {
                    window.location.href = `/produit/${lastProduct.slug}`;
                } else {
                    showNotification('Impossible de rediriger vers le dernier produit.', 'error');
                }
            } else {
                showNotification('Votre panier est vide.', 'error');
            }
        } else {
            const cartBar = document.getElementById('cart-bar');
            if (cartBar) {
                cartBar.classList.toggle('visible');
                if (cartBar.classList.contains('visible')) cartBubble.focus();
                else cartBubble.blur();
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
                isZooming = true;
                stopAutoScroll();
            });

            img.addEventListener("mouseleave", () => {
                img.classList.remove("zoomed");
                img.style.transformOrigin = "center center";
                isZooming = false;
                startAutoScroll();
            });
        });
    }

    // --- Gestion des étoiles dynamiques ---
    document.querySelectorAll(".stars").forEach(starElement => {
        const stars = parseFloat(starElement.getAttribute("data-stars") || 0);
        starElement.innerHTML = "";
        for (let i = 1; i <= 5; i++) {
            if (stars >= i) {
                starElement.innerHTML += '<span style="color:#FFD600">★</span>';
            } else if (stars >= i - 0.5) {
                starElement.innerHTML += '<span style="color:#FFD600">⯨</span>';
            } else {
                starElement.innerHTML += '<span style="color:#bdbdbd">☆</span>';
            }
        }
    });


    //SHARE BUTTON//
    function initShareButton() {
        const shareBtn = document.getElementById('share-btn');
        if (!shareBtn) return;

        let overlay = document.getElementById('share-modal-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'share-modal-overlay';
            document.body.appendChild(overlay);
        }

        let modal = document.getElementById('share-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'share-modal';
            document.body.appendChild(modal);
        }

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

                modal.querySelector('.close-share-modal').onclick = closeModal;
                overlay.onclick = function(e) {
                    if (e.target === overlay) closeModal();
                };

                const nativeBtn = document.getElementById('share-native');
                if (nativeBtn && navigator.share) {
                    nativeBtn.onclick = async () => {
                        try {
                            await navigator.share({url, title: document.title, text: document.title});
                            closeModal();
                        } catch(e) {}
                    };
                }

                document.getElementById('share-copy').onclick = () => doCopy(url, modal);
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
                void cartBadge.offsetWidth;
                cartBadge.classList.add('pop');
            }
        }

        function saveCart() {
            localStorage.setItem('cart', JSON.stringify(cart));
            updateCartBadge(false);
        }

        function calculateTotal() {
            return cart.reduce((total, item) => {
                return total + (Number(item.price || 0) * Number(item.quantity || 1));
            }, 0);
        }

        // Helper: conversion panier robuste
        async function convertCartNow(maxRetries = 8) {
            try {
                const sel = JSON.parse(localStorage.getItem('da_locale') || '{}');
                const targetCur = (sel.currency || 'XOF').toUpperCase();

                if (window.__da_debugLocale && typeof window.__da_debugLocale.convert === 'function') {
                    await window.__da_debugLocale.convert(targetCur);
                    return;
                }

                // Fallback local si le pont global n'est pas encore prêt
                let rates = null;
                try {
                    const cached = localStorage.getItem('da_fx_rates');
                    if (cached) {
                        const obj = JSON.parse(cached);
                        if (obj && obj.rates) rates = obj.rates;
                    }
                } catch {}
                if (!rates) {
                    const r = await fetch('/api/fx-rates', { cache: 'no-store', credentials: 'same-origin' });
                    const j = await r.json();
                    if (j && j.status === 'success' && j.rates) {
                        rates = j.rates;
                        try { localStorage.setItem('da_fx_rates', JSON.stringify({ rates, ts: Date.now() })); } catch {}
                    }
                }
                if (!rates) {
                    if (maxRetries > 0) {
                        return new Promise(res => setTimeout(() => res(convertCartNow(maxRetries - 1)), 60));
                    }
                    return;
                }

                const SYMBOL = { XOF:'XOF', USD:'$', EUR:'€', GBP:'£', AED:'د.إ', RUB:'₽', CNY:'¥', JPY:'¥' };
                const convertAmountViaXOFLocal = (amount, fromCur, toCur) => {
                    if (!isFinite(amount)) return amount;
                    if (fromCur === toCur) return amount;
                    try {
                        const rFrom = fromCur === 'XOF' ? 1 : rates[fromCur];
                        const inXof = rFrom ? (fromCur === 'XOF' ? amount : amount / rFrom) : amount;
                        const rTo = toCur === 'XOF' ? 1 : rates[toCur];
                        return rTo ? (toCur === 'XOF' ? inXof : inXof * rTo) : inXof;
                    } catch { return amount; }
                };
                const formatAmountLocal = (amount, currency) => `${Number(amount).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} ${SYMBOL[currency] || currency}`;

                const nodes = document.querySelectorAll('#cart-bar [data-price]');
                nodes.forEach(el => {
                    const base = parseFloat(el.getAttribute('data-price'));
                    const fromCur = (el.getAttribute('data-currency') || 'XOF').toUpperCase();
                    if (!isFinite(base)) return;
                    const conv = convertAmountViaXOFLocal(base, fromCur, targetCur);
                    el.textContent = formatAmountLocal(conv, targetCur);
                    el.setAttribute('data-currency', targetCur);
                });
            } catch (_) {}
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
                    const baseCur = 'XOF';
                    const basePrice = Number(item.price) || 0;

                    itemElement.innerHTML = `
                        <span>${item.name}</span>&ensp;
                        <span class="cart-price" data-price="${basePrice}" data-currency="${baseCur}">
                            ${basePrice} ${baseCur}
                        </span>
                        <button class="remove-item" data-index="${index}">⛌</button>
                    `;
                    cartItemsContainer.appendChild(itemElement);

                    const priceEl = itemElement.querySelector('.cart-price');
                    if (priceEl) {
                        priceEl.dataset.basePrice = String(basePrice);
                        priceEl.dataset.baseCurrency = baseCur;
                    }
                });
            }

            const totalBase = calculateTotal();
            cartTotalElement.setAttribute('data-price', String(totalBase));
            cartTotalElement.setAttribute('data-currency', 'XOF');
            cartTotalElement.textContent = `${totalBase} XOF`;
            cartTotalElement.dataset.basePrice = String(totalBase);
            cartTotalElement.dataset.baseCurrency = 'XOF';

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

            // Conversion panier immédiate (double passe)
            convertCartNow();
            requestAnimationFrame(() => convertCartNow());
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
            text = text.normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
            text = text.replace(/[^\w\s-]/g, '').trim().toLowerCase();
            return text.replace(/[\s]+/g, '-');
        }

        addToCartButtons.forEach(button => {
            button.addEventListener('click', async () => {
                const productId = button.getAttribute('data-id');
                const productName = button.getAttribute('data-name');
                const productPrice = parseFloat(button.getAttribute('data-price'));
                const productSlug = slugify(productName);

                const found = cart.find(item => item.id === productId);
                if (!found) {
                    cart.push({ id: productId, name: productName, price: productPrice, slug: productSlug });
                    saveCart();
                    renderCart();              // rend + convertCartNow()
                    updateAddToCartButtons();
                    if (cartBar) cartBar.classList.add('visible');
                    updateCartBadge(true);

                    // Conversion supplémentaire immédiate pour garantir l'affichage en devise user
                    await convertCartNow();
                    requestAnimationFrame(() => convertCartNow());

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
        
        // Remplacer complètement la fonction PaymentInfoModal actuelle par celle-ci:
        
        function PaymentInfoModal(onSubmit, onCancel) {
            const previousActive = document.activeElement;
            let lastProfile = {};
            try { lastProfile = JSON.parse(localStorage.getItem('da_checkout_profile') || '{}'); } catch {}
        
            // IDs uniques pour éviter les conflits
            const overlayId = 'payment-modal-overlay-' + Date.now();
            const modalId = 'payment-modal-' + Date.now();
            
            // Créer l'overlay 
            const overlay = document.createElement('div');
            overlay.id = overlayId;
            overlay.className = 'customModal-overlay';
            
            // TECHNIQUE FONCTIONNELLE: forcer les styles critiques avec !important
            overlay.style.setProperty('position', 'fixed', 'important');
            overlay.style.setProperty('inset', '0', 'important');
            overlay.style.setProperty('display', 'flex', 'important');
            overlay.style.setProperty('align-items', 'center', 'important');
            overlay.style.setProperty('justify-content', 'center', 'important');
            overlay.style.setProperty('z-index', '9999', 'important');
            
            // RESTAURATION STYLE VISUEL
            overlay.style.background = 'rgba(0,0,0,.5)';
            
            // Créer la modale
            const modal = document.createElement('div');
            modal.id = modalId;
            modal.className = 'customModal';
            modal.setAttribute('role', 'dialog');
            modal.setAttribute('aria-modal', 'true');
            
            // TECHNIQUE FONCTIONNELLE: forcer display/position critiques
            modal.style.setProperty('display', 'block', 'important');
            modal.style.setProperty('position', 'relative', 'important');
            modal.style.setProperty('z-index', '10000', 'important');
            
            // RESTAURATION STYLE VISUEL
            modal.style.background = '#111';
            modal.style.color = '#fff';
            modal.style.borderRadius = '12px';
            modal.style.width = 'min(96vw, 520px)';
            modal.style.maxHeight = '90vh';
            modal.style.overflow = 'auto';
            modal.style.boxShadow = '0 10px 40px rgba(0,0,0,.4)';
            modal.style.padding = '18px';
            modal.style.outline = 'none';
            
            // TECHNIQUE FONCTIONNELLE: règle CSS globale uniquement pour l'affichage critique
            const styleElement = document.createElement('style');
            styleElement.textContent = `
                #${overlayId} { display: flex !important; }
                #${modalId} { display: block !important; }
            `;
            document.head.appendChild(styleElement);
            
            // Verrouiller le scroll
            document.documentElement.style.overflow = 'hidden';
            
            // CONTENU: style visuel d'origine et formulaire
            modal.innerHTML = `
              <form id="payment-form-${modalId}" autocomplete="on" novalidate>
                <h3 id="modal-title" style="margin:.2em 0 0.6em 0;">Finaliser la commande</h3>
                <p id="modal-desc" style="opacity:.8;margin-top:0;margin-bottom:1em;">
                  Renseignez vos informations pour recevoir vos produits.
                </p>
        
                <div class="form-field" style="margin-bottom:10px;">
                  <label for="payment-nom-client-${modalId}">Nom complet</label>
                  <input
                    type="text"
                    id="payment-nom-client-${modalId}"
                    name="name"
                    placeholder="Votre nom complet"
                    required
                    autocomplete="name"
                    autocapitalize="words"
                    spellcheck="false"
                    />
                </div>
        
                <div class="form-field" style="margin-bottom:10px;">
                  <label for="payment-email-${modalId}">Adresse e-mail</label>
                  <input
                    type="email"
                    id="payment-email-${modalId}"
                    name="email"
                    placeholder="Pour recevoir vos produits"
                    required
                    autocomplete="email"
                    inputmode="email"
                    />
                </div>
        
                <div class="form-field" style="margin-bottom:4px;">
                  <label for="payment-whatsapp-${modalId}">Numéro WhatsApp</label>
                  <input
                    type="tel"
                    id="payment-whatsapp-${modalId}"
                    name="tel"
                    placeholder="+2250700000000"
                    autocomplete="tel"
                    inputmode="tel"
                    />
                  <small id="whats-hint" style="opacity:.7;">Format international recommandé (+225…)</small>
                </div>
        
                <div id="payment-error-${modalId}" aria-live="assertive" style="min-height:1.2em;color:#ff8a80;margin:.4em 0;"></div>
        
                <div class="customModal-buttons" style="display:flex; gap:10px; margin-top:12px;">
                  <button type="submit" class="customModal-yes" id="payment-submit-${modalId}">Valider et Payer</button>
                  <button type="button" class="customModal-no" id="payment-cancel-${modalId}">Annuler</button>
                </div>
              </form>
            `;
            
            overlay.appendChild(modal);
            document.body.appendChild(overlay);
            
            const formEl = document.getElementById(`payment-form-${modalId}`);
            const nomEl = document.getElementById(`payment-nom-client-${modalId}`);
            const emailEl = document.getElementById(`payment-email-${modalId}`);
            const telEl = document.getElementById(`payment-whatsapp-${modalId}`);
            const errEl = document.getElementById(`payment-error-${modalId}`);
            const btnSubmit = document.getElementById(`payment-submit-${modalId}`);
            const btnCancel = document.getElementById(`payment-cancel-${modalId}`);
            
            if (lastProfile && typeof lastProfile === 'object') {
                if (lastProfile.name) nomEl.value = lastProfile.name;
                if (lastProfile.email) emailEl.value = lastProfile.email;
                if (lastProfile.whatsapp) telEl.value = lastProfile.whatsapp;
            }
            
            setTimeout(() => { nomEl.focus(); }, 50);
            
            function close() {
                styleElement.remove();
                document.documentElement.style.overflow = ''; 
                document.removeEventListener('keydown', onKeydown);
                overlay.remove();
                
                if (previousActive && typeof previousActive.focus === 'function') {
                    previousActive.focus();
                }
            }
            
            function onKeydown(e) {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    close();
                    if (typeof onCancel === 'function') onCancel();
                }
            }
            document.addEventListener('keydown', onKeydown);
            
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    close();
                    if (typeof onCancel === 'function') onCancel();
                }
            });
            
            formEl.addEventListener('submit', (evt) => {
                evt.preventDefault();
                errEl.textContent = '';
                
                const nom = nomEl.value.trim();
                const email = emailEl.value.trim();
                const whatsapp = telEl.value.trim();
                
                if (!nom || !email) {
                    errEl.textContent = "Le nom et l'e-mail sont requis.";
                    (nom ? emailEl : nomEl).focus();
                    return;
                }
                
                if (!/^\S+@\S+\.\S+$/.test(email)) {
                    errEl.textContent = "Veuillez entrer une adresse e-mail valide.";
                    emailEl.focus();
                    return;
                }
                
                try {
                    localStorage.setItem('da_checkout_profile', JSON.stringify({ name: nom, email, whatsapp }));
                } catch {}
                
                close();
                onSubmit({ nom_client: nom, email, whatsapp });
            });
            
            btnCancel.addEventListener('click', () => {
                close();
                if (typeof onCancel === 'function') onCancel();
            });
        }

        
        function getArticleObject(cart) {
            const article = {};
            cart.forEach(item => {
                article[item.name] = parseFloat(item.price) * (item.quantity || 1);
            });
            return [article];
        }

        function getTotalPrice(cart) {
            return cart.reduce((acc, item) => acc + (Number(item.price || 0) * Number(item.quantity || 1)), 0);
        }

        function redirectToPayment(amount, cart) {
          const selectedCurrency = (() => {
            try { const obj = JSON.parse(localStorage.getItem('da_locale') || '{}'); return (obj.currency || 'XOF').toUpperCase(); }
            catch { return 'XOF'; }
          })();
          const totalPriceXOF = cart.reduce((acc, item) => acc + (Number(item.price || 0) * Number(item.quantity || 1)), 0);
        
          PaymentInfoModal(({ nom_client, email, whatsapp }) => {
            const checkoutData = {
              totalPrice: totalPriceXOF,
              cart: cart,
              email: email,
              nom_client: nom_client,
              whatsapp: whatsapp,
              currency: selectedCurrency
            };
        
            fetch("/api/checkout/prepare", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(checkoutData)
            })
            .then(res => {
              if (!res.ok) throw new Error('La préparation du paiement a échoué.');
              return res.json();
            })
            .then(prepareData => {
              const articleObject = {};
              cart.forEach(item => {
                articleObject[item.name] = Number(item.price) * (item.quantity || 1);
              });
        
              const numeroClient = (whatsapp || "").trim();
        
              const paymentData = {
                totalPrice: totalPriceXOF,
                article: [articleObject],
                numeroSend: numeroClient,
                nomclient: nom_client.trim(),
                personal_Info: [{ userId: nom_client, orderId: `cart_${prepareData.cart_id}` }],
                return_url: window.location.origin + "/callback",
                webhook_url: window.location.origin + "/webhook",
                currency: "XOF"
              };
        
              return fetch("/payer", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(paymentData)
              });
            })
            .then(res => res.json())
            .then(paymentResponse => {
              if (paymentResponse.url) {
                localStorage.removeItem("cart");
                window.location.href = paymentResponse.url;
              } else {
                throw new Error(paymentResponse.error || "Erreur inconnue lors de la création du lien de paiement.");
              }
            })
            .catch(err => {
              showNotification("Erreur technique : " + err.message, "error");
              console.error("Erreur dans le flux de paiement :", err);
            });
          }, () => {
            showNotification("Paiement annulé.", "info");
          });
        }

        buyDirectlyButtons.forEach(button => {
            button.addEventListener('click', () => {
                const productName = button.getAttribute('data-name');
                const productPrice = parseFloat(button.getAttribute('data-price'));
                const cart = [{ name: productName, price: productPrice, quantity: 1 }];
                redirectToPayment(productPrice, cart);
            });
        });

        if (buyFromCartButton) {
            buyFromCartButton.addEventListener('click', () => {
                const cart = JSON.parse(localStorage.getItem('cart')) || [];
                const total = getTotalPrice(cart);
                if (total > 0) {
                    redirectToPayment(total, cart);
                } else {
                    showNotification("Votre panier est vide. Ajoutez des articles pour continuer.", 'error');
                }
            });
        }

        if (closeCartButton && cartBar) {
            closeCartButton.addEventListener('click', () => {
                cartBar.classList.toggle('visible');
            });
        }

        window.__da_cart = {
            render: renderCart,
            convertNow: () => convertCartNow()
        };

        updateCartBadge(false);
        renderCart();
        updateAddToCartButtons();
    }

    initCartDigital();

    // --- Commentaires "voir plus" ---
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

    (function initProductFaqToggles() {
      const items = document.querySelectorAll('.product-faq-item');
      items.forEach(item => {
        const q = item.querySelector('.product-faq-question');
        const a = item.querySelector('.product-faq-answer');
        if (!q || !a) return;

        // Masquer par défaut, en forçant l'override de toute règle !important éventuelle
        a.style.setProperty('display', 'none', 'important');

        q.addEventListener('click', () => {
          const isHidden = getComputedStyle(a).display === 'none';
          if (isHidden) {
            a.style.setProperty('display', 'block', 'important');
            item.classList.add('open');
          } else {
            a.style.setProperty('display', 'none', 'important');
            item.classList.remove('open');
          }
        });
      });
    })();

    // --- FAQ ---
    document.querySelectorAll(".faq-item").forEach((faqItem) => {
        const question = faqItem.querySelector(".faq-question");
        question.addEventListener("click", () => {
            faqItem.classList.toggle("closed");
        });
    });

};

(function bannerMarqueeAutoDuration() {
    let resizeTO = null;

    function recalcDuration() {
        const banner = document.getElementById('site-announcement-banner');
        if (!banner) return;
        const content = banner.querySelector('.announcement-banner-content');
        if (!content) return;

        const contentWidth = content.scrollWidth || 0;
        const viewport = banner.clientWidth || window.innerWidth || 360;

        const isMobile = window.matchMedia('(max-width: 600px)').matches;
        const pxPerSec = isMobile ? 70 : 90;

        const distance = contentWidth + viewport;
        const duration = Math.max(8, distance / pxPerSec);

        content.style.animationDuration = duration + 's';
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', recalcDuration);
    } else {
        recalcDuration();
    }

    window.addEventListener('resize', () => {
        clearTimeout(resizeTO);
        resizeTO = setTimeout(recalcDuration, 120);
    });

    const banner = document.getElementById('site-announcement-banner');
    if (banner) {
        const mo = new MutationObserver(() => setTimeout(recalcDuration, 0));
        mo.observe(banner, { childList: true, subtree: true });
    }
})();

// ===== Locale Switcher =====
document.addEventListener('DOMContentLoaded', () => {
    const SUPPORTED = ['XOF','USD','EUR','GBP','AED','RUB','CNY','JPY'];
    const XOF_ZONE = new Set(['CI','SN','BJ','BF','TG','ML','NE','GW']);
    const SYMBOL = { XOF:'XOF', USD:'$', EUR:'€', GBP:'£', AED:'د.إ', RUB:'₽', CNY:'¥', JPY:'¥' };
    let RATES_XOF = null;

    const flagUrl = cc => `https://cdn.jsdelivr.net/gh/lipis/flag-icons@6.6.6/flags/1x1/${String(cc||'').toLowerCase()}.svg`;

    function saveRatesCache(rates) { try { localStorage.setItem('da_fx_rates', JSON.stringify({ rates, ts: Date.now() })); } catch {} }
    function loadRatesCache(maxAgeMs = 6 * 60 * 60 * 1000) {
      try {
        const raw = localStorage.getItem('da_fx_rates');
        if (!raw) return null;
        const obj = JSON.parse(raw);
        if (!obj || !obj.rates) return null;
        if (typeof obj.ts === 'number' && (Date.now() - obj.ts) <= maxAgeMs) return obj.rates;
        return obj.rates;
      } catch { return null; }
    }
    async function loadRates() {
      try {
        const r = await fetch('/api/fx-rates', { credentials:'same-origin', cache:'no-store' });
        const j = await r.json();
        if (j && j.status === 'success' && j.rates) {
          RATES_XOF = j.rates;
          saveRatesCache(RATES_XOF);
        }
      } catch {}
    }
    async function ensureRates() {
      if (!RATES_XOF) RATES_XOF = loadRatesCache() || null;
      if (!RATES_XOF) await loadRates();
      return !!RATES_XOF;
    }

    const SYMBOL_TO_CUR = {'$':'USD','€':'EUR','£':'GBP','¥':'CNY','₽':'RUB','د.إ':'AED'};
    function parseNumberFromText(txt) {
      if (!txt) return NaN;
      const cleaned = txt.replace(/\s|\u00A0|\u202F/g,'');
      const m = cleaned.match(/[-+]?\d+(?:[.,]\d+)?/);
      if (!m) return NaN;
      return parseFloat(m[0].replace(',', '.'));
    }
    function parseCurrencyFromText(txt) {
      if (!txt) return null;
      const cm = txt.match(/\b(XOF|USD|EUR|GBP|AED|RUB|CNY|JPY)\b/i);
      if (cm) return cm[1].toUpperCase();
      const sm = txt.match(/[$€£¥₽]|د\.?إ/);
      return sm ? (SYMBOL_TO_CUR[sm[0]] || null) : null;
    }
    
    function ensureDatasetForPrice(el) {
      const attrPrice = parseFloat(el.getAttribute('data-price') || 'NaN');
      const hasDataPriceAttr = !isNaN(attrPrice);
      if (el.dataset.basePrice) {
        const currentBase = parseFloat(el.dataset.basePrice);
        if (hasDataPriceAttr && isFinite(attrPrice) && attrPrice !== currentBase) {
          el.dataset.basePrice = String(attrPrice);
          const attrCur = (el.getAttribute('data-currency') || el.dataset.baseCurrency || 'XOF').toUpperCase();
          el.dataset.baseCurrency = attrCur;
          return true;
        }
        return true;
      }
      if (!el.hasAttribute('data-price') && el.children && el.children.length > 0) return false;
      let basePrice = parseFloat(el.getAttribute('data-price') || 'NaN');
      let baseCur = (el.getAttribute('data-currency') || '').toUpperCase();
      if (!isFinite(basePrice)) basePrice = parseNumberFromText(el.textContent);
      if (!baseCur) baseCur = parseCurrencyFromText(el.textContent) || 'XOF';
      if (!isFinite(basePrice)) return false;
      el.dataset.basePrice = String(basePrice);
      el.dataset.baseCurrency = baseCur;
      if (!el.hasAttribute('data-price')) el.setAttribute('data-price', String(basePrice));
      if (!el.hasAttribute('data-currency')) el.setAttribute('data-currency', baseCur);
      return true;
    }
    function annotateLikelyPriceSpans() {
      const candidates = document.querySelectorAll(
        '.product-price, .product-old-price, .current-price, .old-price, [data-price]'
      );
      candidates.forEach(el => {
        if (
          el.hasAttribute('data-noconvert') ||
          el.classList.contains('product-badge') ||
          el.closest('.product-badges-container') ||
          el.closest('.product-buttons') ||
          el.matches('button, .btn, .btn-buy, .add-to-cart, .product-action, [role="button"]')
        ) {
          return;
        }
        ensureDatasetForPrice(el);
      });
    }
    function convertAmountViaXOF(amount, fromCur, toCur) {
      if (!RATES_XOF || !isFinite(amount)) return amount;
      if (fromCur === toCur) return amount;
      try {
        const rFrom = fromCur === 'XOF' ? 1 : RATES_XOF[fromCur];
        const inXof = rFrom ? (fromCur === 'XOF' ? amount : amount / rFrom) : amount;
        const rTo = toCur === 'XOF' ? 1 : RATES_XOF[toCur];
        return rTo ? (toCur === 'XOF' ? inXof : inXof * rTo) : inXof;
      } catch { return amount; }
    }
    function formatAmount(amount, currency) {
      return `${Number(amount).toLocaleString('fr-FR', {maximumFractionDigits:2})} ${SYMBOL[currency] || currency}`;
    }
    function convertDisplayedPrices(targetCurrency) {
      if (!RATES_XOF) return 0;
      const fromDataAttr = Array.from(document.querySelectorAll('[data-price]')).filter(el => {
        if (el.hasAttribute('data-noconvert')) return false;
        if (el.classList.contains('product-badge') || el.closest('.product-badges-container')) return false;
        if (el.closest('.product-buttons')) return false;
        if (el.matches('button, .btn, .btn-buy, .add-to-cart, .product-action, [role="button"]')) return false;
        return true;
      });
      const fromClasses = Array.from(
        document.querySelectorAll('.product-price, .product-old-price, .current-price, .old-price')
      ).filter(el => {
        if (el.hasAttribute('data-noconvert')) return false;
        if (el.classList.contains('product-badge') || el.closest('.product-badges-container')) return false;
        if (el.closest('.product-buttons')) return false;
        if (el.matches('button, .btn, .btn-buy, .add-to-cart, .product-action, [role="button"]')) return false;
        return (el.hasAttribute('data-price') || !el.children || el.children.length === 0);
      });
      const seen = new Set(); const nodes = [];
      [...fromDataAttr, ...fromClasses].forEach(el => { if (!seen.has(el)) { seen.add(el); nodes.push(el); } });

      let converted = 0;
      nodes.forEach(el => {
        if (!ensureDatasetForPrice(el)) return;
        const base = parseFloat(el.dataset.basePrice);
        const fromCur = (el.dataset.baseCurrency || 'XOF').toUpperCase();
        const conv = convertAmountViaXOF(base, fromCur, targetCurrency);
        el.textContent = formatAmount(conv, targetCurrency);
        el.setAttribute('data-currency', targetCurrency);
        converted++;
      });
      return converted;
    }

    window.__da_debugLocale = {
      convert: async function(targetCurrency) {
        try {
          await ensureRates();
          annotateLikelyPriceSpans();
          if (!targetCurrency) {
            const sel = (()=>{ try { return JSON.parse(localStorage.getItem('da_locale')||'{}'); } catch { return {}; } })();
            targetCurrency = (sel.currency || 'XOF').toUpperCase();
          }
          convertDisplayedPrices(targetCurrency);
          requestAnimationFrame(() => convertDisplayedPrices(targetCurrency));
        } catch (_) {}
      }
    };

    function pickSupportedCurrency(cc, countryCurrency, region) {
      const cur = String(countryCurrency || '').toUpperCase();
      if (SUPPORTED.includes(cur)) return cur;
      const regionLC = String(region || '').toLowerCase();
      if (XOF_ZONE.has(String(cc || '').toUpperCase())) return 'XOF';
      if (regionLC === 'europe') return 'EUR';
      if (regionLC.includes('america')) return 'USD';
      if (['asia','africa'].includes(regionLC) && cur.startsWith('A')) return 'AED';
      if (regionLC === 'asia') return 'CNY';
      return 'USD';
    }
    async function fetchAllCountries() {
      try {
        const url = 'https://restcountries.com/v3.1/all?fields=cca2,name,currencies,languages,region';
        const r = await fetch(url, { cache: 'force-cache' });
        const arr = await r.json();
        const list = arr.map(it => {
          const code = String(it.cca2 || '').toLowerCase();
          const name = (it.name && it.name.common) ? it.name.common : code.toUpperCase();
          const region = it.region || '';
          const cur = it.currencies ? Object.keys(it.currencies)[0] : '';
          const langCode = it.languages ? Object.keys(it.languages)[0] : 'en';
          const currency = pickSupportedCurrency(code, cur, region);
          return { code, name, currency, lang: langCode || 'en', region };
        }).filter(x => x.code);
        list.sort((a,b) => a.name.localeCompare(b.name, 'fr'));
        return list;
      } catch {
        return [ {code:'ci', name:"Côte d'Ivoire", currency:'XOF', lang:'fr'}, {code:'sn', name:'Sénégal', currency:'XOF', lang:'fr'}, {code:'tg', name:'Togo', currency:'XOF', lang:'fr'}, {code:'fr', name:'France', currency:'EUR', lang:'fr'}, {code:'us', name:'United States', currency:'USD', lang:'en'} ];
      }
    }
    async function geolocateCountry() {
      try {
        const r = await fetch('https://ipapi.co/json/', { cache: 'no-store' });
        const j = await r.json();
        if (j && j.country) return String(j.country).toLowerCase();
      } catch {}
      try {
        const r2 = await fetch('https://api.country.is', { cache: 'no-store' });
        const j2 = await r2.json();
        if (j2 && j2.country) return String(j2.country).toLowerCase();
      } catch {}
      return null;
    }

    const timeEl = document.getElementById('gmt-time');
    const wrap = document.createElement('div');
    wrap.className = 'locale-switch-wrap';
    wrap.innerHTML = `
      <button id="localeSwitchBtn" class="locale-switch" aria-haspopup="listbox" aria-expanded="false" title="Choisir un pays">
        <img id="localeFlagImg" class="flag" alt="flag" />
        <span id="localeCur" class="locale-code">XOF</span>
      </button>
      <div id="localePanel" class="locale-panel" role="listbox" aria-label="Choisir un pays">
        <div class="locale-search"><input id="localeSearch" type="search" placeholder="Rechercher un pays..." autocomplete="off" /></div>
        <div class="country-list" id="countryList"></div>
      </div>
    `;
    if (timeEl && timeEl.parentNode) {
      timeEl.parentNode.replaceChild(wrap, timeEl);
    } else {
      const navRight = document.querySelector('.right-nav, .nav-right');
      if (navRight) navRight.appendChild(wrap);
    }

    const btn = document.getElementById('localeSwitchBtn');
    const panel = document.getElementById('localePanel');
    const list = document.getElementById('countryList');
    const search = document.getElementById('localeSearch');
    const flagImg = document.getElementById('localeFlagImg');
    let curEl = document.getElementById('localeCur') || document.getElementById('localeLang');
    if (!curEl) {
      curEl = document.createElement('span');
      curEl.id = 'localeCur';
      curEl.className = 'locale-code';
      curEl.textContent = 'XOF';
      const btnInnerFlag = document.getElementById('localeFlagImg');
      const btn2 = document.getElementById('localeSwitchBtn');
      if (btnInnerFlag && btnInnerFlag.parentNode) {
        btnInnerFlag.parentNode.insertBefore(curEl, btnInnerFlag.nextSibling);
      } else if (btn2) {
        btn2.appendChild(curEl);
      }
    }

    let ALL_LOCALES = [];

    function setFlag(code) {
      if (!code) { flagImg.removeAttribute('src'); return; }
      flagImg.src = flagUrl(code);
      flagImg.alt = `${String(code||'').toUpperCase()} flag`;
    }
    function mountList(filterText) {
      const q = String(filterText || '').trim().toLowerCase();
      list.innerHTML = '';
      ALL_LOCALES.filter(it => !q || it.name.toLowerCase().includes(q) || String(it.currency||'').toLowerCase().includes(q) || it.code.includes(q))
        .forEach(it => {
          const item = document.createElement('div');
          item.className = 'country-item';
          item.dataset.country = it.code;
          item.innerHTML = `<img class="flag" src="${flagUrl(it.code)}" alt="${it.code.toUpperCase()} flag" loading="lazy" /><div class="label"><span class="name">${it.name}</span><span class="meta">${String(it.currency||'').toUpperCase()} • ${String(it.lang||'').toUpperCase()}</span></div>`;
          item.addEventListener('click', () => selectCountry({ country: it.code, currency: it.currency, lang: it.lang }));
          list.appendChild(item);
        });
    }
    function openPanel() { panel.classList.add('open'); btn.setAttribute('aria-expanded','true'); search.value = ''; mountList(''); setTimeout(() => search.focus(), 10); }
    function closePanel() { panel.classList.remove('open'); btn.setAttribute('aria-expanded','false'); }
    btn.addEventListener('click', (e) => { e.stopPropagation(); if (panel.classList.contains('open')) closePanel(); else openPanel(); });
    document.addEventListener('click', (e) => { if (!panel.contains(e.target) && e.target !== btn) closePanel(); });
    search.addEventListener('input', () => mountList(search.value));

    function saveLocale(sel) { try { localStorage.setItem('da_locale', JSON.stringify(sel)); } catch {} }
    function loadLocale() { try { const r = localStorage.getItem('da_locale'); return r ? JSON.parse(r) : null; } catch { return null; } }
    function persistSelection(sel) {
      saveLocale(sel);
      fetch('/api/locale', { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body: JSON.stringify(sel) }).catch(()=>{});
      document.documentElement.lang = sel.lang || 'fr';
    }

    function applySelection(sel, persist=false) {
      setFlag(sel.country);
      if (curEl) curEl.textContent = String(sel.currency || 'XOF').toUpperCase();
      if (persist) persistSelection(sel);
    }

    async function selectCountry(sel) {
      await ensureRates();
      applySelection(sel, true);

      try {
        if (window.__da_cart && typeof window.__da_cart.render === 'function') {
          window.__da_cart.render();
        }
      } catch (_) {}

      annotateLikelyPriceSpans();
      convertDisplayedPrices(sel.currency);
      requestAnimationFrame(() => convertDisplayedPrices(sel.currency));
      closePanel();
    }

    (async function initLocale() {
      annotateLikelyPriceSpans();

      let chosen = loadLocale();
      ALL_LOCALES = await fetchAllCountries();

      if (!chosen) {
        const geo = await geolocateCountry();
        const found = ALL_LOCALES.find(x => x.code === geo);
        if (found) chosen = { country: found.code, currency: found.currency, lang: found.lang };
      }
      if (!chosen) {
        chosen = { country:'ci', currency:'XOF', lang:'fr' };
      }

      await ensureRates();

      applySelection(chosen, true);
      annotateLikelyPriceSpans();
      convertDisplayedPrices(chosen.currency);
      requestAnimationFrame(() => convertDisplayedPrices(chosen.currency));

      try {
        if (window.__da_cart && typeof window.__da_cart.convertNow === 'function') {
          window.__da_cart.convertNow();
        }
      } catch (_) {}
    })();
}); 

// --- Initialisation globale ---
document.addEventListener('DOMContentLoaded', () => {
    window.initProductSearchSort();
    window.initCategoryFilter();
    window.initProductPage();
});
