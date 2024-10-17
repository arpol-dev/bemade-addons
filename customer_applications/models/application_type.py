from odoo import models, fields, api


class PartnerApplicationType(models.Model):
    _name = "partner.application.type"
    _description = "Partner Application Type"

    _inherit = ["mail.thread", "mail.activity.mixin"]

    color = fields.Integer()
    name = fields.Char(
        required=True,
        tracking=1,
    )
    description = fields.Text(tracking=2)
    application_ids = fields.One2many(
        comodel_name="partner.application",
        inverse_name="application_type_id",
        tracking=3,
    )

    applications_count = fields.Integer(
        string="Applications Count",
        compute="_compute_applications_count",
    )

    partner_ids = fields.One2many(
        comodel_name="res.partner",
        compute="_compute_partner_ids",
        search="_search_partner_ids",
        string="Partners",
        readonly=True,
    )

    @api.depends("application_ids", "application_ids.partner_id")
    def _compute_partner_ids(self):
        for application_type in self:
            application_type.partner_ids = application_type.application_ids.mapped(
                "partner_id"
            )

    def _search_partner_ids(self, operator, value):
        return [("application_ids.partner_id", operator, value)]

    @api.depends("application_ids")
    def _compute_applications_count(self):
        for record in self:
            record.applications_count = len(record.application_ids)
