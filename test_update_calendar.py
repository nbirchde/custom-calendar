import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from icalendar import Calendar, Event

from update_calendar import (
    SOURCE_ICS_URL,
    clean_location,
    extract_course_code,
    extract_course_name,
    extract_teacher,
    get_event_type,
    should_keep_event,
    unescape_ics,
    update_calendar,
)

FEED_SUMMARY = "INFOF403, Théorie, Enseignant: GEERAERTS Gilles, M-INFOS:1, M-IRIFS:1"


def make_event(summary, uid, description="", location="", days=0):
    ev = Event()
    ev.add("summary", summary)
    start = datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc) + timedelta(days=days)
    ev.add("dtstart", start)
    ev.add("dtend", start + timedelta(hours=2))
    if location:
        ev.add("location", location)
    if description:
        ev.add("description", description)
    ev.add("uid", uid)
    ev.add("dtstamp", start)
    return ev


def make_feed(*events):
    cal = Calendar()
    cal.add("prodid", "-//TimeEdit//")
    cal.add("version", "2.0")
    for ev in events:
        cal.add_component(ev)
    return cal.to_ical().decode("utf-8")


def read_events(directory):
    out = {}
    for name in sorted(os.listdir(directory)):
        with open(os.path.join(directory, name), "rb") as f:
            cal = Calendar.from_ical(f.read())
        out[name] = [e for e in cal.walk("VEVENT")]
    return out


class TestHelpers(unittest.TestCase):
    def test_unescape_ics(self):
        self.assertEqual(unescape_ics("a\\, b"), "a, b")
        self.assertEqual(unescape_ics("a\\; b"), "a; b")
        self.assertEqual(unescape_ics("a\\nb"), "a\nb")
        self.assertEqual(unescape_ics(None), "")

    def test_get_event_type(self):
        self.assertEqual(get_event_type("INFOF403, Théorie"), "Theory")
        self.assertEqual(get_event_type("ELECH417, Travaux pratiques"), "Lab")
        self.assertEqual(get_event_type("INFOH417, Exercices"), "Exercises")
        self.assertEqual(get_event_type("PROJH402, Projet"), "Project")
        self.assertEqual(get_event_type("Random event"), "")

    def test_clean_location(self):
        self.assertEqual(clean_location("P.NO4.008 (PC)\\, P.NO4.009"), "P.NO4.008 (PC)")
        self.assertEqual(clean_location("Salle: H.1302, Campus"), "H.1302")
        self.assertEqual(clean_location(None), "")

    def test_extract_course_code(self):
        self.assertEqual(extract_course_code(FEED_SUMMARY), "INFOF403")
        self.assertEqual(extract_course_code("ELECH417, Travaux pratiques"), "ELECH417")
        self.assertIsNone(extract_course_code("Info: Toussaint"))

    def test_extract_course_name(self):
        self.assertEqual(
            extract_course_name("Introduction to language theory and compiling\\nID 1514188"),
            "Introduction to language theory and compiling",
        )
        # Untitled break events carry a date range instead of a title.
        self.assertEqual(extract_course_name("01/11/2026 23:00 - 02/11/2026 23:00\\nID 1"), "")

    def test_extract_teacher(self):
        self.assertEqual(extract_teacher(FEED_SUMMARY), "GEERAERTS Gilles")
        self.assertEqual(extract_teacher("INFOF403, Théorie"), "")

    def test_group_filter(self):
        self.assertTrue(should_keep_event("ELECH417", "Lab", "ELECH417, Travaux pratiques, M-IRIFS:1, M-IRCBS:2"))
        self.assertFalse(should_keep_event("ELECH417", "Lab", "ELECH417, Travaux pratiques, B-INFO:3"))
        self.assertFalse(should_keep_event("ELECH417", "Lab", "ELECH417, Travaux pratiques, M-IRELE:1"))
        self.assertTrue(should_keep_event("ELECH417", "Theory", "ELECH417, Théorie, B-INFO:3"))

    def test_source_url_is_public_view(self):
        self.assertIn("/be_ulb/web/public/ri.ics", SOURCE_ICS_URL)
        self.assertIn("sid=10", SOURCE_ICS_URL)
        self.assertIn("179271.5", SOURCE_ICS_URL)  # INFOF403 2026-27


class TestUpdateCalendar(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cal_test_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_with_feed(self, feed_text):
        with patch("update_calendar.requests.get") as mock_get:
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.text = feed_text
            mock_get.return_value = resp
            return update_calendar("https://example.com/feed.ics", self.dir)

    def test_splits_by_course_and_type_and_writes_merged(self):
        feed = make_feed(
            make_event(FEED_SUMMARY, "1", "Introduction to language theory and compiling\\nID 1", "S.DC2.206"),
            make_event("INFOF403, Exercices, Enseignant: GEERAERTS Gilles, M-IRIFS:1", "2", days=1),
            make_event("INFOH417, Théorie, Enseignant: SAKR Mahmoud, M-IRIFS:1", "3", "Database systems architecture\\nID 3", days=2),
        )
        stats = self.run_with_feed(feed)
        files = read_events(self.dir)
        self.assertEqual(stats["processed"], 3)
        self.assertEqual(
            sorted(files),
            [
                "custom_calendar_INFOF403_exercises.ics",
                "custom_calendar_INFOF403_theory.ics",
                "custom_calendar_INFOH417_theory.ics",
                "custom_calendar_all.ics",
            ],
        )
        theory = files["custom_calendar_INFOF403_theory.ics"][0]
        self.assertEqual(str(theory["summary"]), "Compilers (Theory)")
        self.assertEqual(str(theory["location"]), "S.DC2.206")
        self.assertIn("INFOF403 - Introduction to language theory and compiling", str(theory["description"]))
        self.assertIn("Teacher: GEERAERTS Gilles", str(theory["description"]))
        self.assertEqual(len(files["custom_calendar_all.ics"]), 3)

    def test_filters_noise_and_other_groups(self):
        feed = make_feed(
            make_event("Info: Toussaint", "info"),
            make_event("", "blank", "01/11/2026 23:00 - 02/11/2026 23:00\\nID 9"),
            make_event("INFOH410, Théorie, Enseignant: X", "notmine"),
            make_event("ELECH417, Travaux pratiques, Enseignant: DRICOT Jean-Michel, B-INFO:3", "lab-other"),
            make_event("ELECH417, Travaux pratiques, Enseignant: DRICOT Jean-Michel, M-IRIFS:1, M-IRCBS:2", "lab-mine"),
        )
        stats = self.run_with_feed(feed)
        files = read_events(self.dir)
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["unknown_course"], 1)
        labs = files["custom_calendar_ELECH417_lab.ics"]
        self.assertEqual([str(e["uid"]) for e in labs], ["lab-mine"])

    def test_rerun_replaces_content(self):
        self.run_with_feed(make_feed(make_event(FEED_SUMMARY, "1", location="S.DC2.206")))
        self.run_with_feed(make_feed(make_event(FEED_SUMMARY, "1", location="S.DC2.999")))
        ev = read_events(self.dir)["custom_calendar_INFOF403_theory.ics"][0]
        self.assertEqual(str(ev["location"]), "S.DC2.999")


if __name__ == "__main__":
    unittest.main()
