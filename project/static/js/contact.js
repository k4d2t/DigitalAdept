function initContactPage() {
    const contactForm = document.querySelector("#contact-form");
    if (!contactForm) {
        console.warn("Formulaire de contact introuvable !");
        return;
    }

    const submitButton = contactForm.querySelector("button[type='submit']");
    contactForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        // Collecter les données du formulaire
        const formData = new FormData(contactForm);

        // Désactiver le bouton pour éviter les doubles soumissions
        submitButton.disabled = true;
        submitButton.textContent = "Envoi...";

        let resetStyleTimeout;
        try {
            // Envoyer les données au backend
            const response = await fetch(contactForm.action, {
                method: contactForm.method,
                body: formData,
            });

            const result = await response.json();

            if (response.ok && result.status === "success") {
                // Succès : notification, son, style bouton
                showNotification("Votre message a été envoyé avec succès !", "success", {icon: ""});
                submitButton.textContent = "Succès";
                submitButton.classList.add("success");
            } else {
                // Erreur côté serveur
                showNotification(result.message || "Une erreur est survenue. Veuillez réessayer.", "error", {icon: ""});
                submitButton.textContent = "Échec";
                submitButton.classList.add("error");
            }
        } catch (error) {
            console.error("Erreur lors de l'envoi :", error);
            showNotification("Impossible d'envoyer le message. Vérifiez votre connexion.", "error", {icon: ""});
            submitButton.textContent = "Erreur";
            submitButton.classList.add("error");
        } finally {
            // Remettre le bouton "Envoyer" et le réactiver après délai visuel
            clearTimeout(resetStyleTimeout);
            resetStyleTimeout = setTimeout(() => {
                submitButton.textContent = "Envoyer";
                submitButton.disabled = false;
                submitButton.classList.remove("success", "error");
                contactForm.reset();
            }, 3000);
        }
    });
}
document.addEventListener("DOMContentLoaded", () => {
    console.log("Initialisation de la page de contact...");
    initContactPage();
});
