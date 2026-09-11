import logging
import uuid

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class RecurrenceRule(models.Model):
    _inherit = "calendar.recurrence"

    caldav_uid = fields.Char(
        readonly=True,
        copy=False,
    )
    _sql_constraints = [
        ("caldav_uid_unique", "UNIQUE (caldav_uid)", "caldav_uid must be unique")
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if not self._context.get("caldav_keep_ids"):
            for vals in vals_list:
                vals["caldav_uid"] = str(uuid.uuid4())
        else:
            for vals in vals_list:
                base_event = self.env["calendar.event"].browse(vals["base_event_id"])
                caldav_uid = base_event.caldav_uid
                if caldav_uid and self.search_count([("caldav_uid", "=", caldav_uid)]):
                    # A recurrence with this caldav_uid already exists (e.g. Odoo
                    # split off a new calendar.recurrence from an already-synced
                    # series on write(), such as a "this and following" edit).
                    # Reusing the same caldav_uid would violate the uniqueness
                    # constraint above, so this new recurrence gets its own
                    # fresh id instead, same as a non-CalDAV-originated one.
                    caldav_uid = str(uuid.uuid4())
                vals.update(caldav_uid=caldav_uid)
        return super().create(vals_list)

    @api.model
    def _detach_events(self, events):
        """When events are detached from a recurrence, their CalDAV UID and
        recurrence-id are no longer going to be valid, so we remove them from
        the server. They may then be re-written to the server with their new
        IDs later, but we don't care about that here.
        """
        detached_events = super()._detach_events(events)
        for event in detached_events:
            event._sync_unlink_to_caldav()
        return detached_events
