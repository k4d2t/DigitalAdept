import os
import asyncio
import tempfile
from flask import Flask, request
from telegram.request import HTTPXRequest
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
import requests

TELEGRAM_TOKEN = "8033540599:AAHfLrLZ4HJqHcAb0b26MoePsRdh_5DMAFY"
GROUP_ID = -1002630529273
THREAD_ID = 10
MOCKAPI_URL = "https://6840a10f5b39a8039a58afb0.mockapi.io/api/paiement/paiement"
TEMP_DIR = "static"

flask_app = Flask(__name__)
os.makedirs(TEMP_DIR, exist_ok=True)

def get_user_by_userid(user_id):
    try:
        r = requests.get(MOCKAPI_URL, params={"user_id": user_id}, timeout=5)
        res = r.json()
        if isinstance(res, list) and res:
            return res[0]
        return None
    except Exception as e:
        print("Erreur get_user_by_userid:", e)
        return None

def update_user_by_userid(user_id, update_dict):
    user = get_user_by_userid(user_id)
    if not user:
        return False
    try:
        r = requests.put(f"{MOCKAPI_URL}/{user['id']}", json=update_dict, timeout=5)
        return r.ok
    except Exception as e:
        print("Erreur update_user_by_userid:", e)
        return False

async def send_proof_to_group(application, user_id):
    user = get_user_by_userid(user_id)
    if not user:
        print(f"[ERREUR] Aucun user_data pour {user_id}")
        return
    proof = user.get("proof")
    proof_type = user.get("type")
    caption = (
        "Nouvelle preuve de paiement !\n"
        f"ID utilisateur : <code>{user_id}</code>\n"
        f"Type : {proof_type}"
    )
    try:
        if proof_type == "ref":
            await application.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=THREAD_ID,
                text=f"{caption}\nRéférence : <code>{proof}</code>",
                parse_mode="HTML"
            )
            print(f"[OK] Preuve ref envoyée pour {user_id}")
        else:
            await application.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=THREAD_ID,
                text=f"[ERREUR] Type de preuve inconnu (ou image non supportée ici) pour <code>{user_id}</code>",
                parse_mode="HTML"
            )
            print(f"[ERREUR] Type de preuve inconnu (ou image) pour {user_id}: {proof_type}")
    except Exception as e:
        print(f"[EXCEPTION] lors de l'envoi Telegram: {e}")

# --- Handlers Telegram ---

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Utilisation: /approve <user_id>")
        return
    user_id = args[0]
    if update_user_by_userid(user_id, {"status": "approved"}):
        await update.message.reply_text(f"Preuve approuvée pour {user_id}")
    else:
        await update.message.reply_text(f"Utilisateur {user_id} introuvable.")

async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Utilisation: /reject <user_id>")
        return
    user_id = args[0]
    if update_user_by_userid(user_id, {"status": "rejected"}):
        await update.message.reply_text(f"Preuve refusée pour {user_id}")
    else:
        await update.message.reply_text(f"Utilisateur {user_id} introuvable.")

async def private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ce bot ne répond qu'aux commandes dans le groupe.")

# --- Flask route pour notification ---
@flask_app.route("/notify", methods=["POST"])
def notify():
    print("Requête /notify reçue")
    event_loop = application.bot_data.get("tg_event_loop")
    if event_loop is None:
        print("Boucle Telegram non initialisée, aucun message Telegram ne sera envoyé.")
        return {"ok": False, "error": "Bot event loop not initialized"}

    # --- Cas image ---
    if 'photo' in request.files:
        user_id = request.form.get("user_id")
        photo = request.files.get("photo")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir=TEMP_DIR) as tmp:
            temp_path = tmp.name
            photo.save(temp_path)

        caption = (
            "Nouvelle preuve de paiement !\n"
            f"ID utilisateur : <code>{user_id}</code>\n"
            f"Type : image"
        )

        async def send_image():
            try:
                with open(temp_path, "rb") as img:
                    await application.bot.send_photo(
                        chat_id=GROUP_ID,
                        message_thread_id=THREAD_ID,
                        photo=img,
                        caption=caption,
                        parse_mode="HTML"
                    )
                print(f"[OK] Preuve image envoyée pour {user_id}")
            except Exception as e:
                print(f"[EXCEPTION] lors de l'envoi Telegram (image): {e}")

        try:
            future = asyncio.run_coroutine_threadsafe(send_image(), event_loop)
            future.result(timeout=10)
        finally:
            try:
                os.remove(temp_path)
                print(f"Fichier {temp_path} supprimé après envoi.")
            except Exception as e:
                print(f"[WARN] Impossible de supprimer {temp_path}: {e}")

        return {"ok": True}

    # --- Cas référence (texte) ---
    user_id = request.form.get("user_id") or (request.json and request.json.get("user_id"))
    ref = request.form.get("reference") or (request.json and request.json.get("reference"))
    if user_id and ref:
        caption = (
            "Nouvelle preuve de paiement !\n"
            f"ID utilisateur : <code>{user_id}</code>\n"
            f"Type : ref\n"
            f"Référence : <code>{ref}</code>"
        )
        async def send_ref():
            try:
                await application.bot.send_message(
                    chat_id=GROUP_ID,
                    message_thread_id=THREAD_ID,
                    text=caption,
                    parse_mode="HTML"
                )
                print(f"[OK] Preuve ref envoyée pour {user_id}")
            except Exception as e:
                print(f"[EXCEPTION] lors de l'envoi Telegram (ref): {e}")
        future = asyncio.run_coroutine_threadsafe(send_ref(), event_loop)
        future.result(timeout=10)
        return {"ok": True}

    return {"ok": False, "error": "Aucune preuve envoyée"}

def start_flask():
    port = int(os.environ.get('PORT', 5000))  # Utilise le PORT de Render ou 5000 en local
    flask_app.run(port=port, threaded=True)

def main():
    global application
    request_ = HTTPXRequest(connect_timeout=5, read_timeout=10, write_timeout=10, pool_timeout=5)
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).request(request_).build()
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CommandHandler("reject", reject))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, private_message))
    print("Bot Telegram prêt.")

    import threading
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application.bot_data["tg_event_loop"] = loop

    application.run_polling()

if __name__ == "__main__":
    main()
