from odoo import models, fields, api


class PartnerApplicationSpecification(models.Model):
    _name = "partner.application.specification"
    _description = "Partner Application Specification"
    _inherit = ["mail.thread", "mail.activity.mixin", "incrementing.sequence.mixin"]
    _sequence_group = "application_id"

    key_id = fields.Many2one(
        comodel_name="partner.application.specification.key",
        tracking=1,
        ondelete="restrict",
        domain="[('id', 'in', allowed_specification_keys)]",
        string="Name",
        required=True,
    )
    name = fields.Char(
        related="key_id.name",
    )
    value = fields.Text(
        tracking=2,
    )
    application_id = fields.Many2one(
        comodel_name="partner.application",
        tracking=1,
        ondelete="cascade",
    )
    allowed_specification_keys = fields.Many2many(
        related="application_id.application_type_id.allowed_specification_keys",
    )
