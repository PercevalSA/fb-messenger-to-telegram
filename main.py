import argparse
import shutil
import sys
import tomllib
from pathlib import Path

from loguru import logger

from messenger import extract_conversation_from_export_folder

CONFIGURATION_FILE_TEMPLATE = Path(__file__).parent / "configuration-template.toml"
CONFIGURATION_FILE = "config.toml"


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


def parse_cli_arguments() -> argparse.Namespace:
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

    return args


def main() -> None:
    """Run the migration from Facebook Messenger to Telegram."""
    arguments = parse_cli_arguments()
    configuration = load_configuration(Path(arguments.config))
    extract_conversation_from_export_folder(
        arguments.export_folder,
        configuration["user1"]["name"],
    )


if __name__ == "__main__":
    main()
