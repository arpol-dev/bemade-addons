from odoo import models, fields


class PartnerApplicationSpecification(models.Model):
    _name = "partner.application.specification"
    _description = "Partner Application Specification"
    _inherit = ["mail.thread", "mail.activity.mixin", "incrementing.sequence.mixin"]
    _sequence_group = "application_id"

    name = fields.Char(
        tracking=2,
        required=True,
    )
    value = fields.Text(
        tracking=2,
    )
    application_id = fields.Many2one(
        comodel_name="partner.application",
        tracking=1,
    )
