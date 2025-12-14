import json

from calendar import monthrange
from datetime import date, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import pytz
from datetime import datetime, time

class CentersModel(models.Model):
    _name = "centers.model"
    _description = "Centers and Courts"

    id_center = fields.Integer(
        string="ID for onchange",
        store=True
    )

    name = fields.Char(string="Name")

    is_center = fields.Boolean(
        default = False,
        string="Is Center",
    )

    child_courts_ids = fields.One2many(
        comodel_name="centers.model",
        inverse_name="parent_center_id",
        string="Child Courts",
    )

    parent_center_id = fields.Many2one(
        comodel_name="centers.model",
        string="Parent center",
    )

    worker_ids = fields.One2many(
        comodel_name="hr.employee",
        inverse_name="working_center_id",
        string="Workers"
    )

    employee_ids = fields.Many2many(
        "hr.employee",
        compute="_compute_employees",
        # For demo data uncomment
        # store=False,
        store=True,
        string="Employees",
        relation="centers_employee_rel",
        column1="center_id",
        column2="employee_id"
    )

    parent_employee_ids = fields.Many2many(
        "hr.employee",
        compute="_compute_parent_employees",
        # For demo data uncomment
        # store=False,
        store=True,
        string="Parent Center Employees",
        relation="centers_parent_employee_rel",
        column1="center_id",
        column2="employee_id"
    )

    main_manager_id = fields.Many2one(
        comodel_name="hr.employee",
        compute="_compute_manager",
        string="Main Manager",
    )

    working_hours_center_utc = fields.Json(
        string="Working Hours Center (UTC)",
        store=True,
    )
    working_hours_center_local = fields.Json(
        string="Working Hours Center"
    )

    # For Statistic
    total_money_for_period = fields.Float(
        string="Total Money For Period",
        store = True,
    )

    filter_profitable_customer_visit_id = fields.Many2one(
        string="Filter Profitable Customer Visit",
        comodel_name="res.partner",
        store=False
    )
    count_for_period = fields.Integer(string="Count for Period", store=False)

    filter_profitable_customer_money_id = fields.Many2one(
        string="Filter Profitable Customer Money",
        comodel_name="res.partner",
        store=False
    )
    money_for_period = fields.Integer(string="Money for Period", store=False)

    filter_profitable_instructor_id = fields.Many2one(
        string="Filter Profitable Instructor",
        comodel_name="hr.employee",
        store=False
    )
    profit_for_period = fields.Integer(string="Profit for Period", store=False)

    filter_most_visited_training_id = fields.Many2one(
        string="Filter the Most Visited Training",
        comodel_name="product.product",
        store=False
    )
    count_for_period_training = fields.Integer(string="Count for Period Trainig", store=False)

    period_start = fields.Date(
        string="Start of Period",
        store=False
    )
    period_end = fields.Date(
        string="End of Period",
        store=False
    )

    is_freeze_for_report = fields.Boolean(
        string="Frozen for Report",
        store=True,
        default=False
    )
    period_start_frozen = fields.Date(
        string="Start of Period Frozen",
        store=True,
        compute="_compute_frozen_time"
    )
    period_end_frozen = fields.Date(
        string="End of Period Frozen",
        store=True,
        compute="_compute_frozen_time"
    )


    # Main
    @api.model
    def default_get(self, fields):
        res = super(CentersModel, self).default_get(fields)
        today = date.today()
        res["period_start"] = today.replace(day=1)
        res["period_end"] = today.replace(day=monthrange(today.year, today.month)[1])
        self._onchange_period_dates()
        if self.working_hours_center_utc:
            res["working_hours_center_local"] = self.convert_utc_to_user_timezone(self.working_hours_center_utc)
        else:
            res["working_hours_center_local"] = (
                'DEFAULT {"1":["10:00-18:00"], '
                '"2":["10:00-18:00"], '
                '"3":["10:00-18:00"], '
                '"4":["10:00-18:00"], '
                '"5":["10:00-18:00"], '
                '"6":["10:00-18:00"], '
                '"7":["10:00-18:00"]}',
            )
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("working_hours_center_local"):
                working_hours = json.loads(vals["working_hours_center_local"])
                working_hours = self._convert_working_hours_to_utc(working_hours)
                vals["working_hours_center_utc"] = json.dumps(working_hours)

            elif "working_hours_center_utc" in vals:
                local_hours = self.convert_utc_to_user_timezone(vals["working_hours_center_utc"])
                vals["working_hours_center_local"] = json.dumps(local_hours)

        records = super(CentersModel, self).create(vals_list)

        ProductProduct = self.env["product.product"]
        type_training_values = [key for key, _ in ProductProduct._fields["type_training"].selection]
        selection_dict = dict(ProductProduct._fields["type_training"].selection)

        for record in records:
            if record.is_center:
                for training_type in type_training_values:
                    name = f"{selection_dict[training_type]} - {record.name}"
                    ProductProduct.create({
                        "name": name,
                        "type_training": training_type,
                        "center_id": record.id,
                        "list_price": 0.0,
                        "type": "service",
                    })
            record.id_center = record.id

            if not record.is_freeze_for_report:
                record.period_start_frozen = record.period_start
                record.period_end_frozen = record.period_end

        return records

    def write(self, vals):
        working_hours_changed = (
                "working_hours_center_local" in vals and
                vals.get("working_hours_center_local") != self.working_hours_center_local
        )
        if "working_hours_center_local" in vals:
            working_hours = json.loads(vals["working_hours_center_local"])
            working_hours = self._convert_working_hours_to_utc(working_hours)
            vals["working_hours_center_utc"] = json.dumps(working_hours)
        elif "working_hours_center_utc" in vals:
            local_hours = self.convert_utc_to_user_timezone(vals["working_hours_center_utc"])
            vals["working_hours_center_local"] = json.dumps(local_hours)

        res = super(CentersModel, self).write(vals)
        if working_hours_changed:
            for rec in self:
                if not rec.is_center:
                    continue
                training_ids = self.env["training.model"].sudo().search([
                    ("center_id", "=", rec.id),
                    ("product_training_id", "=", 1),
                    ("instructor_id", "=", 1),
                    "|",
                    ("status", "=", "new"),
                    ("status", "=", "unavailable"),
                ])
                training_ids.unlink()
        return res


    def clean_intervals(self, intervals):
        """It merges overlapping intervals, taking into account the transition across 00:00"""

        def time_to_minutes(t):
            h, m = map(int, t.split(':'))
            return h * 60 + m

        def minutes_to_time(m):
            m = m % (24 * 60)
            h = m // 60
            m = m % 60
            return f"{h:02d}:{m:02d}"

        interval_minutes = []
        for interval in intervals:
            start, end = interval.split('-')
            start_min = time_to_minutes(start)
            end_min = time_to_minutes(end)
            if end_min <= start_min:
                end_min += 24 * 60
            interval_minutes.append((start_min, end_min))

        interval_minutes.sort(key=lambda x: x[0])

        merged = []
        for start, end in interval_minutes:
            if not merged:
                merged.append((start, end))
            else:
                last_start, last_end = merged[-1]
                if start <= last_end:  # пересечение
                    merged[-1] = (last_start, max(last_end, end))
                else:
                    merged.append((start, end))

        result = []
        for start, end in merged:
            if end <= 24 * 60:
                result.append(f"{minutes_to_time(start)}-{minutes_to_time(end)}")
            else:
                result.append(f"{minutes_to_time(start)}-00:00")
                result.append(f"00:00-{minutes_to_time(end)}")

        return result

    def _prev_weekday(self, day):
        return "7" if day == "1" else str(int(day) - 1)

    def _next_weekday(self, day):
        return "1" if day == "7" else str(int(day) + 1)

    def _convert_working_hours_to_utc(self, working_hours):
        """
        Convert working hours from user's timezone to UTC,
        split intervals crossing days at 00:00,
        merge overlaps.
        """
        user_tz = pytz.timezone(self.env.user.tz or "UTC")
        utc = pytz.UTC
        result = {}
        today = datetime.today()

        for weekday, intervals in working_hours.items():
            for interval in intervals:
                start_str, end_str = interval.split("-")
                start_local = user_tz.localize(datetime.combine(today, time.fromisoformat(start_str)))
                end_local = user_tz.localize(datetime.combine(today, time.fromisoformat(end_str)))

                if end_local <= start_local:
                    end_local += timedelta(days=1)

                start_utc = start_local.astimezone(utc)
                end_utc = end_local.astimezone(utc)

                start_day_diff = (start_utc.date() - start_local.date()).days
                end_day_diff = (end_utc.date() - start_local.date()).days

                start_weekday = self._shift_weekday(weekday, start_day_diff)
                end_weekday = self._shift_weekday(weekday, end_day_diff)

                if start_weekday == end_weekday:
                    result.setdefault(start_weekday, []).append(
                        f"{start_utc.strftime('%H:%M')}-{end_utc.strftime('%H:%M')}"
                    )
                else:
                    result.setdefault(start_weekday, []).append(
                        f"{start_utc.strftime('%H:%M')}-00:00"
                    )
                    result.setdefault(end_weekday, []).append(
                        f"00:00-{end_utc.strftime('%H:%M')}"
                    )

        for day, intervals in result.items():
            result[day] = self.clean_intervals(intervals)

        return result

    def _shift_weekday(self, weekday, offset):
        """We shift the day of the week by an offset (-1, 0, 1)."""
        wd = int(weekday) + offset
        if wd < 1:
            wd += 7
        elif wd > 7:
            wd -= 7
        return str(wd)

    @api.model
    def convert_utc_to_user_timezone(self, working_hours_utc):
        """
        working_hours_utc: dict, for example
            {"1": ["07:00-15:00"], "2": ["07:00-15:00"], ..., "6": ["07:00-21:00"]}
            user_tz_str: str, for example "Europe/Moscow"

        Returns a dict in the same format, but with times in the user's local time zone.
        """
        user_tz_str = self.env.user.tz or "UTC"
        user_tz = pytz.timezone(user_tz_str or "UTC")
        utc = pytz.UTC
        today = date.today()
        working_hours_utc = json.loads(working_hours_utc)

        result = {}

        for weekday, intervals in working_hours_utc.items():
            local_intervals = []
            for interval in intervals:
                start_str, end_str = interval.split("-")

                start_utc = utc.localize(datetime.combine(today, time.fromisoformat(start_str)))
                end_utc = utc.localize(datetime.combine(today, time.fromisoformat(end_str)))

                start_local = start_utc.astimezone(user_tz)
                end_local = end_utc.astimezone(user_tz)

                local_intervals.append(f"{start_local:%H:%M}-{end_local:%H:%M}")

            result[weekday] = local_intervals

        return result


    # Onchange
    @api.onchange("child_courts_ids","parent_center_id")
    def _onchange_not_both_child_and_parent(self):
        """ Check in UI not both child and parent """
        for rec in self:
            if rec.child_courts_ids and rec.parent_center_id:
                raise ValidationError(_("Place can not be both Center and Court"))

    @api.onchange("period_start", "period_end", "worker_ids")
    def _onchange_period_dates(self):
        """ Onchange Data for Statistic """
        for rec in self:
            rec._compute_worker_view_ids()

    # Depends
    @api.depends("is_freeze_for_report", "period_start", "period_end")
    def _compute_frozen_time(self):
        """ Write Frozen Data for Statistic """
        for rec in self:
            if not rec.is_freeze_for_report:
                rec.period_start_frozen = rec.period_start
                rec.period_end_frozen = rec.period_end


    @api.depends("worker_ids")
    def _compute_manager(self):
        """ Get Main Manager """
        manager_department_id = self.env["hr.department"].search([("name", "=", "Manager")], limit=1)
        for rec in self:
            rec.main_manager_id = self.env["hr.employee"].search(
                [("working_center_id", "=", rec.id),
                 ("department_id", "=", manager_department_id.id)],
                limit=1)

    @api.depends("parent_center_id.worker_ids")
    def _compute_parent_employees(self):
        """ Get workers for Court from parent Center """
        for record in self:
            record.parent_employee_ids = record.parent_center_id.worker_ids

    @api.depends("worker_ids", "period_start", "period_end")
    def _compute_worker_view_ids(self):
        """ Update Statistic Data """
        for rec in self:
            begin_period, end_period = rec._get_report_period()
            period_end_next_day = end_period + timedelta(days=1)

            rec.filter_profitable_customer_visit_id = False
            rec.count_for_period = False
            rec.filter_profitable_customer_money_id = False
            rec.money_for_period = False
            rec.filter_profitable_instructor_id = False
            rec.profit_for_period = False
            rec.filter_most_visited_training_id = False
            rec.count_for_period_training = False

            rec.total_money_for_period = False

            for worker in rec.worker_ids:
                worker.count_trainings_done = 0
                worker.count_customers_in_training = 0
                worker.profit_to_center_total = 0
                worker.salary_period = 0
                worker.profit_to_center_center = 0

                training_ids = self.env["training.model"].search([
                    ("instructor_id", "=", worker.id_instructor),
                    ("status", "=", "done"),
                    ("time_begin", ">=", begin_period),
                    ("time_finish", "<", period_end_next_day),
                    ("center_id.is_center", "=", True),
                ])

                worker.count_trainings_done = len(training_ids)
                worker.count_customers_in_training = sum(training_ids.mapped("fix_count_customers"))
                worker.profit_to_center_total= sum(training_ids.mapped("fix_total_money"))
                worker.salary_period = sum(training_ids.mapped("fix_payment_to_instructor"))
                worker.profit_to_center_center = sum(training_ids.mapped("fix_total_money")) - worker.salary_period

                rec.total_money_for_period += worker.profit_to_center_center

            if rec.id_center:
                done_training_ids = self.env["training.model"].search([
                    ("status", "=", "done"),
                    ("time_begin", ">=", begin_period),
                    ("time_finish", "<", period_end_next_day),
                    ("center_id","=", rec.id_center)
                ])

                customers_visits = {}
                customers_money = {}
                for t in done_training_ids:
                    for cust in t.customer_ids:
                        customers_visits[cust] = customers_visits.get(cust, 0) + 1
                        customers_money[cust] = customers_money.get(cust, 0.0) + (t.fix_total_money or 0.0) / len(t.customer_ids)

                if customers_visits:
                    top_customer_visit = max(customers_visits.items(), key=lambda x: x[1])
                    rec.filter_profitable_customer_visit_id = top_customer_visit[0].id
                    rec.count_for_period = top_customer_visit[1]
                else:
                    rec.filter_profitable_customer_visit_id = False
                    rec.count_for_period = 0

                if customers_money:
                    top_customer_money = max(customers_money.items(), key=lambda x: x[1])
                    rec.filter_profitable_customer_money_id = top_customer_money[0].id
                    rec.money_for_period = top_customer_money[1]
                else:
                    rec.filter_profitable_customer_money_id = False
                    rec.money_for_period = 0.0

                instructor_ids = rec.worker_ids.filtered(lambda w: not w.is_not_instructor)
                profit_instructors = {}
                for instr in instructor_ids:
                    profit_instructors[instr] = instr.profit_to_center_center
                if profit_instructors:
                    top_instr = max(profit_instructors.items(), key=lambda x: x[1])
                    rec.filter_profitable_instructor_id = top_instr[0].id
                    rec.profit_for_period = top_instr[1]
                else:
                    rec.filter_profitable_instructor_id = False
                    rec.profit_for_period = 0.0

                trainings_by_product_ids = {}
                for t in done_training_ids:
                    if t.product_training_id:
                        trainings_by_product_ids[t.product_training_id] = trainings_by_product_ids.get(t.product_training_id, 0) + 1
                if trainings_by_product_ids:
                    top_training = max(trainings_by_product_ids.items(), key=lambda x: x[1])
                    rec.filter_most_visited_training_id = top_training[0].id
                    rec.count_for_period_training = top_training[1]
                else:
                    rec.filter_most_visited_training_id = False
                    rec.count_for_period_training = 0

    @api.depends("worker_ids")
    def _compute_employees(self):
        """ Get workers from Center """
        for record in self:
            record.employee_ids = record.worker_ids

    # Validation
    @api.constrains("is_center", "parent_center_id")
    def _check_is_center_or_parent(self):
        """ Check is Court or is Center """
        for rec in self:
            if not rec.is_center and not rec.parent_center_id:
                raise ValidationError(_(
                    "There can be center or court.\n\n"
                    "You should choose the checkbox 'Is Center' or choose 'Parent Center'."
                ))

    @api.constrains("working_hours_center_local")
    def _check_working_hours(self):
        """ Check Working Hours """
        for rec in self:
            if rec.is_center:
                if isinstance(rec.working_hours_center_local, str):
                    try:
                        data = json.loads(rec.working_hours_center_local)
                    except:
                        raise ValidationError(_("Incorrect Working Hours"))

                    for day, intervals in data.items():
                        for interval in intervals:
                            parts = interval.split("-")
                            if len(parts) != 2:
                                raise ValueError("Incorrect working hours")

                            for part in parts:
                                time_parts = part.split(":")
                                if len(time_parts) != 2:
                                    raise ValueError("Incorrect working hours")
                                hour, minute = time_parts
                                if not hour.isdigit() or not minute.isdigit():
                                    raise ValueError("Incorrect working hours")
                                hour = int(hour)
                                minute = int(minute)
                                if not (0 <= hour <= 24 and 0 <= minute < 60):
                                    raise ValueError("Incorrect working hours")

                                if hour == 24 and minute != 0:
                                    raise ValueError("Incorrect working hours")

    @api.constrains("name")
    def _check_names(self):
        """ Check Name is Unique """
        for rec in self:
            if rec.is_center == True:
                existing_ids = self.search([
                    ("name", "=", rec.name),
                    ("id", "!=", rec.id),
                    ("is_center", "=", True)
                ])
                if existing_ids:
                    raise ValidationError(f"Name '{rec.name}' must be unique.")

    def action_print_report_from_list(self):
        """ Action print Report """
        today = date.today()
        context = dict(self.env.context or {})
        context.update({
            "report_period_start": today.replace(day=1),
            "report_period_end": today.replace(day=monthrange(today.year, today.month)[1]),
        })
        return self.env.ref("tennis_club.action_report_center_print_form").with_context(context).report_action(self)

    def _get_report_period(self):
        """ Func for getting statistic period """
        return self.period_start_frozen or self.period_start or date.today().replace(day=1), \
               self.period_end_frozen or self.period_end or date.today().replace(
                   day=monthrange(date.today().year, date.today().month)[1])