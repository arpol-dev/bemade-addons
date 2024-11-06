from odoo import models, fields, api
from pytz import timezone, utc


class RecurrenceRule(models.Model):
    _inherit = "calendar.recurrence"

    def _recompute_event_caldav_recurrence_ids(self):
        def _get_recurrence_id(event):
            return event.start.astimezone(utc).replace(tzinfo=None)

        for event in self.calendar_event_ids:
            event.caldav_recurrence_id = _get_recurrence_id(event)

    def _apply_recurrence(
        self,
        specific_values_creation=None,
        no_send_edit=False,
        generic_values_creation=None,
    ):
        detached_events = super()._apply_recurrence(
            specific_values_creation, no_send_edit, generic_values_creation
        )
        self._recompute_event_caldav_recurrence_ids()
        return detached_events

    def _detach_events(self, events):
        events = super()._detach_events(events)
        events.with_context(dont_notify=True)._post_recurrence_detach()
        return events
