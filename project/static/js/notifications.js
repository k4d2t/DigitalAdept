// --- Préchargement des sons (version améliorée) ---
const notificationSounds = {
    success: new Audio("/static/sounds/success.wav"),
    error: new Audio("/static/sounds/error.wav"),
    info: new Audio("/static/sounds/info.wav"),
    warning: new Audio("/static/sounds/warning.wav"),
};
// Précharge tous les sons
Object.values(notificationSounds).forEach(sound => sound.preload = "auto");

// --- Notification utilisateur améliorée ---
window.showNotification = function (
    message,
    type = "success",
    options = {}
) {
    // Container unique pour toutes les notifications
    let notificationContainer = document.getElementById("notification-container");
    if (!notificationContainer) {
        notificationContainer = document.createElement("div");
        notificationContainer.id = "notification-container";
        document.body.appendChild(notificationContainer);
    }

    // Crée l'élément notification
    const notification = document.createElement("div");
    notification.className = `notification ${type}`;

    // Ajout d'une icône si options.icon
    if (options.icon) {
        const icon = document.createElement("span");
        icon.className = "notification-icon";
        icon.innerHTML = options.icon;
        notification.appendChild(icon);
    }

    // Ajout du texte
    const text = document.createElement("span");
    text.className = "notification-message";
    text.textContent = message;
    notification.appendChild(text);

    // Option bouton de fermeture
    if (options.closable) {
        const closeBtn = document.createElement("button");
        closeBtn.className = "notification-close";
        closeBtn.innerHTML = "&times;";
        closeBtn.onclick = () => close(true);
        notification.appendChild(closeBtn);
    }

    // Affiche le conteneur si nécessaire
    notificationContainer.style.display = "block";
    notificationContainer.appendChild(notification);

    // Joue le son (centralisé ici)
    const sound = notificationSounds[type];
    if (sound) {
        sound.currentTime = 0;
        sound.play().catch(() => {});
    }

    // Fermeture auto ou manuelle
    const duration = options.duration ?? 3000;
    let timeoutId = setTimeout(close, duration);

    // Fonction de fermeture
    function close(forced = false) {
        clearTimeout(timeoutId);
        notification.classList.add("fade-out");
        notification.addEventListener("animationend", () => {
            notification.remove();
            if (!notificationContainer.hasChildNodes()) {
                notificationContainer.style.display = "none";
            }
            if (typeof options.onClose === "function") options.onClose(forced);
        });
    }
};
