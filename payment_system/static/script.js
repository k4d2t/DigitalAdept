// ---- GESTION AFFICHAGE & LOGIQUE PAIEMENT ----
let selectedNetwork = null;
const yasBtn = document.getElementById("yas");
const moovBtn = document.getElementById("moov");
const infos = document.getElementById("payment-infos");
const proofSection = document.getElementById("proof-section");
const imgBtn = document.getElementById("img-btn");
const refBtn = document.getElementById("ref-btn");
const imgForm = document.getElementById("img-form");
const refForm = document.getElementById("ref-form");
const messageDiv = document.getElementById("message");
const userIdInput = document.getElementById("user_id");
const userId = userIdInput ? userIdInput.value : null;
// On récupère le <b> à l'intérieur de la div avec la classe "payment-amount"
let paymentAmountElement = document.querySelector(".payment-amount span");
let paymentAmount = paymentAmountElement ? paymentAmountElement.innerText : "";



// Feedback handler
function showMessage(msg, isError = false) {
    if (!messageDiv) return;
    messageDiv.textContent = msg || '';
    if (msg && msg.length > 0) {
        messageDiv.classList.add('visible');
        if (isError) {
            messageDiv.classList.add('error');
        } else {
            messageDiv.classList.remove('error');
        }
    } else {
        messageDiv.classList.remove('visible');
        messageDiv.classList.remove('error');
    }
}

if (yasBtn && moovBtn && infos && proofSection) {
    yasBtn.onclick = function() {
        selectedNetwork = "yas";
        infos.innerHTML = `Veuillez envoyer <b>${paymentAmount}</b> au <b>+228 70 55 31 92</b>`;
        proofSection.style.display = "block";
        showMessage("");
    };
    moovBtn.onclick = function() {
        selectedNetwork = "moov";
        infos.innerHTML = `Veuillez envoyer <b>${paymentAmount}</b> au <b>+228 99 58 35 83</b>`;
        proofSection.style.display = "block";
        showMessage("");
    };
}

if (imgBtn && imgForm && refForm && refBtn) {
    imgBtn.onclick = function() {
        imgForm.style.display = "block";
        refForm.style.display = "none";
        showMessage("");
    };
    refBtn.onclick = function() {
        refForm.style.display = "block";
        imgForm.style.display = "none";
        showMessage("");
    };
}

// ---- UPLOAD STYLÉ : affiche le nom du fichier choisi ----
function showFileName(event) {
    const input = event.target;
    const nameDiv = document.getElementById('file-name');
    const labelText = document.getElementById('file-label-text');
    if (input.files && input.files.length > 0) {
        nameDiv.textContent = input.files[0].name;
        if (labelText) labelText.textContent = "Image sélectionnée";
    } else {
        nameDiv.textContent = "";
        if (labelText) labelText.textContent = "Sélectionner une image";
    }
}

// Clique sur le label pour ouvrir l'upload caché
document.addEventListener('DOMContentLoaded', function() {
    const label = document.getElementById('customFileLabel');
    const input = document.getElementById('proof_file');
    if(label && input) {
        label.onclick = function(e) {
            input.click();
        };
    }
});

// ---- ENVOI AJAX DES PREUVES ----
if (imgForm) {
    imgForm.onsubmit = async function(e) {
        e.preventDefault();
        let formData = new FormData(imgForm);
        formData.set("user_id", userId);
        formData.set("proof_type", "image");
        let resp = await fetch("/send_proof", { method: "POST", body: formData });
        let data = await resp.json();
        showMessage(data.message, !data.success);
        if (data.success) startPollingStatus(userId);
    };
}
if (refForm) {
    refForm.onsubmit = async function(e) {
        e.preventDefault();
        let formData = new FormData(refForm);
        formData.set("user_id", userId);
        formData.set("proof_type", "ref");
        let refValue = refForm.querySelector('input[name="reference"]')?.value || "";
        formData.set("reference", refValue);
        let resp = await fetch("/send_proof", { method: "POST", body: formData });
        let data = await resp.json();
        showMessage(data.message, !data.success);
        if (data.success) startPollingStatus(userId);
    };
}

// ---- AUTO-REFRESH STATUT ET CART CLEARING ----
let pollingStatus = false;
let pollingInterval = null;



function startPollingStatus(userId) {
    if (pollingStatus) return; // Évite plusieurs intervals
    pollingStatus = true;
    pollingInterval = setInterval(async function() {
        let resp = await fetch(`/status/${userId}`);
        let data = await resp.json();

        if (data.status === "approved") {
            clearInterval(pollingInterval);
            // Vide le panier après approbation
            window.location.href = `/result/${userId}`;
        } else if (data.status === "rejected") {
            clearInterval(pollingInterval);
            window.location.href = `/result/${userId}`;
        }
    }, 4000);
}

