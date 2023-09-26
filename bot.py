from time import sleep
import logging
import os
from queue import Queue
from musescore_downloader_pdf import download_notes_as_pdf
from utils import URLValidator
import telebot
import sentry_sdk

queue = Queue(1)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

SENITRY_SDK_TOKEN = os.getenv("SENITRY_SDK_TOKEN")

sentry_sdk.init(SENITRY_SDK_TOKEN, traces_sample_rate=1.0)

API_TOKEN = os.environ["TOKEN"]
bot = telebot.TeleBot(API_TOKEN)

FALLBACK_LANGUAGE = "en"

QUEUE_ADD_MESSAGE = {"en": "Adding to queue, please wait....", "ru": 'Задача поставлена в очередь, ожидайте...'}

WELCOME_MESSSAGE = {"en": "Hi {message.from_user.first_name}! I can hel you to download PRO notes from MuseScore in high resolution. Send me URL and I will send you PDF of your notes.", "ru": "Привет {message.from_user.first_name}! Я помогу тебе скачивать платные нотки из Musescore в высоком качестве. Отправь мне ссылку на ноты и я отправлю тебе ноты в формате PDF.\n\nРазработана специально для JustPlay"}

NOT_VALID_URL_MESSAGE = {"ru": "К сожалению, ссылка не является допустимой. Проверьте ссылку на действительность.", "en": "Unfortunately, URL is not valid. Check for any error."}

DOWNLOADING_NOTE_MESSAGE = {"ru": "Скачиваю ноты...", "en": "Downloading..."}

UPLOADING_NOTE_MESSAGE = {"ru": "Загружаю ноты в Telegram...", "en": "Uploading PDF to Telegram..."}

ERROR_MESSAGE = {"ru": "Произошла ошибка: {e}", "en": "Unknown error: {e}"}

from multiprocessing.dummy import Pool
pool = Pool(20)


# Thanks god: https://ru.stackoverflow.com/questions/1304696/%D0%9C%D0%BD%D0%BE%D0%B3%D0%BE%D0%BF%D0%BE%D1%82%D0%BE%D1%87%D0%BD%D0%BE%D1%81%D1%82%D1%8C-%D0%B4%D0%BB%D1%8F-%D0%B1%D0%BE%D1%82%D0%B0-%D0%B2-%D1%82%D0%B5%D0%BB%D0%B5%D0%B3%D1%80%D0%B0%D0%BC%D0%B5
def executor(fu):
    def run(*a, **kw):
        pool.apply_async(fu, a, kw, lambda result: ..., lambda error: error)
    return run


def __(message, translate_dict: dict) -> str:
    user_language = message.from_user.language_code
    if user_language in translate_dict:
        return translate_dict[user_language]
    else:
        return translate_dict[FALLBACK_LANGUAGE]


@bot.message_handler(commands=['help', 'start'])
@executor
def welcome_msg(message):
    bot.reply_to(message, __(message, WELCOME_MESSSAGE).format(message=message))


@bot.message_handler(func=lambda message: message.content_type == "text")
@executor
def process_musescore(message):
    if not URLValidator(message.text):
        bot.reply_to(message, __(message, NOT_VALID_URL_MESSAGE))
        return

    queue_msg = bot.reply_to(message, __(message, QUEUE_ADD_MESSAGE))

    sleep(2)

    queue.put("MUSESCORE")

    notification_msg = bot.edit_message_text(__(message, DOWNLOADING_NOTE_MESSAGE), queue_msg.chat.id, queue_msg.message_id)

    try:
        pdf_note = download_notes_as_pdf(message.text)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        bot.edit_message_text(__(message, ERROR_MESSAGE).format(e=e), notification_msg.chat.id, notification_msg.message_id)
        return
    else:
        bot.edit_message_text(__(message, UPLOADING_NOTE_MESSAGE), notification_msg.chat.id, notification_msg.message_id)
        try:
            bot.send_document(notification_msg.chat.id, pdf_note.getvalue(), visible_file_name="musescore.pdf")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            bot.edit_message_text(__(message, ERROR_MESSAGE).format(e=e), notification_msg.chat.id, notification_msg.message_id)
            return
        else:
            bot.delete_message(notification_msg.chat.id, notification_msg.message_id)
    finally:
        queue.get("MUSESCORE")
        queue.task_done()


if __name__ == "__main__":
    bot.infinity_polling()
