from odoo import models, fields, api
from pytz import timezone


class RecurrenceRule(models.Model):
    _inherit = "calendar.recurrence"

    def _apply_recurrence(self, **kwargs):
        detached_events = super()._apply_recurrence(**kwargs)

        def _get_recurrence_id(event):
            format = "%Y%m%d" if event.allday else "%Y%m%dT%H%M%S"
            return event.start.astimezone(timezone(event.user_id.tz)).strftime(format)

        for event in self.calendar_event_ids:
            event.caldav_recurrence_id = _get_recurrence_id(event)

        return detached_events
