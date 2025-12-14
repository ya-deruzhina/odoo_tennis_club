from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _inherit = "account.move"

    name = fields.Char(
        string="Number",
    )

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True
    )

    is_paid = fields.Boolean(
        string="Is Paid",
        default=False,
        store=True
    )
    invoice_user_id = fields.Many2one(
        string="Salesperson",
        comodel_name="hr.employee",
        copy=False,
        tracking=True,
        store=True,
        readonly=True,
        default=lambda self: self._get_default_invoice_user()
    )

    # Main
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.name = f"Invoice №{rec.id}"
            if rec.state == "posted" and rec.payment_state == "paid":
                amount = sum(rec.invoice_line_ids.mapped("price_total"))
                rec.partner_id.balance_card += amount
        return records

    @api.model
    def _get_default_invoice_user(self):
        """ Get default User """
        employee = self.env["hr.employee"].search([("user_id", "=", self.env.user.id)], limit=1)
        print(employee)
        return employee.id if employee else False

    def write(self, vals):
        old_states = {rec.id: rec.state for rec in self}
        old_paiments = {rec.id: rec.payment_state for rec in self}
        result = super().write(vals)

        for rec in self:
            old_paid = (old_states[rec.id] == "posted" and old_paiments[rec.id] == "paid")
            new_paid = (rec.state == "posted" and rec.payment_state == "paid")

            amount = sum(rec.invoice_line_ids.mapped("price_total"))

            if old_paid and not new_paid:
                rec.partner_id.balance_card -= amount

            elif not old_paid and new_paid:
                rec.partner_id.balance_card += amount

        return result

    # Constrains
    @api.constrains("is_paid")
    def check_product_not_test(self):
        """ Check product before paid """
        for rec in self:
            if rec.is_paid and rec.invoice_line_ids:
                test_product_line = rec.invoice_line_ids.filtered(
                    lambda l: l.product_id and l.product_id.name == "Test for All"
                )
                if test_product_line:
                    raise ValidationError(
                        _("You cannot mark this invoice as paid because it contains a test product (Test for All)."))

    # Depends
    @api.depends("is_paid")
    def _compute_payment_state(self):
        """ Compute Boolean for 'is paid' """
        for rec in self:
            if rec.is_paid:
                rec.payment_state = "paid"
            else:
                rec.payment_state = "not_paid"