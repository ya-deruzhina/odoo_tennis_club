from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    invoice_user_center_id = fields.Many2one(
        comodel_name="centers.model",
        string="Salesperson Center",
        related="move_id.invoice_user_id.working_center_id",
        store=True,
        readonly=True
    )

    is_special_training = fields.Boolean(
        string="Is Special Training",
        default=False,
        store=True
    )

    # Onchange
    @api.onchange("product_id")
    def _onchange_is_special_training(self):
        """ Change Bool is_special_training for readonly in UI for price of special training"""
        for rec in self:
            if rec.product_id and rec.product_id.type_training in ["personal","split","group"]:
                rec.is_special_training = True
            else:
                rec.is_special_training = False