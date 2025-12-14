# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Tennis Club",
    "version": "1.0",
    "category": "Custom",
    "author": "Deruzhina",
    "summary": "Module for tennis club",
    "description": "For tennis club",
    "depends": ["base", "hr", "account","product","web"],
    "data": [
        "security/security_groups.xml",
        "security/security_rules.xml",
        "security/ir.model.access.csv",

        "views/invoice.xml",
        "views/customers.xml",
        "views/employe.xml",
        "views/training.xml",
        "views/products.xml",

        "data/cron_jobs.xml",
        "data/cron_notify_telegram.xml",
        "data/cron_auto_complite_training.xml",

        "report/action_print_form_center.xml",
        "report/report_print_form_center_template.xml",

        "views/centers.xml",
        "wizards/change_department_wizard.xml",

    ],
    "demo": [
        "demo/demo_data_all.xml"],
    "assets": {
        "web.assets_backend": [
            "tennis_club/static/src/js/x2m_default_lines.js",
            "tennis_club/static/src/js/calendar_new_slots.js",
        ],
    },
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",
    "license": "LGPL-3",
}
