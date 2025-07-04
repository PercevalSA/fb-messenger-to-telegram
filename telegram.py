# https://docs.telethon.dev/en/stable/basic/signing-in.html

import argparse

from telethon.sync import TelegramClient, events

# /!\ attention au ToS, on va mettre un max de slip
# la session est stockée dans un fichier .session portant le nom du client
# si le fichier existe déjà, on n'a pas besoin de se réauthentifier


def parse_arguments():
    parser = argparse.ArgumentParser(description="Telegram Bot Example")
    parser.add_argument("--name", type=str, help="Name of the Telegram client")
    parser.add_argument("--api-id", type=int, help="API ID for Telegram")
    parser.add_argument("--api-hash", type=str, help="API Hash for Telegram")
    return parser.parse_args()


def main():
    args = parse_arguments()
    with TelegramClient(args.name, args.api_id, args.api_hash) as client:
        client.send_message("me", "Hello, myself!")
        print(client.download_profile_photo("me"))

        @client.on(events.NewMessage(pattern="(?i).*Hello"))
        async def handler(event):
            await event.reply("Hey!")

        client.run_until_disconnected()


if __name__ == "__main__":
    main()
