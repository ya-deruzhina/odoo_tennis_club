from odoo import api, SUPERUSER_ID

def post_init_hook(cr_or_env, registry=None):
    if registry is None:
        env = cr_or_env
    else:
        env = api.Environment(cr_or_env, SUPERUSER_ID, {})

    #   REMOVE IN PROD - Company
    company = env.ref("base.main_company")

    #  REMOVE IN PROD - Create General Journal if missing
    if not env["account.journal"].search([("company_id", "=", company.id), ("type", "=", "sale")], limit=1):
        env["account.journal"].create({
            "name": "General Journal",
            "code": "GEN",
            "type": "sale",
            "company_id": company.id,
        })

    # Admin with full access
    admin_user = env.ref("base.user_admin", raise_if_not_found=False)
    custom_group = env.ref("tennis_club.group_admin_full_access", raise_if_not_found=False)
    if admin_user and custom_group and custom_group not in admin_user.groups_id:
        admin_user.write({"groups_id": [(4, custom_group.id)]})
        if admin_user.partner_id:
            admin_user.partner_id.is_customer = False

    #   REMOVE IN PROD - Company partner is not customer
    if company.partner_id:
        company.partner_id.is_customer = False

    # Create Departments
    department_model = env["hr.department"]
    for name in ["Head", "Manager", "Instructor", "Not Created"]:
        if not department_model.search([("name", "=", name)], limit=1):
            department_model.create({"name": name})

    #   REMOVE IN PROD - Create Tax Group and Tax
    tax_group = env["account.tax.group"].search([("name", "=", "Default VAT Group")], limit=1)
    if not tax_group:
        tax_group = env["account.tax.group"].create({
            "name": "Default VAT Group",
            "company_id": company.id,
        })

    tax_0 = env["account.tax"].search([("name", "=", "VAT 0%"), ("company_id", "=", company.id)], limit=1)
    if not tax_0:
        env["account.tax"].create({
            "name": "VAT 0%",
            "amount": 0.0,
            "type_tax_use": "sale",
            "amount_type": "percent",
            "company_id": company.id,
            "tax_group_id": tax_group.id,
            "country_id": env.ref("base.us").id,
        })

    # Create default Product
    Product = env["product.product"]
    if not Product.search([("name", "=", "Test for All")], limit=1):
        Product.create({
            "name": "Test for All",
            "type_training": "other",
            "center_id": False,
            "list_price": 0.0,
            "type": "service",
        })
