import logging
import io
import os

from queue import Queue
from time import sleep

import sentry_sdk
import telebot

from extraction import Extraction
from utils import URLValidator

from const import FALLBACK_LANGUAGE
from i18n import *

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

from multiprocessing.dummy import Pool

pool = Pool(20)
extraction = Extraction()

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
        pdf_note = io.BytesIO()
        extraction.extract(message.text, pdf_note)
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
            # raise e
        else:
            bot.delete_message(notification_msg.chat.id, notification_msg.message_id)
    finally:
        queue.get("MUSESCORE")
        queue.task_done()


if __name__ == "__main__":
    bot.infinity_polling()
