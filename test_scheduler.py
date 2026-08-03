import unittest
import datetime
from unittest.mock import AsyncMock, patch
from aiogram.exceptions import TelegramForbiddenError

import scheduler


class SchedulerTest(unittest.IsolatedAsyncioTestCase):
    def test_parse_session_datetime(self):
        dt = scheduler.parse_session_datetime("2026-03-15", "05:00:00Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 3)
        self.assertEqual(dt.day, 15)
        self.assertEqual(dt.hour, 5)

        self.assertIsNone(scheduler.parse_session_datetime("2026-03-15", None))

    def test_format_msk_time(self):
        dt = datetime.datetime(2026, 3, 15, 5, 0, 0, tzinfo=datetime.timezone.utc)
        msk_str = scheduler.format_msk_time(dt)
        self.assertIn("15.03.2026, 08:00 МСК", msk_str)

    def test_extract_race_sessions(self):
        race_data = {
            "date": "2026-03-15",
            "time": "05:00:00Z",
            "FirstPractice": {"date": "2026-03-13", "time": "01:30:00Z"},
            "Qualifying": {"date": "2026-03-14", "time": "05:00:00Z"},
        }
        sessions = scheduler.extract_race_sessions(race_data)
        session_keys = [s[0] for s in sessions]
        self.assertIn("FirstPractice", session_keys)
        self.assertIn("Qualifying", session_keys)
        self.assertIn("Race", session_keys)

    @patch("scheduler.db")
    async def test_send_reminder_to_subscribers(self, mock_db):
        mock_db.deactivate_subscription = AsyncMock()

        bot = AsyncMock()
        # 111 succeeds, 222 blocks bot
        bot.send_message.side_effect = [None, TelegramForbiddenError(method=AsyncMock(), message="Forbidden")]

        await scheduler.send_reminder_to_subscribers(bot, [111, 222], "Test message")

        self.assertEqual(bot.send_message.await_count, 2)
        mock_db.deactivate_subscription.assert_awaited_once_with(222)

    @patch("scheduler.api_client")
    @patch("scheduler.db")
    async def test_check_and_send_reminders_trigger(self, mock_db, mock_api_client):
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        session_start = now_utc + datetime.timedelta(minutes=10)
        date_str = session_start.strftime("%Y-%m-%d")
        time_str = session_start.strftime("%H:%M:%SZ")

        mock_api_client.get_races_data = AsyncMock(return_value={
            "MRData": {
                "RaceTable": {
                    "Races": [{
                        "season": "2026",
                        "round": "1",
                        "raceName": "Australian Grand Prix",
                        "Circuit": {"Location": {"country": "Australia", "locality": "Melbourne"}},
                        "date": date_str,
                        "time": time_str
                    }]
                }
            }
        })
        mock_db.is_reminder_sent = AsyncMock(return_value=False)
        mock_db.get_matching_subscribers = AsyncMock(return_value=[999])
        mock_db.mark_reminder_sent = AsyncMock()

        bot = AsyncMock()
        await scheduler.check_and_send_reminders(bot)

        # Should send 2 messages: 1h window and 15m window
        self.assertEqual(bot.send_message.await_count, 2)
        self.assertEqual(mock_db.mark_reminder_sent.await_count, 2)


if __name__ == "__main__":
    unittest.main()
