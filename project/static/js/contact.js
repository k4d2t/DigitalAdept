function initContactPage() {
    const contactForm = document.querySelector("#contact-form");
    if (!contactForm) {
        console.warn("Formulaire de contact introuvable !");
        return;
    }

    const submitButton = contactForm.querySelector("button[type='submit']");
    contactForm.addEventListener("submit", async (e) => {
        e.preventDefault(); // Empêche le comportement par défaut (rechargement)

    // Collecter les données du formulaire
    const formData = new FormData(contactForm);

    // Désactiver le bouton pour éviter les doubles soumissions
    submitButton.disabled = true;
    submitButton.textContent = "Envoi...";

    try {
        // Envoyer les données au backend
        const response = await fetch(contactForm.action, {
            method: contactForm.method,
            body: formData,
        });

        const result = await response.json();

        if (response.ok && result.status === "success") {
            // Succès : afficher une notification, jouer le son et réinitialiser
            showNotification("Votre message a été envoyé avec succès !", "success");
            successSound.play();

            submitButton.textContent = "Succès";
            submitButton.classList.add("success");
            setTimeout(() => {
                submitButton.textContent = "Envoyer";
                submitButton.disabled = false;
                submitButton.classList.remove("success");
                contactForm.reset();
            }, 3000);
        } else {
            // Erreur renvoyée par le serveur
            showNotification(result.message || "Une erreur est survenue. Veuillez réessayer.", "error");
            errorSound.play();

            submitButton.textContent = "Échec";
            submitButton.classList.add("error");
            setTimeout(() => {
                submitButton.textContent = "Envoyer";
                submitButton.disabled = false;
                submitButton.classList.remove("error");
            }, 3000);
        }
    } catch (error) {
        console.error("Erreur lors de l'envoi :", error);

        // Erreur côté client
        showNotification("Impossible d'envoyer le message. Vérifiez votre connexion.", "error");
        errorSound.play();

        submitButton.textContent = "Erreur";
        submitButton.classList.add("error");
        setTimeout(() => {
            submitButton.textContent = "Envoyer";
            submitButton.disabled = false;
            submitButton.classList.remove("error");
        }, 3000);
    }
    });
}
document.addEventListener("DOMContentLoaded", () => {
    console.log("Initialisation de la page de contact...");
    initContactPage();
});
