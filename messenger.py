import json
import sys
from pathlib import Path

from loguru import logger

"""FOLDER HIERARCHY:

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
FB_MESSENGER_EXPORT_FILENAME = "message_1.json"
FB_CONVERSATION_FOLDER = "your_facebook_activity/messages/e2ee_cutover"


def user_conversation_folder_path(export_folder: Path, username: str) -> Path:
    """Get the path to the conversation folder for a specific user.

    This folder stores the conversation exported from Facebook Messenger
    for the specified user in a file named `message_1.json`
    and other media files (photos, videos, audios) in dedicated subfolders.

    Args:
        export_folder (Path): Path to the export folder.
        username (str): Username of the Facebook account.

    Returns:
        Path: Path to the conversation folder for the specified user.

    """
    direct_conversations_folder = export_folder / FB_CONVERSATION_FOLDER

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


def load_conversation_from_export(
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


def save_conversation_to_file(messages: list[dict], output_file: Path) -> None:
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


def extract_conversation_from_export_folder(
    export_folder: Path,
    username: str,
) -> list[dict]:
    """Extract conversation from the Facebook Messenger export folder.

    This function loads the messages from the specified user's conversation folder
    within the Facebook Messenger export folder and saves them to a JSON file.
    It also handles the case where the export folder is not specified,
    attempting to find it in the current directory.
    exit with error if the export folder does not exist.

    Args:
        export_folder (Path): Path to the folder containing exported Facebook data.
        username (str): Username of the recipient whose conversation is to be extracted.

    Returns:
        list[dict]: List of messages extracted from the conversation.

    """
    # parse export
    if not export_folder:
        logger.info(
            "Export folder not specified. Trying to find it in the current directory.",
        )
        export_folder = find_facebook_export_folder()
        if not export_folder:
            logger.error(
                "Export folder not found. "
                "Please ensure export folder exists in the current directory.",
            )
            sys.exit(1)
    else:
        export_folder = Path(export_folder).resolve()
        if not export_folder.exists():
            logger.error(f"Export folder does not exist: {export_folder}")
            sys.exit(1)

    user_conv_path = user_conversation_folder_path(export_folder, username)
    messages = load_conversation_from_export(user_conv_path)

    save_conversation_to_file(messages, Path.cwd() / "messages.json")

    return messages
