import logging
import os
from musescore_downloader_pdf import download_notes_as_pdf
from utils import URLValidator
import telebot

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

API_TOKEN = os.environ["TOKEN"]
bot = telebot.TeleBot(API_TOKEN)


@bot.message_handler(commands=['help', 'start'])
def welcome_msg(message):
    bot.reply_to(message, f"Привет {message.from_user.first_name}! Я помогу тебе скачивать платные нотки из Musescore в высоком качестве. Отправь мне ссылку на ноты и я отправлю тебе ноты в формате PDF.\n\nРазработана специально для JustPlay")


@bot.message_handler(func=lambda message: message.content_type == "text")
def process_musescore(message):
    if not URLValidator(message.text):
        bot.reply_to(message, "К сожалению, ссылка не является допустимой. Проверьте ссылку на действительность.")
        return

    notification_msg = bot.reply_to(message, "Скачиваю ноты...")

    try:
        pdf_note = download_notes_as_pdf(message.text)
    except Exception as e:
        bot.edit_message_text(f"Произошла ошибка: {e}", notification_msg.chat.id, notification_msg.message_id)
        return
    else:
        bot.edit_message_text("Загружаю ноты в Telegram...", notification_msg.chat.id, notification_msg.message_id)
        try:
            bot.send_document(notification_msg.chat.id, pdf_note.getvalue(), visible_file_name="musescore.pdf")
        except Exception as e:
            bot.edit_message_text(f"Произошла ошибка при загрузке нот: {e}", notification_msg.chat.id, notification_msg.message_id)
            return
        else:
            bot.delete_message(notification_msg.chat.id, notification_msg.message_id)


if __name__ == "__main__":
    bot.infinity_polling()
