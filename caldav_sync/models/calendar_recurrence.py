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

    def _stop_at(self, event):
        detached_events = super()._stop_at(event)
        detached_events._recompute_caldav_uid()
        detached_events._recompute_caldav_recurrence_id()
        self.calendar_event_ids._sync_recurrence_to_caldav()
        # detached_events._sync_recurrence_to_caldav()
        return detached_events
