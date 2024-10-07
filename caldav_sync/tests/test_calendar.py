from collections.abc import Iterable
from odoo.tests import TransactionCase
from odoo import Command
from unittest.mock import patch, MagicMock, PropertyMock
import icalendar
from pathlib import Path
from .common import CaldavTestCommon
from contextlib import contextmanager
from datetime import datetime, UTC, timedelta


def _get_ics_path(filename):
    return Path(__file__).parent / "data" / filename


@contextmanager
def _patch_caldav_with_events_from_ics(ics_paths, user, last_modified=None):
    with (
        patch("caldav.DAVClient") as MockDAVClient,
        patch("caldav.Calendar") as MockCalendar,
        patch("caldav.Event") as MockEvent,
    ):
        mock_client = MockDAVClient.return_value
        mock_calendar = MockCalendar.return_value
        mock_client.calendar = mock_calendar

        def calendar_side_effect(url):
            if url == user.caldav_calendar_url:
                return mock_calendar
            raise Exception("Calendar does not exist.")

        mock_calendar.side_effect = calendar_side_effect
        ical_events = []
        if ics_paths:
            if not isinstance(ics_paths, Iterable):
                ics_paths = [ics_paths] if ics_paths else []
            for ics_path in ics_paths:
                with ics_path.open("rb") as file:
                    ical_content = file.read()
                ical_events.append(icalendar.Calendar.from_ical(ical_content))
        mock_caldav_events = []
        for ical_event in ical_events:
            mock_event = MockEvent()
            mock_event.icalendar_instance = ical_event
            if last_modified:
                for component in ical_event.walk():
                    if component.name == "VEVENT":
                        component["last-modified"] = last_modified.strftime(
                            "%Y%m%dT%H%M%SZ"
                        )
            mock_caldav_events.append(mock_event)
        mock_calendar.events.return_value = mock_caldav_events
        user._compute_is_caldav_enabled()
        yield


class TestCalendarEvent(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.users"].search([])._compute_is_caldav_enabled()
        cls.user_1_url = "https://mycaldav.test.com/test1calendar"
        cls.user_1 = cls._generate_user("test1", "test1", cls.user_1_url)
        cls.user_2_url = "https://mycaldav.test.com/test2calendar"
        cls.user_2 = cls._generate_user("test2", "test2", cls.user_2_url)
        cls.user_3_url = "https://mycaldav.test.com/test3calendar"
        cls.user_3 = cls._generate_user("test3", "test3", cls.user_3_url)

    def test_basic_event_from_server_create(self):
        user = self.user_1
        ics_path = _get_ics_path("basic.ics")
        with _patch_caldav_with_events_from_ics(ics_path, user):
            current_events = self.env["calendar.event"].search([])
            self.env["calendar.event"].poll_caldav_server()
            events_after_sync = self.env["calendar.event"].search([])
            new_events = events_after_sync - current_events
            self.assertEqual(len(new_events), 1)

    def test_basic_event_from_server_update(self):
        user = self.user_1
        ics_path = _get_ics_path("basic.ics")
        with _patch_caldav_with_events_from_ics(ics_path, user):
            self.env["calendar.event"].poll_caldav_server()
        event = self.env["calendar.event"].search([("user_id", "=", user.id)])
        orig_start = event.start
        orig_stop = event.stop
        ics_path = _get_ics_path("basic_updated.ics")
        with _patch_caldav_with_events_from_ics(
            ics_path,
            user,
            last_modified=(datetime.now(UTC)),
        ):
            self.env["calendar.event"].poll_caldav_server()
        event = self.env["calendar.event"].search([("user_id", "=", user.id)])
        self.assertEqual(event.name, "Test Updated")
        # This next one is just lazy avoiding the HTML stripping
        self.assertIn("Some note ...", event.description)
        self.assertGreater(event.start, orig_start)
        self.assertGreater(event.stop, orig_stop)

    def test_basic_event_from_server_delete(self):
        user = self.user_1
        ics_path = _get_ics_path("basic.ics")
        with _patch_caldav_with_events_from_ics(ics_path, user):
            self.env["calendar.event"].poll_caldav_server()
        # Passing None to ics_path means no events returned from server
        with _patch_caldav_with_events_from_ics(None, user):
            self.env["calendar.event"].poll_caldav_server()
        event = self.env["calendar.event"].search([("user_id", "=", user.id)])
        self.assertFalse(event)

    def test_multiple_attendees_event_from_server_create(self):
        user = self.user_1
        ics_path = _get_ics_path("test_multi_attendee.ics")
        with _patch_caldav_with_events_from_ics(ics_path, user):
            self.env["calendar.event"].poll_caldav_server()
        event = self.env["calendar.event"].search([("user_id", "=", user.id)])
        self.assertEqual(len(event.attendee_ids), 3)
        self.assertIn(user.partner_id, event.attendee_ids.partner_id)

    def test_multiple_attendees_event_from_server_update(self):
        user = self.user_1
        ics_path = _get_ics_path("test_multi_attendee.ics")
        with _patch_caldav_with_events_from_ics(ics_path, user):
            self.env["calendar.event"].poll_caldav_server()
        event = self.env["calendar.event"].search([("user_id", "=", user.id)])
        ics_path = _get_ics_path("test_multi_attendee_update.ics")
        with _patch_caldav_with_events_from_ics(
            ics_path, user, last_modified=datetime.now(UTC)
        ):
            self.env["calendar.event"].poll_caldav_server()
        self.assertEqual(len(event.attendee_ids), 2)
        self.assertIn(user.partner_id, event.attendee_ids.partner_id)

    def test_multiple_attendees_event_from_server_delete(self):
        user = self.user_1
        ics_path = _get_ics_path("test_multi_attendee.ics")
        with _patch_caldav_with_events_from_ics(ics_path, user):
            self.env["calendar.event"].poll_caldav_server()
        # Passing None as ics_path means no events returned from server
        with _patch_caldav_with_events_from_ics(None, user):
            self.env["calendar.event"].poll_caldav_server()
        event = self.env["calendar.event"].search([("user_id", "=", user.id)])
        self.assertFalse(event)

    def test_multiple_user_attendees_event_from_server_create(self):
        """Test event has:
        Organizer: user1 (test1@example.com)
        Attendees: user2 and user3 (test2@example.com, test3@example.com)
        """
        user1 = self.user_1
        user2 = self.user_2
        user3 = self.user_3
        ics_path = _get_ics_path("test_multi_user.ics")
        with _patch_caldav_with_events_from_ics(ics_path, user1):
            self.env["calendar.event"].poll_caldav_server()

    def test_multiple_user_attendees_event_from_server_update(self):
        pass

    def test_multiple_user_attendees_event_to_server_create(self):
        pass
