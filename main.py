import argparse
import json
import shutil
import sys
import tomllib
from pathlib import Path

from loguru import logger
from telethon.sync import TelegramClient

CONFIGURATION_FILE_TEMPLATE = Path(__file__).parent / "configuration-template.toml"
CONFIGURATION_FILE = "config.toml"
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


"""
FOLDER HIERARCHY:

your_facebook_activity/messages/e2ee_cutover
├── username_<userid_int>
│   ├── audio
│   │   ├── audioclip174505167400033691_1432813888161410.mp4
│   │   └── audioclip17450517150008568_2214026662384824.mp4
│   ├── message_1.json
│   ├── photos
│   │   └── 491010253_1380232929859346_9172913065121913888_n_1380232926526013.jpg
│   └── videos
│       └── 491479191_9637673916315694_3568367626553686238_n_697954715998034.mp4

direct messages are stored in the "e2ee_cutover" folder
while group messages are stored in the "inbox" folder
"""


def user_conversation_folder_path(export_folder: Path, username: str) -> Path:
    """Get the path to the messages folder for a specific user.

    This folder stores the messages exported from Facebook Messenger for the specified user
    in a file named `message_1.json` and other media files (photos, videos, audios) in
    dedicated subfolders.

    Args:
        export_folder (Path): Path to the export folder.
        username (str): Username of the Facebook account.

    Returns:
        Path: Path to the messages folder for the specified user.

    """
    direct_conversations_folder = (
        export_folder / "your_facebook_activity/messages/e2ee_cutover"
    )

    # find folder starting with the username in e2ee_cutover
    messages_folder = next(
        (
            folder
            for folder in direct_conversations_folder.iterdir()
            if folder.is_dir() and folder.name.startswith(username)
        ),
        None,
    )

    if not messages_folder:
        logger.error(f"Messages folder not found: {messages_folder}")
        sys.exit(1)

    logger.info(f"Messages folder found: {messages_folder}")
    return messages_folder


def load_messages(
    export_folder: Path,
    messages_filename: str = FB_MESSENGER_EXPORT_FILENAME,
) -> list:
    logger.info(f"Loading messages from {messages_filename}...")
    with (export_folder / messages_filename).open("r", encoding="utf-8") as f:
        data = json.load(f)

    # check direct conv
    if len(data["participants"]) != 2:
        logger.error(
            "This script is designed to migrate direct conversations only. "
            "Please ensure the conversation is a direct one.",
        )
        sys.exit(1)

    messages = []
    for msg in data.get("messages", []):
        date = msg["timestamp_ms"]  # datetime.fromtimestamp(msg["timestamp_ms"] / 1000)
        sender = msg.get("sender_name")
        text = msg.get("content", "")
        photos = [p["uri"] for p in msg.get("photos", [])]
        videos = [v["uri"] for v in msg.get("videos", [])]
        audios = [a["uri"] for a in msg.get("audio_files", [])]
        reply_to = msg.get(
            "reply_to",
        )  # valeur personnalisée si elle existe (id/message key)

        messages.append(
            {
                "sender": sender,
                "text": text,
                "photos": photos,
                "videos": videos,
                "audios": audios,
                "date": date,
                "reply_to": reply_to,
            },
        )
    logger.debug(f"Loaded {len(messages)} messages from {messages_filename}")

    return messages


def save_messages_to_file(messages: list[dict], output_file: Path) -> None:
    """Save messages to a JSON file.

    Useful for debugging or archiving purposes. Messages will be saved sorted by date.

    Args:
        messages (list[dict]): List of messages to save.
        output_file (Path): Path to the output file where messages will be saved.

    """
    logger.debug(messages)
    with output_file.open("w", encoding="utf-8") as f:
        # ensure_ascii=True to keep Unicode characters as-is (like emojis)
        json.dump(messages, f, indent=4, ensure_ascii=True)
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


def find_facebook_export_folder() -> Path | None:
    """Try to find the facebook export folder in the current directory.

    The export folder contains a subfolder named 'your_facebook_activity' which contains
    the exported messages and media files.

    Returns:
        Path: Path to the export folder if found, otherwise logs an error and exits.

    """
    current_dir = Path.cwd()
    for item in current_dir.rglob("your_facebook_activity"):
        if item.is_dir():
            logger.info(f"Export folder found: {item.parent}")
            return item.parent

    logger.error(
        "Export folder not found. ",
        "Please ensure export folder exists in the current directory.",
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
        "--export-folder",
        "-f",
        "--data",
        "-d",
        type=str,
        help="Path to the folder containing exported facebook data (including messages)",
    )
    parser.add_argument(
        "--username",
        "-u",
        type=str,
        default="morganebnn",
        help="Username of the Facebook account for finding messages: "
        "surname and name without accents sticked together",
    )
    parser.add_argument(
        "--telegram-chat",
        "-t",
        "--chat",
        "-c",
        type=str,
        help="Telegram chat to send messages to. "
        "Can be a username, channel ID, or group ID. "
        "Useful for testing in a dedicated chat.",
    )
    args = parser.parse_args()

    configuration = load_configuration(Path(args.config))

    # parse export
    if not args.export_folder:
        logger.info(
            "Export folder not specified. Trying to find it in the current directory.",
        )
        export_folder = find_facebook_export_folder()
        if not export_folder:
            logger.error(
                "Export folder not found. Please ensure export folder exists in the current directory.",
            )
            sys.exit(1)
    else:
        export_folder = Path(args.export_folder).resolve()
        if not export_folder.exists():
            logger.error(f"Export folder does not exist: {export_folder}")
            sys.exit(1)

    user_conv_path = user_conversation_folder_path(export_folder, args.username)
    messages = load_messages(user_conv_path)

    save_messages_to_file(messages, Path.cwd() / "messages.json")

    sys.exit(0)
    with TelegramClient(
        "runner",
        configuration["user1_api_id"],
        configuration["user1_api_hash"],
    ) as runner:
        runner.loop.run_until_complete(send_conversation(messages))


if __name__ == "__main__":
    main()
