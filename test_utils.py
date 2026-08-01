import unittest
import datetime
from utils import (
    parse_session_datetime,
    format_msk_time,
    format_session_datetime,
    check_race_status,
    extract_race_sessions,
)
from constants import ALLOWED_TIMINGS, ALLOWED_SESSIONS


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
        self.assertIn("1h", ALLOWED_TIMINGS)
        self.assertIn("15m", ALLOWED_TIMINGS)
        self.assertIn("both", ALLOWED_TIMINGS)
        self.assertNotIn("invalid_timing", ALLOWED_TIMINGS)

        self.assertIn("main", ALLOWED_SESSIONS)
        self.assertIn("all", ALLOWED_SESSIONS)
        self.assertNotIn("invalid_session", ALLOWED_SESSIONS)


if __name__ == "__main__":
    unittest.main()
