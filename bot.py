import logging
import os
from musescore_downloader_pdf import async_download_notes_as_pdf
from utils import URLValidator
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

TOKEN = os.environ["TOKEN"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"Привет {user.mention_html()}! Я помогу тебе скачивать платные нотки из Musescore в высоком качестве. Отправь мне ссылку на ноты и я отправлю тебе ноты в формате PDF.\n\nРазработана специально для JustPlay",
        reply_markup=ForceReply(selective=True),
    )


async def process_musescore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not URLValidator(update.message.text):
        await update.message.reply_text("К сожалению, ссылка не является допустимой. Проверьте ссылку на действительность.")
        return

    notification_msg = await update.message.reply_text("Скачиваю ноты...")

    try:
        pdf_note = await async_download_notes_as_pdf(update.message.text)
    except Exception as e:
        await notification_msg.edit_text(f"Произошла ошибка: {e}")
        return
    else:
        await notification_msg.edit_text("Ноты успешно скачаны. Загружаю ноты в Telegram....")
        try:
            await update.message.reply_document(
                pdf_note.getvalue(),
                filename="musescore_notes.pdf",
            )
        except Exception as e:
            await notification_msg.edit_text(f"Произошла ошибка при загрузке нот: {e}")
            return
        else:
            await notification_msg.delete()


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_musescore))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
