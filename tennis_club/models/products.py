from odoo import models, fields, api

class ProductsModel(models.Model):
    _inherit = "product.product"

    purchase_ok = fields.Boolean( # noqa: system data
        "Purchase",
            default=False,
            store=True,
            readonly=False,
    )

    type = fields.Selection(
        string="Product Type",
        help="Goods are tangible materials and merchandise you provide.\n"
             "A service is a non-material product you provide.",
        selection=[
            ("consu", "Goods"),
            ("service", "Service"),
            ("combo", "Combo"),
        ],
        required=True,
        default="service",
    )

    type_training = fields.Selection(
        string="Training Type",
        selection=[
            ("personal", "Personal"),
            ("split", "Split"),
            ("group", "Group"),
            ("other", "Other")
        ],
        required=True,
        default="other",
    )
    count_customers = fields.Integer(
        string = "Count Customers in training",
        compute="_compute_count_customers",
    )

    center_id = fields.Many2one(
        comodel_name="centers.model",
        string="Sport Center"
    )

    # Onchange
    @api.onchange("type_training","center_id")
    def _onchange_name(self):
        """ Create Default name when create from UI """
        for rec in self:
            if rec.type_training and rec.center_id:
                selection = dict(self._fields["type_training"].selection)
                label = selection.get(rec.type_training, rec.type_training)
                rec.name = f"{label} - {rec.center_id.name}"

    # Depends
    @api.depends("type_training")
    def _compute_count_customers(self):
        """ Compute method for Count Customers depends on type Training"""
        for rec in self:
            count_customers_per_type_training = {
            "personal":1,
            "split":2,
            "group":5,
            "other":1}
            rec.count_customers = count_customers_per_type_training.get(rec.type_training,0)