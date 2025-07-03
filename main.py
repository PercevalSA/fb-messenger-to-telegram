from telethon.sync import TelegramClient
import json
from datetime import datetime
import time
import os

# === CONFIGURATION ===
# Remplace par les vraies valeurs
api_id_alice = 123456
api_hash_alice = 'API_HASH_ALICE'
api_id_bob = 654321
api_hash_bob = 'API_HASH_BOB'

session_alice = 'alice_session'
session_bob = 'bob_session'

json_file = 'export/message_1.json'
base_path = 'export'  # dossier racine de l'export Messenger
destination_chat = 'nom_du_groupe_ou_du_canal'  # ID ou @username du groupe/canal cible

# Nom Messenger → compte Telegram
sender_map = {
    'Alice Dupont': {
        'session': session_alice,
        'api_id': api_id_alice,
        'api_hash': api_hash_alice
    },
    'Bob Martin': {
        'session': session_bob,
        'api_id': api_id_bob,
        'api_hash': api_hash_bob
    }
}


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
        client = TelegramClient(conf['session'], conf['api_id'], conf['api_hash'])
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

    messages = load_messages(json_file)

    with TelegramClient('runner', api_id_alice, api_hash_alice) as runner:
        runner.loop.run_until_complete(send_conversation(messages))

