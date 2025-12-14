import pytz
from datetime import timedelta, datetime

from odoo import models, api
from odoo.fields import Datetime

from ..telegram_bot.send_notification import send_telegram_notification

from dotenv import load_dotenv
load_dotenv()


class TrainingGenerator(models.Model):
    _inherit = "training.model"
    _description = "Logic for generating training slots"

    @api.model
    def cron_notify_upcoming_trainings(self):
            """ Cron Task to Send Notifications to Telegram"""
            now = datetime.now() + timedelta(hours=1)
            one_hour_from_now = now + timedelta(hours=1)

            training_ids = self.search([
                ("status", "in", ["reserved", "waiting_approve_cancel"]),
                ("time_begin", ">=", now),
                ("time_begin", "<=", one_hour_from_now)
            ])

            for rec in training_ids:
                for customer in rec.customer_ids.sudo():
                    if customer.telegram_chat_id and customer.is_permission_to_notify:
                        user_tz = customer.user_id.tz or "UTC"
                        tz = pytz.timezone(user_tz)

                        customer_time_begin = Datetime.context_timestamp(self, rec.time_begin).astimezone(tz)
                        customer_time_finish = Datetime.context_timestamp(self, rec.time_finish).astimezone(tz)
                        customers_names = ", ".join([c["name"] for c in rec.customer_ids])

                        message = (f"Your training '{rec.name}' will start in an hour"
                                   f"\n{customer_time_begin.strftime('%Y-%m-%d %H:%M')}-{customer_time_finish.strftime('%H:%M')}\n"
                                   f"\nCustomer: {customers_names}"
                                   f"\nCenter {rec.center_id.name}"
                                   f"\nCourt {rec.tennis_court_id.name}"
                                   f"\nInstructor {rec.instructor_id.name}"
                                   f"\n")
                        send_telegram_notification(customer, message)