from psycopg2.extras import RealDictCursor
from telegram import Update
from telegram.ext import ContextTypes
from .db_connection import get_db_connection


async def get_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Get Balance """
    chat_id = update.effective_chat.id
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            SELECT balance_card, name
            FROM res_partner
            WHERE telegram_chat_id = %s
        """, (chat_id,))

        records = cursor.fetchall()

        if not records:
            await update.message.reply_text("Users not found")
            return

        for record in records:
            balance = record["balance_card"]
            user = record["name"]
            await update.message.reply_text(f"Balance for user {user}: {balance}")

    finally:
        cursor.close()
        conn.close()