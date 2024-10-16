from odoo import models, fields


class PartnerApplicationType(models.Model):
    _name = "partner.application.type"
    _description = "Partner Application Type"

    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        required=True,
        tracking=1,
    )
    description = fields.Text(tracking=2)
