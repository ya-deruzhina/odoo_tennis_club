import datetime
import pytz

from telegram import Update
from telegram.ext import ContextTypes
from psycopg2.extras import RealDictCursor

from .db_connection import get_db_connection



def get_month_start_end():
    """" Get month Start and End """
    today = datetime.date.today()
    start_month = today.replace(day=1)
    if today.month == 12:
        end_month = today.replace(day=31)
    else:
        end_month = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)
    return start_month, end_month

async def get_month_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Get month training """
    chat_id = update.effective_chat.id
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    start_month, end_month = get_month_start_end()

    try:
        cursor.execute("""
            SELECT id, name, tz
            FROM res_partner
            WHERE telegram_chat_id = %s
        """, (chat_id,))
        users = cursor.fetchall()

        if not users:
            await update.message.reply_text("Status - FAILED\nUser not found")
            return

        status_dict = {
            "new": "New",
            "waiting_approve_reserve": "Waiting for Approval Reserve",
            "reserved": "Reserved",
            "done": "Done",
            "waiting_approve_cancel": "Waiting for Approval Cancel",
            "cancelled": "Cancelled",
            "unavailable": "Unavailable",
        }

        messages = []

        for user in users:
            user_id = user["id"]
            user_tz = user["tz"] if user["tz"] else "UTC"
            tz = pytz.timezone(user_tz)

            cursor.execute("""
                SELECT 
                    t.id AS training_id,
                    t.time_begin,
                    t.time_finish,
                    t.status,
                    t.count_customers,
                    t.price_total_from_person,
                    c_center.name AS center_name,
                    c_court.name AS court_name,
                    prod.type_training AS product_name,
                    instr.name AS instructor_name
                FROM training_model t
                JOIN training_partner_rel rel 
                       ON t.id = rel.training_id
                LEFT JOIN centers_model c_center 
                       ON t.center_id = c_center.id
                LEFT JOIN centers_model c_court 
                       ON t.tennis_court_id = c_court.id
                LEFT JOIN product_product prod 
                       ON t.product_training_id = prod.id
                LEFT JOIN hr_employee instr 
                       ON t.instructor_id = instr.id
                WHERE rel.customer_id = %s
                  AND t.time_begin::date BETWEEN %s AND %s
                ORDER BY t.time_begin;
            """, (user_id, start_month, end_month))

            records = cursor.fetchall()

            if not records:
                messages.append(f"Status - FAILED\nNo trainings found for user {user['name']}")
                continue

            message = f"Trainings for {user['name']} this month:\n"

            for r in records:
                time_begin_utc = r["time_begin"].replace(tzinfo=pytz.UTC)
                time_finish_utc = r["time_finish"].replace(tzinfo=pytz.UTC)
                customer_time_begin = time_begin_utc.astimezone(tz)
                customer_time_finish = time_finish_utc.astimezone(tz)

                cursor.execute("""
                    SELECT rp.name
                    FROM res_partner rp
                    JOIN training_partner_rel rel ON rp.id = rel.customer_id
                    WHERE rel.training_id = %s
                """, (r["training_id"],))
                customers = cursor.fetchall()
                customer_names = ", ".join([c["name"] for c in customers])

                message += (
                    f"\n{customer_time_begin.strftime('%Y-%m-%d %H:%M')} - {customer_time_finish.strftime('%H:%M')}\n"
                    f"Customers: {customer_names}\n"
                    f"Center: {r['center_name']}\n"
                    f"Court: {r['court_name']}\n"
                    f"Training: {r['product_name']}\n"
                    f"Instructor: {r['instructor_name']}\n"
                    f"Status: {status_dict.get(r['status'], r['status'])}\n"
                    f"Price from person: {r['price_total_from_person']}\n"
                )

            messages.append(message)

        for msg in messages:
            await update.message.reply_text(msg)

    finally:
        cursor.close()
        conn.close()
