import os
import logging

from dotenv import load_dotenv
load_dotenv()

from telegram.ext import Application, CommandHandler

from .commands import (
    start,
    get_notifications,
    get_month_training,
    get_reserved_training,
    get_balance,
)


TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

async def error_handler(update, context):
    logging.error(f"The error in the update {update}: {context.error}")

if __name__ == "__main__":
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_error_handler(error_handler)

    application.add_handler(get_notifications) #Registration
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("get_balance", get_balance))
    application.add_handler(CommandHandler("get_month_training", get_month_training))
    application.add_handler(CommandHandler("get_reserved_training", get_reserved_training))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

    application.run_polling()
