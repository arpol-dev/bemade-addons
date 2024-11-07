from odoo import models, fields, api
import uuid
import logging

_logger = logging.getLogger(__name__)


class RecurrenceRule(models.Model):
    _inherit = "calendar.recurrence"

    @api.model
    def _default_uid(self):
        return uuid.uuid4()

    caldav_uid = fields.Char(
        default=_default_uid,
        readonly=True,
    )
