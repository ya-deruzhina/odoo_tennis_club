import json
import pytz
import random

from datetime import timedelta, time, datetime
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.fields import Datetime

from ..telegram_bot.send_notification import send_telegram_notification
from dotenv import load_dotenv
load_dotenv()

STATUSES_DICT = {
                "new": "New",
                "waiting_approve_reserve": "Waiting for Approval Reserve",
                "reserved": "Reserved",
                "done": "Done",
                "waiting_approve_cancel": "Waiting for Approval Cancel",
                "cancelled": "Cancelled",
                "unavailable": "Unavailable",
            }

ALLOWED_TRANSITIONS = {
            "new": ["waiting_approve_reserve"],
            "waiting_approve_reserve": ["reserved", "cancelled"],
            "reserved": ["done", "waiting_approve_cancel"],
            "done": ["waiting_approve_cancel"],
            "waiting_approve_cancel": ["cancelled", "done"],
            "cancelled": [],
            "unavailable": [],
        }


class TrainingModel(models.Model):
    _name = "training.model"
    _description = "Training"

    name = fields.Char(string="Name")

    status = fields.Selection(
        selection=[("new", "New"),
                   ("waiting_approve_reserve", "Waiting for Approval Reserve"),
                   ("reserved", "Reserved"),
                   ("done", "Done"),
                   ("waiting_approve_cancel", "Waiting for Approval Cancel"),
                   ("cancelled", "Cancelled"),
                   ("unavailable", "Unavailable")],
        string="Training Status",
        default="new"
    )

    color = fields.Integer(compute="_compute_color", store=True)

    center_id = fields.Many2one(
        comodel_name="centers.model",
        string="Center",
        default=lambda self: self._get_default_center_id(),
        domain=[("is_center", "=", True)],
        store=True,
    )

    tennis_court_id = fields.Many2one(
        comodel_name="centers.model",
        string="Tennis Court",
        required=True,
        domain="[('parent_center_id','=',center_id)]"
    )

    selected_court_ids = fields.Many2many(
        comodel_name="centers.model",
        relation="training_model_selected_courts_rel",
        column1="training_id",
        column2="court_id",
        string="Selected Courts",
    )

    product_training_id = fields.Many2one(
        comodel_name="product.product",
        string="Type Training",
        required=True,
    )

    price_training_total_per_hour = fields.Float(
        string="Price Total per Hour",
        compute="_compute_price_training_total_per_hour",
        store=True,
    )
    fix_price_training_total_per_hour = fields.Float(
        string="Price Fixed Training Total per Hour",
        readonly=True)

    instructor_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Instructor",
        required=True,
        default=lambda self: self._get_active_employee(),
    )

    is_user_is_instructor = fields.Boolean(
        string="User is Instructor",
        compute="_compute_is_user_is_instructor",
        default=lambda
            self: not self._get_active_employee().is_not_instructor if self._get_active_employee() else False,
    )

    payment_to_instructor = fields.Float(
        string="Payment to Instructor",
        compute="_compute_payment_to_instructor",
        store=True,
    )
    fix_payment_to_instructor = fields.Float(
        string="Fix Payment to Instructor",
        store=True,
        readonly=True
    )

    customer_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="training_partner_rel",
        column1="training_id",
        column2="customer_id",
        string="Customers",
    )

    count_customers = fields.Integer(
        string="Count Customers",
        compute="_compute_count_customers",
        store="True"
    )

    fix_count_customers = fields.Float(string="Count Customers Fixed", readonly=True)

    used_customer_ids = fields.Many2many(
        "res.partner",
        compute="_compute_used_customer_ids",
        string="Used Customers",
        store=False
    )

    price_per_hour_from_person = fields.Float(
        string="Price per Hour (from person)",
        compute="_compute_price_per_hour_from_person",
        store=True,
    )

    price_total_from_person = fields.Float(
        string="Price Total (from person)",
        compute="_compute_price_total_from_person",
        store=True,
    )

    time_begin = fields.Datetime(
        string="Training From",
    )

    time_finish = fields.Datetime(
        string="Training To"
    )

    duration_hours = fields.Float(
        string="Duration (hours)",
        compute="_compute_duration_hours",
        store=True,
    )

    fix_total_money = fields.Float(
        string="Fix Total Money",
        store=True,
        readonly=True
    )

    fixed_data = fields.Char(string="Fixed Data", readonly=True, default="")

    repeat_until_date = fields.Date(
        string="Repeat Until Date",
        required=False,
    )
    how_often_repeat = fields.Selection(
        selection=[("one_time", "One Time"),
                   ("every_day", "Every Day"),
                   ("every_week", "Every Week"),
                   ("every_month", "Every Month")],
        string="How Often Repeat",
        default="one_time"
    )


    # Main
    def unlink(self):
        for rec in self:
            if rec.status not in ["new", "unavailable"]:
                raise ValidationError(
                    "You can not delete training "
                    "\nFor Delete chose status 'Waiting for Approval Cancel', and then 'Cancelled'"
                )

        result = super(TrainingModel, self).unlink()
        return result


    def write(self, vals):
        if self.env.context.get("skip_recurrence") or self.env.context.get("skip_training_write"):
            return super().write(vals)

        old_statuses = {rec.id: rec.status for rec in self}
        change_status = False

        if "status" not in vals:
            if any(rec.status not in ["unavailable", "cancelled", "done"] for rec in self):
                vals = vals.copy()
                vals["status"] = "waiting_approve_reserve"
                change_status = True

        result = super().write(vals)

        customer_movements = {}

        for rec in self:
            old_status = old_statuses[rec.id]
            new_status = rec.status
            movement = rec.duration_hours * rec.price_total_from_person

            user_instructor_id = self.env["hr.employee"].search([("user_id", "=", self.env.user.id)], limit=1).id
            if old_status == "new" and rec.instructor_id.id != user_instructor_id and not self.env.context.get(
                    "skip_instructor_write"):
                rec.with_context(skip_instructor_write=True).write({"instructor_id": user_instructor_id})


            if old_status == "new" and rec.repeat_until_date and rec.how_often_repeat != "one_time":
                rec.sudo().with_context(skip_recurrence=True).write({"status": "waiting_approve_reserve"})
                self._create_recurrences_training(rec)

            if old_status != new_status:
                for customer in rec.customer_ids.sudo():
                    if customer.id not in customer_movements:
                        customer_movements[customer.id] = {"balance_card": 0, "frozen_balance_card": 0}

                    if old_status == "new" and new_status == "waiting_approve_reserve":
                        customer_movements[customer.id]["balance_card"] -= movement
                        customer_movements[customer.id]["frozen_balance_card"] += movement
                    elif old_status in ["waiting_approve_cancel",
                                        "waiting_approve_reserve"] and new_status == "cancelled":
                        customer_movements[customer.id]["balance_card"] += movement
                        customer_movements[customer.id]["frozen_balance_card"] -= movement
                    elif old_status == "done" and new_status == "waiting_approve_cancel":
                        customer_movements[customer.id]["frozen_balance_card"] += movement
                    elif old_status in ["reserved", "waiting_approve_cancel"] and new_status == "done":
                        customer_movements[customer.id]["frozen_balance_card"] -= movement

                    if customer.telegram_chat_id and customer.is_permission_to_notify and new_status in ["reserved",
                                                                                                         "done",
                                                                                                         "cancelled"]:
                        tz = pytz.timezone(customer.tz or "UTC")
                        customer_time_begin = Datetime.context_timestamp(self, rec.time_begin).astimezone(tz)
                        customer_time_finish = Datetime.context_timestamp(self, rec.time_finish).astimezone(tz)
                        customers_names = ", ".join([c.name for c in rec.customer_ids])
                        message = (
                            f"Your training status '{rec.product_training_id.type_training}' changed"
                            f"\n{STATUSES_DICT.get(old_status, old_status)} -> {STATUSES_DICT.get(new_status, new_status)}"
                            f"\n{customer_time_begin.strftime('%Y-%m-%d %H:%M')}-{customer_time_finish.strftime('%H:%M')}"
                            f"\n\nCustomers: {customers_names}"
                            f"\n\nCenter: {rec.center_id.name}"
                            f"\nCourt: {rec.tennis_court_id.name}"
                            f"\nInstructor: {rec.instructor_id.name}\n"
                        )
                        send_telegram_notification(customer, message)

                allowed = ALLOWED_TRANSITIONS.get(old_status, [])
                if new_status not in allowed and not change_status:
                    raise ValidationError(f"Invalid status transition {old_status} -> {new_status}")

            if new_status in ["unavailable", "new", "cancelled"]:
                rec.sudo().with_context(skip_recurrence=True).write({
                    "fixed_data": False,
                    "fix_price_training_total_per_hour": False,
                    "fix_count_customers": False,
                    "fix_payment_to_instructor": False,
                    "fix_total_money": False,
                })
            elif new_status not in ["unavailable", "new", "cancelled"] and not rec.fixed_data:
                rec._update_fixed_data()

        for customer_id, changes in customer_movements.items():
            customer = self.env["res.partner"].sudo().browse(customer_id)
            customer.sudo().with_context(skip_training_write=True).write({
                "balance_card": customer.balance_card + changes["balance_card"],
                "frozen_balance_card": customer.frozen_balance_card + changes["frozen_balance_card"],
            })

        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for rec, vals in zip(records, vals_list):
            if rec.status!="unavailable" and rec.name !="free slot":
                rec._update_fixed_data()
                rec.status = "waiting_approve_reserve"
        return records

    def _update_fixed_data(self):
        """ Update fixed data when creating or writing record """
        for rec in self:
            vals = {
                "fixed_data": (
                    f"Name {rec.name}\n"
                    f"Center {rec.center_id.name}\n"
                    f"Tennis court {rec.tennis_court_id.name}\n"
                    f"Training {rec.product_training_id.name}\n"
                    f"Instructor {rec.instructor_id.name}\n"
                    f"Customers {', '.join(rec.customer_ids.mapped('name'))}\n"
                    f"Duration {rec.duration_hours} hours from {rec.time_begin} to {rec.time_finish}"
                ),
                "fix_price_training_total_per_hour": rec.product_training_id.list_price,
                "fix_count_customers": rec.count_customers,
                "fix_payment_to_instructor": rec.duration_hours * rec.payment_to_instructor,
                "fix_total_money":rec.duration_hours * rec.price_training_total_per_hour,
            }
            super(TrainingModel, rec).with_context(skip_recurrence=True).write(vals)

    @api.model
    def _get_default_center_id(self):
        """ Get Default Center """
        employee = self.env["hr.employee"].search([("user_id", "=", self.env.user.id)], limit=1)
        return employee.working_center_id if employee else False

    @api.model
    def _get_active_employee(self):
        """ Get Active Employee """
        return self.env["hr.employee"].search([("user_id", "=", self.env.user.id)], limit=1)

    @api.model
    def count_recurrences(self, end_date, recurrence, start_date=None):
        """ Count Recurrences when create record with Recurrence """
        today = start_date.date() if start_date else datetime.today().date()

        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        if end_date < today:
            return {"count": 0, "dates": []}

        dates = []
        current = today

        if recurrence == "every_day":
            delta = timedelta(days=1)
            while current <= end_date:
                dates.append(current)
                current += delta

        elif recurrence == "every_week":
            delta = timedelta(weeks=1)
            while current <= end_date:
                dates.append(current)
                current += delta

        elif recurrence == "every_month":
            while current <= end_date:
                dates.append(current)
                current += relativedelta(months=1)
        else:
            raise ValueError("Unknown recurrence type")

        return {"count": len(dates), "dates": dates}

    def _create_free_slots_from_record(self, rec):
        """ Create Free Slots in Working Hours of Center for Courts """
        free_slots = []
        cur = rec.time_begin
        end = rec.time_finish

        while cur < end:
            slot_end = cur + timedelta(hours=1)
            existing_ids = self.env["training.model"].sudo().search_count([
                ("name","=", "free slot"),
                ("center_id", "=", rec.center_id.id),
                ("tennis_court_id", "=", rec.tennis_court_id.id),
                ("product_training_id","=", 1),
                ("instructor_id", "=", 1),
                ("time_begin", "<", cur),
                ("time_finish", ">", slot_end),
                ("status","=", "new"),
            ])
            if existing_ids:
                continue

            free_slots.append({
                "name": "free slot",
                "center_id": rec.center_id.id,
                "tennis_court_id": rec.tennis_court_id.id,
                "product_training_id": 1,
                "instructor_id": 1,
                "time_begin": cur,
                "time_finish": slot_end,
                "status": "new",
            })

            cur = slot_end

        if free_slots:
            self.env["training.model"].sudo().create(free_slots)

    def _create_recurrences_training(self, rec):
        """ Create Recurrences Training """
        recurrence_dates = self.count_recurrences(
            rec.repeat_until_date, rec.how_often_repeat, start_date=rec.time_begin
        )["dates"]
        to_create = []
        for dt in recurrence_dates:
            if dt == rec.time_begin.date():
                continue
            duration = rec.time_finish - rec.time_begin
            to_create.append({
                "name": rec.name,
                "center_id": rec.center_id.id,
                "tennis_court_id": rec.tennis_court_id.id,
                "product_training_id": rec.product_training_id.id,
                "instructor_id": rec.instructor_id.id,
                "customer_ids": [(6, 0, rec.customer_ids.ids)],
                "time_begin": datetime.combine(dt, rec.time_begin.time()),
                "time_finish": datetime.combine(dt, rec.time_begin.time()) + duration,
                "status": "waiting_approve_reserve",
                "how_often_repeat": "one_time",
                "repeat_until_date": rec.repeat_until_date,
            })
            for customer in rec.customer_ids:
                customer.frozen_balance_card += rec.duration_hours * rec.price_per_hour_from_person
                customer.balance_card -= rec.duration_hours * rec.price_per_hour_from_person
        if to_create:
            self.env["training.model"].sudo().create(to_create)


    # Validate
    @api.constrains("price_total_from_person","payment_to_instructor")
    def _check_complete_field_payment(self):
        """ Check Total Price and Payment to Instructor """
        for rec in self:
            if rec.price_total_from_person and rec.price_total_from_person == 0.00:
                raise ValidationError(f"Please, check field\n"
                                      f"Price Total (from person): {rec.price_total_from_person}")
            if rec.payment_to_instructor and rec.payment_to_instructor == 0.00:
                raise ValidationError(f"Please, check field\n"
                                      f"Payment to Instructor: {rec.payment_to_instructor}")

    @api.constrains("customer_ids", "price_total_from_person")
    def _check_can_customer_pay_by_training(self):
        """ Check opportunity Customer to Pay by training """
        for rec in self:
            for customer in rec.customer_ids:
                if customer.balance_card < rec.price_total_from_person:
                    raise ValidationError(
                        f"Customer '{customer.name}' does not have enough money to reserve this training.\n"
                        f"Balance: {customer.balance_card}\n"
                        f"Already reserved: {customer.frozen_balance_card}\n"
                        f"Required for this training: {rec.price_total_from_person}"
                    )

    @api.constrains("instructor_id", "time_begin", "time_finish")
    def _check_instructor_conflicts(self):
        """ Check Instructor Conflicts """
        for rec in self:
            if rec.status == "unavailable" or rec.name == "free slot":
                continue
            if rec.instructor_id and rec.time_begin and rec.time_finish:
                overlapping_ids = self.search([
                    ("name", "!=", "free slot"),
                    ("status", "!=", "cancelled"),
                    ("instructor_id", "=", rec.instructor_id.id),
                    ("time_begin", "<", rec.time_finish),
                    ("time_finish", ">", rec.time_begin),
                    ("id", "!=", rec.id),
                ])
                if overlapping_ids:
                    names = ", ".join([t.name or "" for t in overlapping_ids])
                    raise ValidationError(
                        f"The Instructor has another training in this time:\n{names}"
                    )

    @api.constrains("customer_ids", "time_begin", "time_finish")
    def _check_customers_conflicts(self):
        """ Check Customers Conflicts """
        for rec in self:
            if rec.how_often_repeat != "one_time":
                continue
            if rec.customer_ids and rec.time_begin and rec.time_finish:
                for customer in rec.customer_ids:
                    overlapping_ids = self.search([
                        ("status", "!=", "cancelled"),
                        ("customer_ids", "in", customer.id),
                        ("time_begin", "<", rec.time_finish),
                        ("time_finish", ">", rec.time_begin),
                        ("id", "!=", rec.id),
                    ])
                    if overlapping_ids:
                        names = ", ".join([t.name or "" for t in overlapping_ids])
                        raise ValidationError(
                            f"The Customer '{customer.name}' has another training in this time:\n"
                            f"{names}\n"
                        )

    @api.constrains("tennis_court_id", "time_begin", "time_finish")
    def _check_schedule_conflicts(self):
        """ Check Schedule Conflicts """
        for rec in self:
            if rec.status == "unavailable" or rec.name == "free slot":
                continue
            if rec.tennis_court_id and rec.time_begin and rec.time_finish:
                overlapping_ids = self.search([
                    ("id", "!=", rec.id),
                    ("status", "!=", "cancelled"),
                    ("tennis_court_id", "=", rec.tennis_court_id.id),
                    ("time_begin", "<", rec.time_finish),
                    ("time_finish", ">", rec.time_begin),
                ])
                if overlapping_ids:
                    for one_overlapping_training in overlapping_ids:
                        if one_overlapping_training.name == "free slot":
                            one_overlapping_training.unlink()
                        else:
                            names = ", ".join([t.name or "" for t in overlapping_ids])
                            raise ValidationError(
                                f"The training overlaps with another training session on this court:\n"
                                f"{names}"
                            )

    @api.constrains("center_id", "time_begin", "time_finish")
    def _check_working_hours(self):
        """ Check Working Hours """
        for rec in self:
            if rec.name == "non-working hours" or rec.name == "free slot":
                continue
            if self._get_active_employee().id == 1:
                continue
            if rec.center_id and rec.time_begin and rec.time_finish:

                today = fields.Datetime.now().date()
                if rec.time_begin.date() < today:
                    raise ValidationError("You cannot schedule training in the past.")

                try:
                    working_hours = json.loads(rec.center_id.working_hours_center_local) or {}
                except ValueError:
                    raise ValidationError("Invalid working hours data for the center.")

                weekday = rec.time_begin.weekday() + 1
                intervals = working_hours.get(str(weekday), [])

                if not intervals:
                    raise ValidationError("Center is closed on this day.")

                local_begin = Datetime.context_timestamp(self, rec.time_begin)
                local_finish = Datetime.context_timestamp(self, rec.time_finish)

                begin_time = local_begin.time()
                finish_time = local_finish.time()

                ok = False
                for interval in intervals:
                    start_str, end_str = interval.split("-")
                    start_t = time(int(start_str[:2]), int(start_str[3:]))
                    end_t = time(int(end_str[:2]), int(end_str[3:]))
                    if begin_time >= start_t and finish_time <= end_t:
                        ok = True
                        break

                if not ok:
                    raise ValidationError("Training cannot be scheduled outside of center opening hours.")

    @api.constrains("customer_ids", "product_training_id")
    def _check_count_customers(self):
        """ Check Count Customers """
        for rec in self:
            if rec.status == "unavailable" or rec.name == "free_slots":
                continue
            if rec.count_customers > rec.product_training_id.count_customers:
                raise ValidationError("Invalid count of customers for this training")

    @api.constrains("duration_hours")
    def _check_duration_hours(self):
        """ Check Duration Hours """
        for rec in self:
            if rec.status == "unavailable":
                continue
            if self._get_active_employee().id == 1:
                continue
            if rec.duration_hours < 1 or rec.duration_hours != int(rec.duration_hours):
                raise ValidationError("The duration of training should be a multiple of 1 hour.")

    @api.constrains("repeat_until_date", "how_often_repeat")
    def _check_repeat_data(self):
        """ Check Repeat Data"""
        for rec in self:
            if rec.repeat_until_date and rec.how_often_repeat != "one_time":
                count_repeat = self.count_recurrences(rec.repeat_until_date, rec.how_often_repeat)["count"]
                necessary_balance = rec.price_total_from_person * count_repeat
                for customer in rec.customer_ids:
                    customer_balance = customer.balance_card
                    if customer_balance < necessary_balance:
                        raise ValidationError(f"Customer {customer.name} have not enough balance for reserve.\n"
                                              f"Customer Balance = {customer.balance_card}")

    @api.constrains("status")
    def _check_status_transitions(self):
        """ Check Status Transitions by Instructor """
        active_employee_id = self._get_active_employee()
        for rec in self:
            if rec.status == "unavailable" or rec.name == "free slot":
                continue
            if rec.status in ["reserved"] and active_employee_id.department_id.name == "Instructor":
                raise ValidationError(
                    "Instructor cannot change to 'Reserved'"
                )


    # Onchange
    @api.onchange("customer_ids", "product_training_id")
    def _onchange_customers_limit(self):
        """ Customers Limit """
        for rec in self:
            if rec.count_customers > rec.product_training_id.count_customers:
                return {
                    "warning": {
                        "title": "Limit Reached",
                        "message": f"The customer limit for this training session has been reached. \n"
                                   f"Customer limit for this training {rec.product_training_id.count_customers}"
                    }
                }

    @api.onchange("time_begin")
    def _onchange_time_finish(self):
        """ Change Time Finish"""
        for rec in self:
            rec.time_finish = rec.time_begin + timedelta(hours=1) if rec.time_begin else False

    @api.onchange("product_training_id", "instructor_id")
    def _onchange_name(self):
        """ Change Name """
        for rec in self:
            if rec.tennis_court_id and rec.product_training_id and rec.instructor_id:
                rec.name = f"{rec.tennis_court_id.name} - {rec.instructor_id.name} - {rec.product_training_id.type_training}"

    @api.onchange("customer_ids")
    def _onchange_count_customers(self):
        """ Change Count Customers """
        for rec in self:
            rec.count_customers = len(rec.customer_ids.ids)

    @api.onchange("product_training_id", "status")
    def _onchange_price_training_total_per_hour(self):
        """ Change Price Training Total Per Hour """
        for rec in self:
            if rec.fix_price_training_total_per_hour:
                rec.price_training_total_per_hour = rec.fix_price_training_total_per_hour
            else:
                rec.price_training_total_per_hour = rec.product_training_id.list_price or 0.0

    @api.onchange("count_customers", "price_training_total_per_hour")
    def _onchange_price_per_hour_from_person(self):
        """ Change Price per Hour from Person """
        for rec in self:
            rec.price_per_hour_from_person = rec.price_training_total_per_hour / rec.count_customers if rec.count_customers else 0.0

    # Depends
    @api.depends("duration_hours", "instructor_id", "product_training_id", "fix_payment_to_instructor")
    def _compute_payment_to_instructor(self):
        """ Compute Payment to Instructor """
        for rec in self:
            if rec.fix_payment_to_instructor:
                rec.payment_to_instructor = rec.fix_payment_to_instructor
            else:
                type_training = rec.product_training_id.type_training
                price_field = f"price_per_hour_{type_training}"
                price = getattr(rec.instructor_id, price_field, 0.0)
                rec.payment_to_instructor = price * rec.duration_hours

    @api.depends("product_training_id", "product_training_id.list_price", "fix_price_training_total_per_hour")
    def _compute_price_training_total_per_hour(self):
        """ Compute Price Training total per Hour """
        for rec in self:
            if rec.fix_price_training_total_per_hour:
                rec.price_training_total_per_hour = rec.fix_price_training_total_per_hour
            else:
                rec.price_training_total_per_hour = rec.product_training_id.list_price or 0.0

    @api.depends("count_customers", "price_training_total_per_hour")
    def _compute_price_per_hour_from_person(self):
        """ Compute Price per Hour from Person """
        for rec in self:
            rec.price_per_hour_from_person = rec.price_training_total_per_hour / rec.count_customers if rec.count_customers else 0.0

    @api.depends("price_per_hour_from_person", "duration_hours")
    def _compute_price_total_from_person(self):
        """ Compute Price Total from Person """
        for rec in self:
            rec.price_total_from_person = rec.price_per_hour_from_person * rec.duration_hours or 0.0

    @api.depends("customer_ids")
    def _compute_used_customer_ids(self):
        """ Compute Used Customer """
        for rec in self:
            rec.used_customer_ids = rec.mapped("customer_ids")

    @api.depends("tennis_court_id", "tennis_court_id.parent_center_id")
    def _compute_center(self):
        """ Compute Center """
        for rec in self:
            rec.center_id = rec.tennis_court_id.parent_center_id or False

    @api.depends("customer_ids")
    def _compute_count_customers(self):
        """ Compute Count Customers """
        for rec in self:
            if rec.fix_count_customers:
                rec.count_customers = rec.fix_count_customers
            else:
                rec.count_customers = len(rec.customer_ids.ids)

    @api.depends("time_begin", "time_finish")
    def _compute_duration_hours(self):
        """ Compute duration Hours """
        for rec in self:
            if rec.time_begin and rec.time_finish:
                delta = rec.time_finish - rec.time_begin
                rec.duration_hours = delta.total_seconds() / 3600
            else:
                rec.duration_hours = 0.0

    @api.depends("status", "name")
    def _compute_color(self):
        """ Compute Color """
        for rec in self:
            if rec.name == "free slot":
                rec.color = 2
            elif rec.status == "unavailable":
                rec.color = 8
            elif rec.status == "new":
                rec.color = 3
            elif rec.status == "waiting_approve_reserve":
                rec.color = 4
            elif rec.status == "reserved":
                rec.color = 10
            elif rec.status == "done":
                rec.color = 7
            elif rec.status == "waiting_approve_cancel":
                rec.color = 5
            elif rec.status == "cancelled":
                rec.color = 1
            else:
                rec.color = 9

    @api.depends("instructor_id", "instructor_id.department_id")
    def _compute_is_user_is_instructor(self):
        """ Compute User is Instructor """
        for rec in self:
            rec.is_user_is_instructor = not rec._get_active_employee().is_not_instructor if rec._get_active_employee() else False

    def action_add_random_customers(self):
        """ Action for Adding Random Customer to Training """
        self.ensure_one()

        used_ids = self.used_customer_ids.ids
        free_customer_ids = self.env["res.partner"].search([
            ("id", "not in", used_ids),
            ("is_customer", "=", "True")
        ])

        if not free_customer_ids:
            return

        customer = free_customer_ids[random.randint(0, len(free_customer_ids) - 1)]
        self.used_customer_ids = [(4, customer.id)]
        self.customer_ids = self.used_customer_ids
