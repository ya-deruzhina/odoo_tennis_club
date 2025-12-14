from odoo import models, fields, api


class CustomersModel(models.Model):
    _inherit = "res.partner"

    activation_date = fields.Datetime(
        string="Activation Date",
        readonly=True
    )
    club_card = fields.Integer(
        string="Club Cards"
    )

    invoice_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="partner_id",
        string="Invoices",
        domain=[("state", "=", "draft")],
        groups="tennis_club.group_admin_full_access,tennis_club.group_manager"
    )

    invoice_lines = fields.One2many( # noqa: system data
        "account.move.line",
        "partner_id",
        string="Invoice Lines",
        groups="tennis_club.group_admin_full_access,tennis_club.group_manager"
    )

    training_ids = fields.Many2many(
        comodel_name="training.model",
        relation="training_partner_rel",
        column1="customer_id",
        column2="training_id",
        string="Trainings",
        domain=[("status", "=", "reserved")],
    )
    company_type = fields.Selection(
        selection=[("person", "Individual"), ("company", "Company")],
        string="Company Type",
        default="person"
    )

    balance_card = fields.Float(
        string="Balance Card",
        default=0.0,
        store=True,
    )

    frozen_balance_card = fields.Float(
        string="Frozen Balance Card",
    )

    is_customer = fields.Boolean(
        string="Is Customer",
        default=True,
    )

    telegram_chat_id = fields.Integer(
        string="Telegram chat id",
        default = 0
    )

    is_permission_to_notify = fields.Boolean(
        string="Permission to send notifications has been received",
        default=False
    )
    is_current_user_admin_and_manager = fields.Boolean(
        compute="_compute_is_current_user_admin_and_manager"
    )

    # Main
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("activation_date"):
                vals["activation_date"] = fields.Datetime.now()
        record_ids = super().create(vals_list)

        for record in record_ids:
            record.club_card = record.id
            if record.company_type != "person":
                record.is_customer = False

        return record_ids

    @api.depends()
    def _compute_is_current_user_admin_and_manager(self):
        """ Compute method for Bool depends on Group Access """
        for rec in self:
            user_id = self.env.user
            rec.is_current_user_admin_and_manager = (
                    user_id.has_group("tennis_club.group_admin_full_access") or
                    user_id.has_group("tennis_club.group_administration") or
                    user_id.has_group("tennis_club.group_head") or
                    user_id.has_group("tennis_club.group_manager")
            )

    # Actions
    def action_create_invoice(self):
        """ Action for creating Invoice with default Product """
        self.ensure_one()
        Product = self.env["product.product"]
        test_product_id = Product.search([("name", "=", "Test for All")], limit=1)
        invoice_vals = {
            "move_type": "out_invoice",
            "partner_id": self.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": test_product_id.id if test_product_id else False,
                "quantity": 1,
                "price_unit": 0.0,
            })] if test_product_id else [],
        }

        return {
            "name": "New Invoice",
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "view_id": False,
            "target": "current",
            "context": {
                "default_move_type": "out_invoice",
                "default_partner_id": self.id,
                "default_invoice_line_ids": invoice_vals["invoice_line_ids"],
            },
        }