from datetime import date, timedelta
from calendar import monthrange

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HREmployeeExtension(models.Model):
    _inherit = "hr.employee"

    id_instructor = fields.Integer(
        string="ID for onchange",
        store=True
    )
    is_current_user_admin = fields.Boolean(
        string="Is Current User Admin",
        compute="_compute_is_visible_finance",
        store=False
    )
    is_visible_finance = fields.Boolean(
        string="Is Current User",
        compute="_compute_is_visible_finance"
    )

    is_not_instructor = fields.Boolean(
        string="Is Not Instructor",
        default=False,
        compute="_compute_is_not_instructor",
        store=True
    )

    working_center_id = fields.Many2one(
        comodel_name="centers.model",
        string="Working center",
        required=True,
    )

    price_per_hour_personal = fields.Float(string="Price per Hour Personal", default=0.0)
    price_per_hour_split = fields.Float(string="Price per Hour Split", default=0.0)
    price_per_hour_group = fields.Float(string="Price per Hour Group", default=0.0)

    salary = fields.Float(
        string="Salary",
        default = 0.0,
        store=False
    )

    profit_to_center = fields.Float(
        string="Profit to Center from Instructor (without Salary)",
        default=0.0,
        store=False,
    )

    begin_reporting_period = fields.Date(
        string="Begin of the Reporting Period",
        store=False
    )

    end_reporting_period = fields.Date(
        string="End of the Reporting Period",
        store=False
    )

    # For Center Statistic
    count_trainings_done = fields.Integer(string="Trainings", store=True)
    count_customers_in_training = fields.Integer(string="Customers", store=True)
    profit_to_center_total = fields.Float(string="Profit TOTAL", store=True)
    salary_period = fields.Float(string="Salary", store=True)
    profit_to_center_center = fields.Float(string="Profit Final", store=True)


    # Main
    @api.model
    def default_get(self, fields):
        """ Getting default report period """
        res = super(HREmployeeExtension, self).default_get(fields)
        today = date.today()
        res["begin_reporting_period"] = today.replace(day=1)
        res["end_reporting_period"] = today.replace(day=monthrange(today.year, today.month)[1])
        self._onchange_reporting_period()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._unset_other_managers()
            if rec.work_contact_id:
                rec.work_contact_id.is_customer = False
            rec.id_instructor = rec.id if rec.id else False
            rec._update_group_by_department()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "department_id" in vals:
            for emp in self:
                emp._update_group_by_department()
                if emp.department_id and emp.department_id.name == "Manager":
                    emp._unset_other_managers()
                if not emp.is_not_instructor or emp.id_instructor == 0:
                    emp.id_instructor = emp.id if emp.id else False

        if "working_center_id" in vals:
            self.env.registry.clear_cache()

        return res

    def _update_group_by_department(self):
        """ Update permission group"""
        group_obj = self.env["res.groups"]
        for rec in self:
            user = rec.user_id.sudo()
            if not user:
                continue
            dep_group_names = ["Head", "Manager", "Instructor", "Administration", "Not Created"]

            if user.department_id and user.department_id.name in ["Manager", "Instructor","Not Created"]:
                group_id = group_obj.search([("name", "=", user.department_id.name)], limit=1)
                if group_id:
                    user.groups_id = [(6, 0, [group_id.id])]

            elif user.department_id and user.department_id.name in ["Administration", "Head"]:
                old_groups = user.groups_id.filtered(lambda g: g.name in dep_group_names)
                user.groups_id = [(3, g.id) for g in old_groups]
                group_id = group_obj.search([("name", "=", user.department_id.name)], limit=1)
                if group_id:
                    user.groups_id = [(4, group_id.id)]

    def unlink(self):
        for rec in self:
            if rec.department_id and rec.department_id.name == "Manager":
                raise ValidationError(_(
                    "The manager contact cannot be deleted. Please change it and try again"
                ))
        return super().unlink()

    def _unset_other_managers(self):
        """ Change department of Managers of the same Center to Not Created """
        for rec in self:
            names = False
            if rec.department_id and rec.department_id.name == "Manager" and rec.working_center_id:
                manager_ids = self.search([
                    ("working_center_id", "=", rec.working_center_id.id),
                    ("id", "!=", rec.id),
                    ("department_id.name", "=", "Manager")
                ])
                not_created_department = self.env["hr.department"].search([("name", "=", "Not Created")], limit=1)
                if not not_created_department:
                    not_created_department = self.env["hr.department"].create({
                        "name": "Not Created",
                    })
                if manager_ids:
                    names = ", ".join(manager_ids.mapped("name"))
                    manager_ids.write({"department_id": not_created_department.id})
        return names

    # Onchange
    @api.onchange("working_center_id")
    def _onchange_one_manager_in_center(self):
        """ Send UI notification about other Managers of same Center"""
        for rec in self:
            if rec.department_id and rec.department_id.name == "Manager" and rec.working_center_id:
                other_manager_ids = self.env["hr.employee"].search([
                    ("id", "!=", rec.id),
                    ("working_center_id", "=", rec.working_center_id.id),
                    ("department_id.name", "=", "Manager"),
                ])
                if other_manager_ids:
                    names = ", ".join(other_manager_ids.mapped("name"))
                    return {
                        "warning": {
                            "title": _("Only One Manager Allowed"),
                                       "message": _(
                                           f"There can only be one manager per working center. \n\n"
                                           f"Other managers were unset automatically."
                                           f"\n{names}"),
                                   }
                    }

    @api.onchange("begin_reporting_period", "end_reporting_period")
    def _onchange_reporting_period(self):
        """ Change Data for Report """
        for rec in self:
            rec._compute_salary_and_profit()


    #Depends
    @api.depends("department_id")
    def _compute_is_not_instructor(self):
        """ Compute method for Bool is_not_instructor """
        for rec in self:
            rec.is_not_instructor = rec.department_id.name != "Instructor" if rec.department_id else True

    @api.depends("begin_reporting_period", "end_reporting_period")
    def _compute_salary_and_profit(self):
        """ Compute method for change Salary and Profit_to_center """
        for rec in self:
            rec.profit_to_center = 0
            rec.salary = 0

            begin_period = rec.begin_reporting_period or date.today().replace(day=1)
            end_period = rec.end_reporting_period or date.today().replace(
                day=monthrange(date.today().year, date.today().month)[1]
            )
            period_end_next_day = end_period + timedelta(days=1)

            if rec.id_instructor:
                training_ids = self.env["training.model"].search([
                    ("instructor_id", "=", rec.id_instructor),
                    ("status", "=", "done"),
                    ("time_begin", ">=", begin_period),
                    ("time_finish", "<", period_end_next_day),
                ])
            else:
                training_ids = self.env["training.model"]

            rec.salary = sum(training_ids.mapped("fix_payment_to_instructor"))
            rec.profit_to_center = sum(training_ids.mapped("fix_total_money")) - rec.salary

    @api.depends()
    def _compute_is_visible_finance(self):
        """ Compute method for Bool is_visible_finance depends on Group Access and Instructor record """
        for rec in self:
            user_id = self.env.user
            rec.is_current_user_admin = (
                    user_id.has_group("tennis_club.group_admin_full_access") or
                    user_id.has_group("tennis_club.group_administration") or
                    user_id.has_group("tennis_club.group_head")
            )

            if rec.is_not_instructor:
                rec.is_visible_finance = False
            elif rec.is_current_user_admin:
                rec.is_visible_finance = True
            else:
                rec.is_visible_finance = rec.id_instructor == user_id.employee_id.id and not rec.is_not_instructor


    def open_department_password_wizard(self):
        """ New window for Change Department """
        return {
            "name": "Change Department",
            "type": "ir.actions.act_window",
            "res_model": "department.password.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_employee_id": self.id,
                "default_working_center_id":self.working_center_id.id
            }
        }




