import uuid
from wsgiref.util import request_uri

from odoo import models, api, fields, Command
from odoo.addons.calendar.models.calendar_recurrence import MAX_RECURRENT_EVENT
import caldav
import logging
from datetime import datetime, date
from icalendar import Calendar, Event, vCalAddress, vText
from bs4 import BeautifulSoup
import re
from pytz import timezone, utc

_logger = logging.getLogger(__name__)

WEEKDAY_MAP = {
    0: "MO",
    1: "TU",
    2: "WE",
    3: "TH",
    4: "FR",
    5: "SA",
    6: "SU",
}


def _parse_rrule_string(rrule_str):
    def try_to_int(part):
        try:
            return int(part)
        except Exception:
            return part

    regex_str = "RRULE:(.*)$"
    regex = re.compile(regex_str)
    params_match = regex.search(rrule_str)
    params_part = params_match.groups()[0]
    params = params_part.split(";")
    params_dict = {}
    for param in params:
        parts = param.split("=")
        params_dict.update({parts[0]: try_to_int(parts[1])})
    return params_dict


def _extract_vcal_email(vcal_address):
    email_regex = re.compile(r"[a-z0-9.\-+_]+@[a-z0-9.\-+_]+\.[a-z]+")
    res = email_regex.search(str(vcal_address))
    return res.group(0).lower().strip() if res else ""


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    caldav_uid = fields.Char(string="CalDAV UID", readonly=True)
    # Recurrence ID in iCalendar is the date or datetime the event would have
    # been at if it followed the sequence. It is set by calendar.recurrence
    # when applying a recurrence.
    caldav_recurrence_id = fields.Char(
        string="CalDAV Recurrence ID",
    )
    caldav_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_caldav_users",
    )
    is_base_event = fields.Boolean(compute="_compute_is_base_event")
    differs_from_base_event = fields.Boolean(compute="_compute_differs_from_base_event")

    @api.depends("name", "description", "partner_ids", "location", "videocall_location")
    def _compute_differs_from_base_event(self):
        base_events = self.filtered("is_base_event")
        non_base_events = self - base_events
        for event in base_events:
            event.differs_from_base_event = False
        fields_to_check = [
            "name",
            "description",
            "partner_ids",
            "location",
            "videocall_location",
        ]
        for event in non_base_events:
            base_event = event.recurrence_id.base_event_id
            event.differs_from_base_event = any(
                [
                    getattr(event, field) != getattr(base_event, field)
                    for field in fields_to_check
                ]
            )

    @api.depends("is_base_event")
    def _compute_update_all_recurrence(self):
        for rec in self:
            rec.update_all_recurrence = (
                rec.recurrency
                and rec.is_base_event
                and (
                    rec.recurrence_update == "all_events"
                    or not rec.recurrence_update
                    or rec.recurrence_id.calendar_event_ids == rec
                )
            )

    @api.depends("recurrency", "recurrence_id.base_event_id")
    def _compute_is_base_event(self):
        for rec in self:
            rec.is_base_event = (
                not rec.recurrency or rec.recurrence_id.base_event_id == rec
            )

    @api.depends("user_id", "partner_ids", "partner_ids.user_id")
    def _compute_caldav_users(self):
        for rec in self:
            rec.caldav_user_ids = (rec.user_id | rec.partner_ids.user_ids).filtered(
                "is_caldav_enabled"
            )

    def _to_sync(self):
        return self.filtered(
            lambda event: event._is_caldav_enabled()
            and (event.is_base_event or event.differs_from_base_event)
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("caldav_uid"):
                vals["caldav_uid"] = str(uuid.uuid4())
        events = super(CalendarEvent, self).create(vals_list)
        if not self.env.context.get("caldav_no_sync"):
            events._to_sync()._sync_create_to_caldav()
        return events

    def write(self, vals):
        res = super().write(vals)
        to_sync = self._to_sync()
        if to_sync and self.env.context.get("caldav_no_sync"):
            for rec in to_sync:
                _logger.debug(
                    f"Updating event {rec.name} in CalDAV. " f"{rec.fields_get()}"
                )
                rec._sync_update_to_caldav()
        return res

    def unlink(self):
        if not self.env.context.get("caldav_no_sync"):
            for rec in self._to_sync():
                try:
                    _logger.debug(f"Removing event {rec.name} from CalDAV")
                    rec._sync_remove_from_caldav()
                except Exception as e:
                    _logger.error(f"Failed to delete event from CalDAV server: {e}")
        return super(CalendarEvent, self).unlink()

    def _is_caldav_enabled(self):
        return self.env.user.is_caldav_enabled

    def _sync_create_to_caldav(self):
        for event in self:
            for user in event.caldav_user_ids:
                client = user._get_caldav_client()
                calendar = client.calendar(url=user.caldav_calendar_url)
                try:
                    _logger.debug(f"Creating new CalDAV event for {event.name}")
                    caldav_events = event._create_in_icalendar(calendar)
                    for caldav_event in caldav_events:
                        caldav_uid = caldav_event.vobject_instance.vevent.uid.value
                        _logger.debug(f"New CalDAV UID: {caldav_uid}")
                        event.with_context(caldav_no_sync=True).write(
                            {"caldav_uid": caldav_uid}
                        )
                except Exception as e:
                    _logger.error(f"Failed to sync event to CalDAV server: {e}")

    def _sync_update_to_caldav(self):
        ical_event_data = self._create_event_data()
        for user in self.caldav_user_ids:
            client = user._get_caldav_client()
            calendar = client.calendar(url=self.env.user.caldav_calendar_url)
            event = self._find_in_icalendar(calendar, user)
            if event:
                event.save(**ical_event_data)
            else:
                calendar.save_event(**ical_event_data)

    def _sync_remove_from_caldav(self):
        if self.caldav_uid:
            for user in self.caldav_user_ids:
                client = user._get_caldav_client()
                calendar = client.calendar(url=self.env.user.caldav_calendar_url)
                try:
                    _logger.debug(f"Removing CalDAV event {self.caldav_uid}")
                    ical_event = self._find_in_icalendar(calendar, user)
                    if ical_event:
                        ical_event.delete()
                except caldav.error.NotFoundError:
                    _logger.warning(
                        f"CalDAV event {self.caldav_uid} not found on server during deletion."
                    )
                except Exception as e:
                    _logger.error(f"Failed to remove event from CalDAV server: {e}")

    def _find_in_icalendar(self, calendar, user):
        # Since search by uid and recurrence-id is not yet supported,
        # we do it manually
        match_recurrence_id = self.recurrency and not self.is_base_event
        if not match_recurrence_id:
            return calendar.event_by_uid(self.caldav_uid)
        else:
            events = user._get_caldav_events()
            for event in events:
                event = event.icalendar_instance
                if (
                    event.get("uid") == self.caldav_uid
                    and event.get("recurrence-id") == self.caldav_recurrence_id
                ):
                    return event
        return None

    def _create_in_icalendar(self, calendar):
        ical_event_data = self._create_event_data()
        caldav_event = calendar.save_event(**ical_event_data)
        if self.recurrency and self.is_base_event and not self.follow_recurrence:
            ical_event_data = self._create_event_data()
            second_caldav_event = calendar.save_event(**ical_event_data)
            return [caldav_event, second_caldav_event]
        return [caldav_event]

    def _create_event_data(self):
        event_data = {}
        self._add_event_dates(event_data)
        self._add_event_header_info(event_data)
        self._add_event_attendees(event_data)
        if self.is_base_event and self.recurrency:
            self._add_event_recurrence(event_data)
        elif self.recurrency:
            self._add_event_recurrence_id(event_data)
        return event_data

    def _add_event_header_info(self, event_data):
        event_data["uid"] = self.caldav_uid
        if self.name:
            event_data["summary"] = self.name
        # TODO: Consider using X-ALT-DESC to stick HTML into the iCal event desc.
        if self.description and self._html_to_text(self.description):
            event_data["description"] = self._html_to_text(self.description)
        if self.location:
            event_data["location"] = self.location
        if self.videocall_location:
            event_data["CONFERENCE"] = self.videocall_location

    def _add_event_dates(self, event_data):
        user_tz = timezone("UTC")
        if self.user_id.tz:
            user_tz = timezone(self.user_id.tz)
        event_data["last-modified"] = utc.localize(self.write_date).astimezone(user_tz)
        event_data["created"] = utc.localize(self.create_date).astimezone(user_tz)
        event_data["dtstart"] = utc.localize(self.start).astimezone(user_tz)
        event_data["dtend"] = utc.localize(self.stop).astimezone(user_tz)
        return event_data

    def _add_event_recurrence_id(self, event_data):
        if self.recurrency:
            event_data["recurrence-id"] = self._get_ical_recurrence_id()

    def _add_event_recurrence(self, event_data):
        # Add RRULE if the event is recurrent
        if self.recurrency:
            rrule = self.recurrence_id._get_rrule()
            rrule_dict = _parse_rrule_string(str(rrule))
            event_data["rrule"] = rrule_dict

    def _add_event_attendees(self, event_data):
        attendee_lines = []
        for partner in self.partner_ids:
            if partner == self.user_id.partner_id:
                continue
            attendee = vCalAddress(f"MAILTO:{partner.email}")
            attendee.params["cn"] = vText(partner.name)
            attendee_record = self.env["calendar.attendee"].search(
                [("event_id", "=", self.id), ("partner_id", "=", partner.id)],
                limit=1,
            )
            if attendee_record:
                attendee.params["partstat"] = vText(
                    self._map_attendee_status(attendee_record.state)
                )
            attendee_lines.append(attendee)
        organizer = vCalAddress(f"MAILTO:{self.user_id.email}")
        organizer.params["cn"] = self.user_id.name
        event_data["organizer"] = organizer
        event_data["attendee"] = attendee_lines

    def _get_ical_recurrence_id(self):
        user_tz = timezone(self.user_id.tz)
        recurrence_id = utc.localize(
            datetime.strptime(self.caldav_recurrence_id, "%Y%m%dT%H%M%S")
        ).astimezone(user_tz)
        return recurrence_id

    @api.model
    def poll_caldav_server(self):
        all_users = self.env["res.users"].search([("is_caldav_enabled", "=", True)])
        for user in all_users:
            self._poll_user_caldav_server(user)

    @api.model
    def _poll_user_caldav_server(self, user):
        _logger.info(f"Polling CalDAV server for user {user.name}")
        events = user._get_caldav_events()
        synced_events = self.env["calendar.event"]
        for caldav_event in events:
            ical_event = caldav_event.icalendar_instance
            synced_events |= self._sync_event_from_ical(ical_event, user)

        # TODO: check if this fails when the user is deleting someone else's event
        # TODO: check if we should send updates to invitees
        orphaned_events = self.search(
            [
                ("caldav_uid", "!=", False),
                ("id", "not " "in", synced_events.ids),
                ("user_id", "=", user.id),
            ]
        )._to_sync()
        if orphaned_events:
            _logger.info(f"Deleting orphaned events {orphaned_events.ids}")
            orphaned_events.with_context(caldav_no_sync=True).with_user(user).unlink()

    @api.model
    def _get_existing_instance(self, uid, recurrence_id):
        if recurrence_id:
            recurrence_id = recurrence_id.dt.strftime("%Y%m%dT%H%M%S")
            instance = self.env["calendar.event"].search(
                [
                    ("caldav_uid", "=", uid),
                    ("caldav_recurrence_id", "=", recurrence_id),
                ]
            )
        else:
            instance = self.env["calendar.event"].search(
                [
                    ("caldav_uid", "=", uid),
                    ("recurrency", "=", False),
                ]
            )
            if instance:
                return instance
            else:
                return (
                    self.env["calendar.recurrence"]
                    .search(
                        [
                            ("base_event_id.caldav_uid", "=", uid),
                        ]
                    )
                    .base_event_id
                )

        if len(instance) == 1:
            return instance
        if len(instance) > 1:
            instance = instance.recurrence_id.base_event_id

        return instance or self.env["calendar.event"].search(
            [
                ("caldav_uid", "=", "uid"),
                ("recurrence_id", "=", False),
            ]
        )

    def _get_recurrency_values_from_ical_event(self, component):
        """Match the fields from calendar.event (recurring fields) to the fields specified in RRULE at
        https://icalendar.org/iCalendar-RFC-5545/3-8-5-3-recurrence-rule.html"""

        if component.get("recurrence-id"):
            # When a component has "recurrence-id" set, it is a single event
            # in a series of events. Recurrence-id is the time the event should
            # normally occur at if it follows the recurrence of the series.
            follow_recurrence = (
                component.get("recurrence-id").dt == component.get("dtstart").dt
            )
            if self and self.follow_recurrence == follow_recurrence:
                return {
                    "follow_recurrence": follow_recurrence,
                }
            else:
                return {
                    "follow_recurrence": follow_recurrence,
                    "recurrence_update": "self-only",
                }
        rrule = [item[1] for item in component.property_items() if item[0] == "RRULE"]
        rrule = rrule[0] if rrule else None

        if not rrule:
            return {}

        rrule_str = rrule.to_ical() and rrule.to_ical().decode("utf-8")
        rrule_params = self.env["calendar.recurrence"]._rrule_parse(
            rrule_str, component.decoded("dtstart")
        )
        vals = {
            "recurrency": True,
            "follow_recurrence": True,
            "recurrence_update": "all_events",
            **rrule_params,
        }
        # Convert None to False since fields from Odoo that are not filled come back False
        vals = {
            key: value if value is not None else False for key, value in vals.items()
        }

        # Forever doesn't exist in Odoo. The calendar.recurrence model changes 'forever'
        # into 'count' with MAX_RECURRENT_EVENT as the 'count' parameter
        if vals.get("end_type") == "forever":
            vals.update(end_type="count")
            if not vals.get("count"):
                vals.update(count=MAX_RECURRENT_EVENT)
        return vals

    def _get_recurrence_changes(self, recurrency_vals):
        if not recurrency_vals and not self.recurrency:
            return {}
        if not recurrency_vals and self.recurrency:
            return {"recurrence_update": "all_events", "recurrency": False}
        if recurrency_vals and not self.recurrency:
            return recurrency_vals
        changed_fields = {
            key: recurrency_vals[key]
            for key in recurrency_vals.keys()
            if hasattr(self, key) and recurrency_vals[key] != getattr(self, key)
        }
        if (
            len(changed_fields) == 1
            and changed_fields.get("recurrence_update") == "all_events"
        ):
            return {}
        return changed_fields

    def _get_value_changes(self, values):
        changed_vals = {}
        # Don't update partner_ids if no change
        if "partner_ids" in values:
            partner_ids = values["partner_ids"][0][2]  # this is a SET command
            added_partner_ids = set(
                [id for id in partner_ids if id not in self.partner_ids.ids]
            )
            removed_partner_ids = set(
                [id for id in self.partner_ids.ids if id not in partner_ids]
            )
            if not (added_partner_ids or removed_partner_ids):
                values.pop("partner_ids")  # They break the equality check later
            else:
                changed_vals["partner_ids"] = values["partner_ids"]

        # Get just the list of values that have changed, leave the others alone
        for key, val in values.items():
            curr_val = getattr(self, key)
            # Can't deal with x2many fields, need ID from a record
            if isinstance(val, list):
                continue
            if curr_val and isinstance(curr_val, models.Model):
                if len(curr_val) > 1:
                    continue
                curr_val = curr_val.id
            if curr_val != val:
                changed_vals.update({key: val})
        return changed_vals

    def _sync_event_from_ical(self, ical_event, user):
        synced_events = self.env["calendar.event"]
        event_components = [
            component for component in ical_event.walk() if component.name == "VEVENT"
        ]
        for component in event_components:
            uid = str(component.get("uid"))
            recurrence_id = component.get(
                "recurrence-id"
            )  # Date & time a single event would normally be at in the series

            existing_instance = self._get_existing_instance(uid, recurrence_id)
            outdated = self._get_outdated(component, existing_instance, synced_events)
            owned = (
                existing_instance and existing_instance.partner_id == user.partner_id
            )
            values = self._get_values_from_ical_component(component, user)
            recurrency_vals = existing_instance._get_recurrency_values_from_ical_event(
                component
            )
            if not existing_instance:
                _logger.info(f"Creating with vals: {values | recurrency_vals}")
                new_event = self.with_context(caldav_no_sync=True).create(
                    values | recurrency_vals
                )
                self.env["calendar.event"].flush_model()
                if new_event.recurrency:
                    synced_events |= new_event.recurrence_id.calendar_event_ids
                else:
                    synced_events |= new_event
                continue
            elif outdated or not owned:
                _logger.info(
                    f"Event {existing_instance.caldav_uid}-{existing_instance.caldav_recurrence_id} "
                    f"{'outdated' if outdated else ''}"
                    f"{'not owned by user' + user.name if not owned else ''}."
                    f" Skipping."
                )
                # Do nothing, it's not this user's event to modify or it's outdated
            else:
                changed_vals = existing_instance._get_recurrence_changes(
                    recurrency_vals
                ) | existing_instance._get_value_changes(values)
                if changed_vals:
                    _logger.info(
                        f"Updating event {existing_instance.caldav_uid}-{existing_instance.caldav_recurrence_id} with : {changed_vals}"
                    )
                    existing_instance.with_context(
                        caldav_no_sync=True,
                    ).write(changed_vals)
            if existing_instance.recurrency and existing_instance.is_base_event:
                synced_events |= existing_instance.recurrence_id.calendar_event_ids
            else:
                synced_events |= existing_instance
        return synced_events

    def _get_outdated(self, component, existing_instance, synced_events):
        outdated = False
        last_modified = component.get("last-modified")
        if (
            existing_instance
            and last_modified
            and existing_instance not in synced_events
        ):
            last_modified = last_modified.dt.astimezone(utc).replace(tzinfo=None)
            if last_modified < existing_instance.write_date:
                outdated = True
        return outdated

    def _get_values_from_ical_component(self, component, user):
        start = component.get("dtstart") and component.decoded("dtstart")
        if isinstance(start, datetime):
            start = start.astimezone(utc).replace(tzinfo=None)
        end = component.get("dtend") and component.decoded("dtend")
        if isinstance(end, datetime):
            end = end.astimezone(utc).replace(tzinfo=None)
        organizer = self._get_organizer_partner(component)
        attendee_ids = self._get_attendee_partners(component, user.partner_id.email)
        values = {
            "name": str(component.get("summary")),
            "start": start,
            "stop": end,
            "description": self._extract_component_text(component, "description"),
            "location": self._extract_component_text(component, "location"),
            "videocall_location": self._extract_component_text(component, "conference"),
            "caldav_uid": str(component.get("uid")),
            "partner_ids": [(6, 0, attendee_ids.ids)],
            "partner_id": organizer.id if organizer else user.partner_id.id,
            "user_id": user.id,
        }
        return values

    def _get_attendee_partners(self, component, current_user_email):
        attendee_emails = self._get_ical_attendee_emails(component)
        if current_user_email not in attendee_emails:
            attendee_emails.append(current_user_email)
        existing_partners = self.env["res.partner"].search(
            [("email", "in", attendee_emails)]
        )
        missing_emails = [
            email
            for email in attendee_emails
            if email not in [partner.email for partner in existing_partners]
        ]
        added_partners = self.env["res.partner"].create(
            [
                {
                    "name": email,
                    "email": email,
                }
                for email in missing_emails
            ]
        )
        final_attendees = {}
        all_partners = existing_partners | added_partners
        # We do this because partners may have identical emails and we only want one
        # attending partner per email. Otherwise invitations get sent out multiple times
        # and nobody likes that.
        # Prioritize users as attendees
        for partner in all_partners.filtered(lambda partner: bool(partner.user_id)):
            if partner.email not in final_attendees:
                final_attendees[partner.email] = partner.id

        for partner in all_partners.filtered(lambda partner: not partner.user_id):
            if partner.email not in final_attendees:
                final_attendees[partner.email] = partner.id

        return all_partners.filtered(
            lambda partner: partner.id in final_attendees.values()
        )

    def _get_organizer_partner(self, component):
        organizer = component.get("organizer")
        if organizer:
            partner = self.env["res.partner"].search(
                [("email", "=", _extract_vcal_email(organizer))]
            )
            # TODO: prioritize partner with a user if there is one
            return partner[0] if partner else partner  # partner[0] in case many matches
        else:
            return self.env["res.partner"]

    @staticmethod
    def _get_ical_attendee_emails(component):
        attendees = component.get("attendee", [])
        if not isinstance(attendees, list):
            attendees = [attendees]
        attendee_emails = [_extract_vcal_email(attendee) for attendee in attendees]
        return attendee_emails

    @staticmethod
    def _extract_component_text(component, subcomponent_name):
        val = component.get(subcomponent_name)
        text = str(val) if val else ""
        return text

    @staticmethod
    def _html_to_text(html):
        return BeautifulSoup(html, "html.parser").getText()

    @staticmethod
    def _map_attendee_status(state):
        mapping = {
            "needsAction": "NEEDS-ACTION",
            "accepted": "ACCEPTED",
            "declined": "DECLINED",
            "tentative": "TENTATIVE",
        }
        return mapping.get(state, "NEEDS-ACTION")
