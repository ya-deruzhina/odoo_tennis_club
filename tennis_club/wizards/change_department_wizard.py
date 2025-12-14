from odoo import fields, models, api, _
from odoo.exceptions import UserError

class DepartmentPasswordWizard(models.TransientModel):
    _name = "department.password.wizard"
    _description = "Password wizard to change department"

    employee_id = fields.Many2one("hr.employee")
    current_department_id = fields.Many2one(
        "hr.department",
        string="Current Department",
        related="employee_id.department_id",
        readonly=True
    )
    working_center_id = fields.Many2one(comodel_name="centers.model")
    new_department_id = fields.Many2one(
        "hr.department",
        string="New Department",
        required=True
    )
    password = fields.Char(string="Password", required=True)

    def action_apply(self):
        """ Form for change Department """
        self.ensure_one()

        CORRECT_PASSWORD = " "

        if self.password != CORRECT_PASSWORD:
            raise UserError("Incorrect Password!")

        if not self.new_department_id:
            raise UserError("Select a new department!")

        self.employee_id.department_id = self.new_department_id.id

        return {"type": "ir.actions.act_window_close"}

    @api.onchange("new_department_id")
    def _onchange_new_department(self):
        """ Check another managers from same Center """
        if self.new_department_id and self.new_department_id.name == "Manager" and self.working_center_id:
            other_managers = self.env["hr.employee"].search([
                ("id", "!=", self.id),
                ("working_center_id", "=", self.working_center_id.id),
                ("department_id.name", "=", "Manager"),
            ])
            if other_managers:
                names = ", ".join(other_managers.mapped("name"))
                return {
                    "warning": {
                        "title": _("Only One Manager Allowed"),
                        "message": _(
                            f"There can only be one manager per working center. \n\n"
                            f"Other managers were unset automatically."
                            f"\n{names}"),
                    }
                }