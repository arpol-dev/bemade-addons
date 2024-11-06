from odoo import models, fields, api
from pytz import timezone, utc


class RecurrenceRule(models.Model):
    _inherit = "calendar.recurrence"

    def _detach_events(self, events):
        events = super()._detach_events(events)
        events.with_context(dont_notify=True)._post_recurrence_detach()
        return events
