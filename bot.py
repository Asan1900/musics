from ast import parse
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from vkapi import VkAPI, VkAPIError, VkAuthError
import os
from config import TELEGRAM_BOT_TOKEN

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {"Accept-Encoding": "identity"}
output_dir = os.path.join(os.getcwd(), "output")

if not os.path.exists(output_dir):
    os.mkdir(output_dir)

def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    update.message.reply_text(f"Hello! I am your VK Audio Bot. Use /auth to authenticate, where you tap your account (number of phone), then password of your account using this logic /auth (number) (password) and /download to get audio tracks.")

def authenticate(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    auth_input = update.message.text.split(" ", 2)
    if len(auth_input) == 3:
        username, password = auth_input[1], auth_input[2]
        try:
            vk = VkAPI(login=username, password=password)
            context.user_data['vk_api'] = vk
            update.message.reply_text("Authentication succeeded!")
        except (VkAuthError, VkAPIError) as e:
            update.message.reply_text(f"Authentication failed: {str(e)}")
    else:
        update.message.reply_text("Invalid input. Please use the format: /auth YourUsername YourPassword")

def process_auth_input(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Unexpected input. Please use /auth to initiate the authentication process.")

def songs_list(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    vk_api = context.user_data.get('vk_api')
    if vk_api:
        try:
            dump = False
            dump_filename = ""

            if len(context.args) == 2 and context.args[0] == "dump":
                dump = True
                dump_filename = context.args[1]

            message_text = f"Logged as {vk_api.user_id}\n"
            headers = HEADERS
            headers["User-Agent"] = vk_api.user_agent
            resp = vk_api.request("catalog.getAudio", {"need_blocks": 1})
            sections = resp["catalog"]["sections"]
            default_section_id = resp["catalog"]["default_section"]
            audios = resp["audios"]
            
            # Accumulate information about the received audios
            message_text += f"Received {len(audios)} audios\n"
            
            music_section = sections[0]
            for s in sections:
                if s["id"] == default_section_id:
                    music_section = s
                    break
            
            message_text += f'Default section: "{music_section["title"]}": {music_section["id"]}: {music_section["url"]}\n'
            
            next_start = music_section.get("next_from")
            while next_start:
                resp = vk_api.request("catalog.getSection", {"start_from": next_start, "section_id": music_section["id"]})
                next_start = resp["section"].get("next_from")
                received_audios = resp["audios"]
                audios += received_audios
                
                # Accumulate information about the received audios
                message_text += f"Received {len(received_audios)} audios\n"
            
            if dump:
                dump_file = open(dump_filename, "w")
            else:
                dump_file = None
            for i, track in enumerate(audios):
                message_text += f"{i + 1}. {track['artist']} — {track['title']}\n"

            if dump:
                message_text += f"Dumped {len(audios)} tracks\n"
                dump_file.close()
            else:
                message_text += "Tracks downloaded and processed. Check your channel for details."
                
            # Include instructions for downloading
            message_text += "\nTo download specific songs, use the command /download followed by the numbers of the songs you want to download."

            # Split the message into chunks of 4096 characters
            message_chunks = [message_text[i:i + 4096] for i in range(0, len(message_text), 4096)]

            # Send each chunk as a separate message
            for chunk in message_chunks:
                update.message.reply_text(chunk)

        except VkAPIError as e:
            update.message.reply_text(f"Failed to download songs: {str(e)}")
    else:
        update.message.reply_text("Authentication required. Use /auth to log in to VK.")


def download_songs(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    vk_api = context.user_data.get('vk_api')
    if vk_api:
        try:
            dump = False
            dump_filename = ""

            if not context.args:
                update.message.reply_text("Select the songs you want to download using /download [song numbers separated by space]")
                return

            if len(context.args) == 1 and context.args[0] == "all":
                dump = True
                dump_filename = "all_songs.txt"

            headers = HEADERS
            headers["User-Agent"] = vk_api.user_agent
            resp = vk_api.request("catalog.getAudio", {"need_blocks": 1})
            sections = resp["catalog"]["sections"]
            default_section_id = resp["catalog"]["default_section"]
            audios = resp["audios"]

            music_section = sections[0]
            for s in sections:
                if s["id"] == default_section_id:
                    music_section = s
                    break

            next_start = music_section.get("next_from")
            while next_start:
                resp = vk_api.request("catalog.getSection", {"start_from": next_start, "section_id": music_section["id"]})
                next_start = resp["section"].get("next_from")
                received_audios = resp["audios"]
                audios += received_audios

            if not dump:
                update.message.reply_text("Select the songs you want to download using /download [song numbers separated by space]")
                return

            download_list = [int(num) - 1 for num in context.args]
            download_list = list(set(download_list))  # Remove duplicates
            download_list = [index for index in download_list if 0 <= index < len(audios)]  # Remove invalid indices

            if not download_list:
                update.message.reply_text("Invalid song numbers. Please select valid song numbers to download.")
                return

            for index in download_list:
                track = audios[index]
                artist = track["artist"]
                title = track["title"]
                update.message.reply_text(f"Processing track: {artist} - {title}")
                # ... (download and process the track)

            update.message.reply_text("Songs downloaded and processed. Check your channel for details.")

        except VkAPIError as e:
            update.message.reply_text(f"Failed to download songs: {str(e)}")
    else:
        update.message.reply_text("Authentication required. Use /auth to log in to VK.")

def main() -> None:
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    # Command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("auth", authenticate))
    dp.add_handler(CommandHandler("list", songs_list))
    dp.add_handler(CommandHandler("download", download_songs))

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, process_auth_input))

    updater.start_polling()

    updater.idle()

if __name__ == '__main__':
    main()