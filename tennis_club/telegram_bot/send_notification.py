import requests
import os
import logging

from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


def send_telegram_notification(customer, message):
    """ Func for send Notifications to Telegram"""
    if customer.telegram_chat_id!=0 and customer.is_permission_to_notify:
        chat_id = customer.telegram_chat_id

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        try:
            with requests.Session() as session:
                session.post(url, json=payload, timeout=5)
            logging.info(f"Telegram notification sent to {chat_id}")
        except Exception as e:
            logging.error(f"Telegram notification failed: {e}")
    else:
        return