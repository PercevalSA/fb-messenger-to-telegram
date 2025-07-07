# === ENVOI DANS TELEGRAM AVEC LES DEUX COMPTES ===
async def send_conversation(messages: list) -> None:
    # Connexion de chaque compte
    clients = {}
    for sender, conf in sender_map.items():
        client = TelegramClient(conf["name"], conf["api_id"], conf["api_hash"])
        await client.start()
        clients[sender] = client

    # Entité cible (groupe, canal)
    # destination_chat is the other user
    entity = await list(clients.values())[0].get_entity(destination_chat)

    # Mapping messages Messenger → message.id Telegram
    message_map = {}

    for msg in messages:
        sender = msg["sender"]
        client = clients.get(sender)
        if not client:
            logger.error(f"❌ Pas de session définie pour {sender}")
            continue

        reply_to_id = None
        if msg.get("reply_to") is not None:
            reply_to_id = message_map.get(msg["reply_to"])

        final_text = (
            f"🕒 {msg['date'].strftime('%d/%m/%Y %H:%M')}\n{msg['text']}"
            if msg["text"]
            else None
        )

        sent_message = None

        if final_text:
            sent_message = await client.send_message(
                entity,
                final_text,
                reply_to=reply_to_id,
            )

        # Médias
        for photo in msg["photos"]:
            if Path(photo).exists():
                sent_message = await client.send_file(
                    entity,
                    photo,
                    reply_to=reply_to_id,
                )

        for video in msg["videos"]:
            if Path(video).exists():
                sent_message = await client.send_file(
                    entity,
                    video,
                    reply_to=reply_to_id,
                )

        for audio in msg["audios"]:
            if Path(audio).exists():
                sent_message = await client.send_file(
                    entity,
                    audio,
                    voice_note=True,
                    reply_to=reply_to_id,
                )

        # Enregistrer l'ID Telegram du message envoyé
        if sent_message:
            message_map[msg["id"]] = sent_message.id

        await asyncio.sleep(0.5)

    for client in clients.values():
        await client.disconnect()

    logger.info("✅ Importation terminée avec succès.")
