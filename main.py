import argparse
import json
import shutil
import sys
import tomllib
from datetime import datetime
from pathlib import Path

from loguru import logger
from telethon.sync import TelegramClient

CONFIGURATION_FILE_TEMPLATE = Path(__file__).parent / "configuration-template.toml"
CONFIGURATION_FILE = "config.toml"
FB_MESSENGER_EXPORT_PATH = "export"
FB_MESSENGER_EXPORT_FILENAME = "message_1.json"


def load_configuration_from_file(configuration_file: Path) -> dict:
    """Load configuration from a TOML file.

    If the file does not exist, create it from a template and return an empty dictionary.

    Args:
        configuration_file (Path): Path to the configuration file.

    Returns:
        dict: Configuration data loaded from the file, or an empty dictionary if the file
              does not exist or is empty.

    """
    if not configuration_file.exists():
        logger.warning(f"Configuration file not found: {configuration_file}")
        logger.info("Creating one from template. Please complete the content")
        if not CONFIGURATION_FILE_TEMPLATE.exists():
            logger.error("Template configuration file not found.")
            return {}

        shutil.copy2(CONFIGURATION_FILE_TEMPLATE, configuration_file)
        return {}

    with configuration_file.open("rb") as f:
        return tomllib.load(f)


def load_configuration(configuration_file: Path) -> dict:
    """Load configuration from a file and validate its content.

    Args:
        configuration_file (Path): Path to the configuration file.

    Returns:
        dict: Configuration data loaded from the file.

    """
    configuration = load_configuration_from_file(configuration_file)
    if configuration == {}:
        logger.error(
            f"Configuration file is incomplete. Please fill {configuration_file}",
        )
        sys.exit(1)

    return configuration


# === CHARGEMENT DES MESSAGES JSON ===
def load_messages(
    export_folder: Path,
    messages_filename: str = FB_MESSENGER_EXPORT_FILENAME,
) -> list:
    logger.info(f"Loading messages from {messages_filename}...")
    with (export_folder / messages_filename).open(encoding="utf-8") as f:
        data = json.load(f)

    messages = []
    for idx, msg in enumerate(data.get("messages", [])):
        if msg.get("type") != "Generic":
            continue

        date = datetime.fromtimestamp(msg["timestamp_ms"] / 1000)
        sender = msg.get("sender_name")
        text = msg.get("content", "")
        photos = [export_folder / p["uri"] for p in msg.get("photos", [])]
        videos = [export_folder / v["uri"] for v in msg.get("videos", [])]
        audios = [export_folder / a["uri"] for a in msg.get("audio_files", [])]
        reply_to = msg.get(
            "reply_to",
        )  # valeur personnalisée si elle existe (id/message key)

        messages.append(
            {
                "id": idx,  # ID interne
                "sender": sender,
                "text": text,
                "photos": photos,
                "videos": videos,
                "audios": audios,
                "date": date,
                "reply_to": reply_to,
            },
        )

    return sorted(messages, key=lambda x: x["date"])


def save_messages_to_file(messages: list, output_file: Path) -> None:
    """Save messages to a JSON file.

    Useful for debugging or archiving purposes. Messages will be saved sorted by date.

    Args:
        messages (list): List of messages to save.
        output_file (Path): Path to the output file where messages will be saved.

    """
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(messages, f, indent=4, ensure_ascii=False)
    logger.info(f"Messages saved to {output_file}")


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


def finding_messages_export_folder() -> Path:
    """Crall recursively folders in the current directory and try to find the export folder

    the export folder is something like your_facebook_activity/messages
    """
    current_dir = Path.cwd()
    for item in current_dir.rglob("your_facebook_activity/messages"):
        if item.is_dir():
            logger.info(f"Export folder found: {item}")
            return item

    logger.error(
        "Export folder not found. Please ensure export folder exists in the current directory.",
    )


def main() -> None:
    """Run the migration from Facebook Messenger to Telegram."""
    parser = argparse.ArgumentParser(
        description="Migrate Facebook Messenger conversation to Telegram.",
        epilog="written by Perceval for Bea with 💙",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=CONFIGURATION_FILE,
        help="Path to the configuration file",
    )
    parser.add_argument(
        "--messages",
        "-m",
        type=str,
        default=FB_MESSENGER_EXPORT_PATH,
        help="Path to the folder containing exported fb messages",
    )
    args = parser.parse_args()

    export_folder = finding_messages_export_folder()

    direct_messages = export_folder / "e2ee_cutover"
    group_messages = export_folder / "inbox"
    logger.info(
        f"Direct messages path: {direct_messages}\nGroup messages path: {group_messages}",
    )
    configuration = load_configuration(Path(args.config))
    messages = load_messages(Path(args.messages))
    save_messages_to_file(messages, Path("messages.json"))

    with TelegramClient(
        "runner",
        configuration["user1_api_id"],
        configuration["user1_api_hash"],
    ) as runner:
        runner.loop.run_until_complete(send_conversation(messages))


if __name__ == "__main__":
    main()
