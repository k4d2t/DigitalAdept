// --- Initialisation et configuration des notifications ---
// Container pour les notifications utilisateur
const notificationContainer = document.getElementById("notification-container") || document.createElement("div");
notificationContainer.id = "notification-container";

// Ajoute le conteneur au body s'il n'existe pas déjà
if (!document.body.contains(notificationContainer)) {
    document.body.appendChild(notificationContainer);
}

// Précharge les sons pour succès et échec
const successSound = new Audio("/static/sounds/success.wav");
const errorSound = new Audio("/static/sounds/error.wav");

successSound.preload = 'none'
errorSound.preload = 'none'
// --- Attache la fonction au window global ---
window.showNotification = function (message, type = "success") {
    const notification = document.createElement("div");
    notification.className = `notification ${type}`;
    notification.textContent = message;

    // Affiche le conteneur si nécessaire
    notificationContainer.style.display = "block";

    // Ajouter la notification au container
    notificationContainer.appendChild(notification);

    // Jouer le son approprié
    if (type === "success") {
        successSound.play().catch(() => console.warn("Impossible de jouer le son de succès."));
    } else if (type === "error") {
        errorSound.play().catch(() => console.warn("Impossible de jouer le son d'erreur."));
    }

    // Supprime la notification après 3 secondes
    setTimeout(() => {
        notification.classList.add("fade-out");
        notification.addEventListener("animationend", () => {
            notification.remove();

            // Masquer le conteneur s'il n'y a plus de notifications
            if (!notificationContainer.hasChildNodes()) {
                notificationContainer.style.display = "none";
            }
        });
    }, 3000);
};
