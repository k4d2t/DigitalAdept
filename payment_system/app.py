import os
import uuid
import requests
from flask import Flask, render_template, request, jsonify
import time
import base64

MOCKAPI_URL = "https://6840a10f5b39a8039a58afb0.mockapi.io/api/externalapi/paiement"
transactions = {}
app = Flask(__name__, static_folder="static", template_folder="templates")

def create_user():
    user_id = str(uuid.uuid4())[:8]
    data = {
        "user_id": user_id,
        "status": "pending",
        "proof": None,
        "type": None,
        "timestamp": time.time()
    }
    r = requests.post(MOCKAPI_URL, json=data)
    if not r.ok:
        raise Exception("Erreur lors de la création d'utilisateur sur MockAPI")
    return user_id

def get_user_by_userid(user_id):
    r = requests.get(MOCKAPI_URL, params={"user_id": user_id})
    res = r.json()
    return res[0] if res else None  # On suppose unicité

def update_user_by_userid(user_id, update_dict):
    user = get_user_by_userid(user_id)
    if not user:
        return False
    r = requests.put(f"{MOCKAPI_URL}/{user['id']}", json=update_dict)
    return r.ok

@app.route("/payment/<encoded_key>")
def payment(encoded_key):
    try:
        raw_details = base64.b64decode(encoded_key).decode('utf-8')
        amount, products, timestamp = raw_details.split(':')
        products = products.split(',')

        user_id = create_user()
        transactions[user_id] = {
            "amount": amount,
            "products": products,
            "timestamp": timestamp
        }
        # --- Réveil du bot Render ! ---
        try:
            # On fait un appel GET "inutile" juste pour réveiller le bot
            requests.get("https://digitaladeptpaymentsystembot.onrender.com/ping", timeout=3)
        except Exception as e:
            # Ce n'est pas bloquant, on ignore l'erreur
            print(f"[WARN] Impossible de réveiller le bot : {e}")
        
        return render_template("paiement.html", user_id=user_id, amount=amount, products=products)
    except Exception as e:
        print(f"Erreur de décodage : {e}")
        return "Invalid payment details", 400

@app.route("/send_proof", methods=["POST"])
def send_proof():
    import time, requests, os
    user_id = request.form.get("user_id")
    proof_type = request.form.get("proof_type")
    MAX_IMAGE_SIZE = 3 * 1024 * 1024  # 3 MB

    if not user_id:
        return jsonify({"success": False, "message": "Identifiant utilisateur manquant."})
    if not proof_type:
        return jsonify({"success": False, "message": "Type de preuve manquant."})

    user_data = get_user_by_userid(user_id)
    if not user_data:
        return jsonify({"success": False, "message": "Utilisateur inconnu."})

    filepath = None
    update = {}

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
        update["proof"] = filename
        update["type"] = "image"
    elif proof_type == "ref":
        ref = request.form.get("proof_ref") or request.form.get("reference")
        if not ref or len(ref.strip()) < 3:
            return jsonify({"success": False, "message": "Référence invalide."})
        update["proof"] = ref.strip()
        update["type"] = "ref"
    else:
        return jsonify({"success": False, "message": "Type de preuve inconnu."})

    update["status"] = "waiting"
    update["timestamp"] = time.time()
    update_user_by_userid(user_id, update)

    # AUTOMATISATION : Notifie le bot et supprime l'image après coup
    try:
        if proof_type == "image" and filepath:
            try:
                with open(filepath, "rb") as img:
                    r = requests.post(
                        "https://digitaladeptpaymentsystembot.onrender.com/notify",
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
                "https://digitaladeptpaymentsystembot.onrender.com/notify",
                json={"user_id": user_id, "reference": update["proof"]}
            )
            if not r.ok:
                print("Bot non notifié ou erreur ref")
    except Exception as e:
        print("Erreur lors de la notification au bot :", e)

    return jsonify({"success": True, "message": "Preuve envoyée avec succès, Un instant vérification en cours...."})

@app.route("/status/<user_id>")
def status(user_id):
    user = get_user_by_userid(user_id)
    if not user:
        return jsonify({"status": "unknown"})
    return jsonify({"status": user["status"]})

@app.route("/bot_update", methods=["POST"])
def bot_update():
    user_id = request.json.get("user_id")
    decision = request.json.get("decision")
    if not user_id:
        return jsonify({"success": False})
    user = get_user_by_userid(user_id)
    if not user:
        return jsonify({"success": False})
    update = {}
    if decision == "approve":
        update["status"] = "approved"
    elif decision == "reject":
        update["status"] = "rejected"
    else:
        return jsonify({"success": False})
    update_user_by_userid(user_id, update)
    return jsonify({"success": True})

@app.route("/result/<user_id>")
def result(user_id):
    user = get_user_by_userid(user_id)
    status = user["status"] if user else "unknown"
    return render_template("result.html", status=status, user_id=user_id)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))  # Utilise le PORT de Render ou 5000 en local
    app.run(host='0.0.0.0', port=port)
