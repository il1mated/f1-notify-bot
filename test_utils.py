import unittest
import datetime
from utils import (
    parse_session_datetime,
    format_msk_time,
    format_session_datetime,
    check_race_status,
    extract_race_sessions,
    parse_notify_timings,
    serialize_notify_timings,
    format_timings_display,
)
from constants import ALLOWED_TIMINGS, ALLOWED_SESSIONS, ALL_TIMINGS


class UtilsTest(unittest.TestCase):
    def test_format_session_datetime(self):
        self.assertEqual(format_session_datetime("2026-03-15", None), "15.03.2026")
        formatted = format_session_datetime("2026-03-15", "05:00:00Z")
        self.assertIn("15.03.2026, 08:00 МСК", formatted)

    def test_check_race_status(self):
        future_date = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)).strftime("%Y-%m-%d")
        past_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)).strftime("%Y-%m-%d")

        self.assertEqual(check_race_status(future_date, "12:00:00Z"), "")
        self.assertEqual(check_race_status(past_date, "12:00:00Z"), "🏁")

    def test_allowed_settings(self):
        self.assertIn("1d", ALLOWED_TIMINGS)
        self.assertIn("1h", ALLOWED_TIMINGS)
        self.assertIn("15m", ALLOWED_TIMINGS)
        self.assertNotIn("both", ALLOWED_TIMINGS)
        self.assertNotIn("invalid_timing", ALLOWED_TIMINGS)

        self.assertIn("main", ALLOWED_SESSIONS)
        self.assertIn("all", ALLOWED_SESSIONS)
        self.assertNotIn("invalid_session", ALLOWED_SESSIONS)

    def test_parse_notify_timings(self):
        self.assertEqual(parse_notify_timings("1h"), ["1h"])
        self.assertEqual(parse_notify_timings("15m"), ["15m"])
        self.assertEqual(parse_notify_timings("1d"), ["1d"])
        self.assertEqual(parse_notify_timings("both"), ["1h", "15m"])
        self.assertEqual(parse_notify_timings("15m,1d"), ["1d", "15m"])  # canonical order
        self.assertEqual(parse_notify_timings("1d,1h,15m"), ["1d", "1h", "15m"])
        self.assertEqual(parse_notify_timings(""), ["1h"])
        self.assertEqual(parse_notify_timings(None), ["1h"])
        self.assertEqual(parse_notify_timings("invalid"), ["1h"])

    def test_serialize_notify_timings(self):
        self.assertEqual(serialize_notify_timings(["1h"]), "1h")
        self.assertEqual(serialize_notify_timings(["15m", "1d"]), "1d,15m")
        self.assertEqual(serialize_notify_timings({"15m", "1h", "1d"}), "1d,1h,15m")
        self.assertEqual(serialize_notify_timings([]), "1h")

    def test_format_timings_display(self):
        self.assertEqual(format_timings_display(["1h"]), "За 1 час")
        self.assertEqual(format_timings_display(["1d", "1h"]), "За 1 день, За 1 час")
        self.assertEqual(format_timings_display(["1d", "1h", "15m"]), "За 1 день, За 1 час, За 15 минут")
        self.assertEqual(format_timings_display("both"), "За 1 час, За 15 минут")


if __name__ == "__main__":
    unittest.main()
