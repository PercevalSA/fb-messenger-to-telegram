from pathlib import Path
import shutil
from telethon.sync import TelegramClient
import json
from datetime import datetime
import time
import os
import tomllib
from loguru import logger

DEFAULT_CONFIGURATION_FILE    = Path(__file__).parent / 'config.toml'
CONFIGURATION_FILE_TEMPLATE = Path(__file__).parent / 'configuration-template.toml'

json_file = 'export/message_1.json'
base_path = 'export'  # dossier racine de l'export Messenger
destination_chat = 'nom_du_groupe_ou_du_canal'  # ID ou @username du groupe/canal cible

def load_configuration_from_file(configuration_file: Path = DEFAULT_CONFIGURATION_FILE) -> dict:
    """
    Charge la configuration depuis un fichier TOML.
    :param configuration_file: Chemin vers le fichier de configuration.
    :return: Dictionnaire de configuration.
    """
    if not configuration_file.exists():
        logger.info(f"Configuration file not found: {configuration_file}")
        logger.info("Creating one from template. Please complete the content")
        if not CONFIGURATION_FILE_TEMPLATE.exists():
            logger.error("Template configuration file not found.")
            return {}
        shutil.copy2(CONFIGURATION_FILE_TEMPLATE, configuration_file)
        return {}

    with open(configuration_file, 'rb') as f:
        return tomllib.load(f)


def load_configuration() -> dict:
    configuration =  load_configuration_from_file()
    if configuration == {}:
        logger.error("Configuration file is missing or incomplete. Please check the template.")
        exit(1)

    return configuration

    

# === CHARGEMENT DES MESSAGES JSON ===
def load_messages(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    messages = []
    for idx, msg in enumerate(data.get('messages', [])):
        if msg.get('type') != 'Generic':
            continue

        date = datetime.fromtimestamp(msg['timestamp_ms'] / 1000)
        sender = msg.get('sender_name')
        text = msg.get('content', '')
        photos = [os.path.join(base_path, p['uri']) for p in msg.get('photos', [])]
        videos = [os.path.join(base_path, v['uri']) for v in msg.get('videos', [])]
        audios = [os.path.join(base_path, a['uri']) for a in msg.get('audio_files', [])]
        reply_to = msg.get('reply_to')  # valeur personnalisée si elle existe (id/message key)

        messages.append({
            'id': idx,  # ID interne
            'sender': sender,
            'text': text,
            'photos': photos,
            'videos': videos,
            'audios': audios,
            'date': date,
            'reply_to': reply_to
        })

    return sorted(messages, key=lambda x: x['date'])


# === ENVOI DANS TELEGRAM AVEC LES DEUX COMPTES ===
async def send_conversation(messages):
    # Connexion de chaque compte
    clients = {}
    for sender, conf in sender_map.items():
        client = TelegramClient(conf['name'], conf['api_id'], conf['api_hash'])
        await client.start()
        clients[sender] = client

    # Entité cible (groupe, canal)
    entity = await list(clients.values())[0].get_entity(destination_chat)

    # Mapping messages Messenger → message.id Telegram
    message_map = {}

    for msg in messages:
        sender = msg['sender']
        client = clients.get(sender)
        if not client:
            print(f"❌ Pas de session définie pour {sender}")
            continue

        reply_to_id = None
        if msg.get('reply_to') is not None:
            reply_to_id = message_map.get(msg['reply_to'])

        final_text = (
            f"🕒 {msg['date'].strftime('%d/%m/%Y %H:%M')}\n"
            f"{msg['text']}" if msg['text'] else None
        )

        sent_message = None

        if final_text:
            sent_message = await client.send_message(
                entity,
                final_text,
                reply_to=reply_to_id
            )

        # Médias
        for photo in msg['photos']:
            if os.path.exists(photo):
                sent_message = await client.send_file(
                    entity,
                    photo,
                    reply_to=reply_to_id
                )

        for video in msg['videos']:
            if os.path.exists(video):
                sent_message = await client.send_file(
                    entity,
                    video,
                    reply_to=reply_to_id
                )

        for audio in msg['audios']:
            if os.path.exists(audio):
                sent_message = await client.send_file(
                    entity,
                    audio,
                    voice_note=True,
                    reply_to=reply_to_id
                )

        # Enregistrer l'ID Telegram du message envoyé
        if sent_message:
            message_map[msg['id']] = sent_message.id

        time.sleep(0.5)

    for client in clients.values():
        await client.disconnect()

    print("✅ Importation terminée avec succès.")


if __name__ == '__main__':
    print("Hello from fb-messenger-to-telegram!")
    configuration = load_configuration()

    messages = load_messages(json_file)

    with TelegramClient('runner', configuration["user1_api_id"], configuration["user1_api_hash"]) as runner:
        runner.loop.run_until_complete(send_conversation(messages))

