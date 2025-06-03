import os
import json
import uuid
import requests
from flask import Flask, render_template, request, jsonify
import time
import base64


DATA_FILE = "paiement_data.json"
# Stockage temporaire des transactions
transactions = {}
app = Flask(__name__, static_folder="static", template_folder="templates")

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def create_user():
    user_id = str(uuid.uuid4())[:8]
    data = load_data()
    data[user_id] = {
        "status": "pending",
        "proof": None,
        "type": None,
        "timestamp": time.time()
    }
    save_data(data)
    return user_id


@app.route("/payment/<encoded_key>")
def payment(encoded_key):
    """
    Décoder les détails de la transaction et afficher la page de paiement.
    """
    try:
        # Décoder la clé encodée en Base64
        raw_details = base64.b64decode(encoded_key).decode('utf-8')

        # Extraire les détails
        amount, products, timestamp = raw_details.split(':')
        products = products.split(',')  # Convertir la liste des produits

        # Générer un user_id unique pour cette transaction
        user_id = create_user()

        # Stocker les détails dans un dictionnaire temporaire
        transactions[user_id] = {
            "amount": amount,
            "products": products,
            "timestamp": timestamp
        }

        # Rediriger vers la page de paiement avec l'user_id
        return render_template("paiement.html", user_id=user_id, amount=amount, products=products)

    except Exception as e:
        print(f"Erreur de décodage : {e}")
        return "Invalid payment details", 400

@app.route("/send_proof", methods=["POST"])
def send_proof():
    import time, requests, os
    user_id = request.form.get("user_id")
    proof_type = request.form.get("proof_type")
    data = load_data()
    MAX_IMAGE_SIZE = 3 * 1024 * 1024  # 3 MB

    if not user_id:
        return jsonify({"success": False, "message": "Identifiant utilisateur manquant."})
    if not proof_type:
        return jsonify({"success": False, "message": "Type de preuve manquant."})

    if user_id not in data:
        data[user_id] = {}

    filepath = None
    if proof_type == "image":
        file = request.files.get("proof_file")
        if not file:
            return jsonify({"success": False, "message": "Aucune image reçue."})
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > MAX_IMAGE_SIZE:
            return jsonify({"success": False, "message": "Image trop lourde (max 3MB)."})
        filename = f"proof_{user_id}.png"
        filepath = os.path.join("static", filename)
        file.save(filepath)
        data[user_id]["proof"] = filename
        data[user_id]["type"] = "image"
    elif proof_type == "ref":
        ref = request.form.get("proof_ref") or request.form.get("reference")
        if not ref or len(ref.strip()) < 3:
            return jsonify({"success": False, "message": "Référence invalide."})
        data[user_id]["proof"] = ref.strip()
        data[user_id]["type"] = "ref"
    else:
        return jsonify({"success": False, "message": "Type de preuve inconnu."})

    data[user_id]["status"] = "waiting"
    data[user_id]["timestamp"] = time.time()
    save_data(data)

    # AUTOMATISATION : Notifie le bot et supprime l'image après coup
    try:
        if proof_type == "image" and filepath:
            try:
                with open(filepath, "rb") as img:
                    r = requests.post(
                        "http://localhost:5001/notify",
                        files={"photo": img},
                        data={"user_id": user_id}
                    )
                if not r.ok:
                    print("Bot non notifié ou erreur image")
            finally:
                try:
                    os.remove(filepath)
                    print(f"Suppression automatique du fichier {filepath}")
                except Exception as e:
                    print(f"[WARN] Impossible de supprimer {filepath}: {e}")
        elif proof_type == "ref":
            r = requests.post(
                "http://localhost:5001/notify",
                json={"user_id": user_id, "reference": data[user_id]["proof"]}
            )
            if not r.ok:
                print("Bot non notifié ou erreur ref")
    except Exception as e:
        print("Erreur lors de la notification au bot :", e)

    return jsonify({"success": True, "message": "Preuve envoyée avec succès, Un instant vérification en cours...."})

@app.route("/status/<user_id>")
def status(user_id):
    data = load_data()
    if user_id not in data:
        return jsonify({"status": "unknown"})
    return jsonify({"status": data[user_id]["status"]})

@app.route("/bot_update", methods=["POST"])
def bot_update():
    user_id = request.json.get("user_id")
    decision = request.json.get("decision")
    data = load_data()
    if user_id not in data:
        return jsonify({"success": False})
    if decision == "approve":
        data[user_id]["status"] = "approved"
    elif decision == "reject":
        data[user_id]["status"] = "rejected"
    save_data(data)
    return jsonify({"success": True})

@app.route("/result/<user_id>")
def result(user_id):
    data = load_data()
    status = data.get(user_id, {}).get("status", "unknown")
    return render_template("result.html", status=status, user_id=user_id)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
