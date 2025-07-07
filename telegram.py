# https://docs.telethon.dev/en/stable/basic/signing-in.html

import argparse

from telethon import TelegramClient

# telethon session is stored in a file named after the client
# if the file already exists, we don't need to re-authenticate
# the session file is named <client_name>.session
# as we will send messages on 2 users' behalf, we will need to create 2 clients


def parse_arguments():
    parser = argparse.ArgumentParser(description="Telegram Bot Example")
    parser.add_argument("--name", type=str, help="Name of the Telegram client")
    parser.add_argument("--api-id", type=int, help="API ID for Telegram")
    parser.add_argument("--api-hash", type=str, help="API Hash for Telegram")
    return parser.parse_args()


async def tg():
    # Getting information about yourself
    me = await client.get_me()

    # "me" is a user object. You can pretty-print
    # any Telegram object with the "stringify" method:
    print(me.stringify())

    # When you print something, you see a representation of it.
    # You can access all attributes of Telegram objects with
    # the dot operator. For example, to get the username:
    username = me.username
    print(username)
    print(me.phone)

    # You can print all the dialogs/conversations that you are part of:
    # async for dialog in client.iter_dialogs():
    #     print(dialog.name, "has ID", dialog.id)

    # You can send messages to yourself...
    await client.send_message("me", "Hello, myself!")
    # ...to your contacts
    await client.send_message("+33600000", "Hello, friend!")
    # ...or even to any username
    await client.send_message("username", "Testing Telethon!")

    # You can, of course, use markdown in your messages:
    message = await client.send_message(
        "me",
        "This message has **bold**, `code`, __italics__ and "
        "a [nice website](https://example.com)!",
        link_preview=False,
    )

    # Sending a message returns the sent message object, which you can use
    print(message.raw_text)

    # You can reply to messages directly if you have a message object
    await message.reply("Cool!")

    # Or send files, songs, documents, albums...
    await client.send_file("me", "image.jpg")

    # You can print the message history of any chat:
    async for message in client.iter_messages("me"):
        print(message.id, message.text)

        # You can download media from messages, too!
        # The method will return the path where the file was saved.
        if message.photo:
            path = await message.download_media()
            print("File saved to", path)  # printed after download is done


if __name__ == "__main__":
    args = parse_arguments()

    with TelegramClient(args.name, args.api_id, args.api_hash) as client:
        client.loop.run_until_complete(tg())
