import unittest
import asyncio
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

    async def test_rate_limiter(self):
        limiter = scheduler.AsyncRateLimiter(rate=100.0, burst=2.0)
        # Should immediately acquire first 2 tokens without delay
        await limiter.acquire()
        await limiter.acquire()

    @patch("scheduler.db")
    async def test_process_campaign_deliveries_success(self, mock_db):
        mock_db.get_pending_deliveries = AsyncMock(side_effect=[
            [{"id": 1, "tg_id": 111}, {"id": 2, "tg_id": 222}],
            []
        ])
        mock_db.update_delivery_status = AsyncMock()
        mock_db.mark_campaign_completed = AsyncMock()

        bot = AsyncMock()
        limiter = scheduler.AsyncRateLimiter(rate=1000.0, burst=10.0)

        await scheduler.process_campaign_deliveries(
            bot, campaign_id=1, text="Test text", rate_limiter=limiter, batch_size=2
        )

        self.assertEqual(bot.send_message.await_count, 2)
        self.assertEqual(mock_db.update_delivery_status.await_count, 2)
        mock_db.mark_campaign_completed.assert_awaited_once_with(1)

    @patch("scheduler.db")
    async def test_process_campaign_deliveries_blocked(self, mock_db):
        mock_db.get_pending_deliveries = AsyncMock(side_effect=[
            [{"id": 1, "tg_id": 111}],
            []
        ])
        mock_db.update_delivery_status = AsyncMock()
        mock_db.deactivate_subscription = AsyncMock()
        mock_db.mark_campaign_completed = AsyncMock()

        bot = AsyncMock()
        bot.send_message.side_effect = TelegramForbiddenError(method=AsyncMock(), message="Forbidden")
        limiter = scheduler.AsyncRateLimiter(rate=1000.0, burst=10.0)

        await scheduler.process_campaign_deliveries(
            bot, campaign_id=1, text="Test text", rate_limiter=limiter
        )

        mock_db.deactivate_subscription.assert_awaited_once_with(111)
        mock_db.update_delivery_status.assert_awaited_once_with(1, "blocked", error_message="Bot blocked by user")

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
        mock_db.get_in_progress_campaigns = AsyncMock(return_value=[])
        mock_db.create_reminder_campaign = AsyncMock(side_effect=[1, 2, 3])
        mock_db.populate_campaign_deliveries = AsyncMock(return_value=1)
        mock_db.get_pending_deliveries = AsyncMock(side_effect=[
            [{"id": 1, "tg_id": 999}], [],
            [{"id": 2, "tg_id": 999}], [],
            [{"id": 3, "tg_id": 999}], [],
        ])
        mock_db.update_delivery_status = AsyncMock()
        mock_db.mark_campaign_completed = AsyncMock()

        bot = AsyncMock()
        await scheduler.check_and_send_reminders(bot)
        # Yield to let background tasks finish
        await asyncio.sleep(0.05)

        self.assertEqual(mock_db.create_reminder_campaign.await_count, 3)
        self.assertEqual(mock_db.populate_campaign_deliveries.await_count, 3)
        self.assertEqual(bot.send_message.await_count, 3)
        self.assertEqual(mock_db.mark_campaign_completed.await_count, 3)

    @patch("scheduler.api_client")
    @patch("scheduler.db")
    async def test_check_and_send_reminders_1d_only(self, mock_db, mock_api_client):
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        session_start = now_utc + datetime.timedelta(hours=12)
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
        mock_db.get_in_progress_campaigns = AsyncMock(return_value=[])
        mock_db.create_reminder_campaign = AsyncMock(return_value=1)
        mock_db.populate_campaign_deliveries = AsyncMock(return_value=1)
        mock_db.get_pending_deliveries = AsyncMock(side_effect=[
            [{"id": 1, "tg_id": 999}], []
        ])
        mock_db.update_delivery_status = AsyncMock()
        mock_db.mark_campaign_completed = AsyncMock()

        bot = AsyncMock()
        await scheduler.check_and_send_reminders(bot)
        # Yield to let background tasks finish
        await asyncio.sleep(0.05)

        # Only 1d window should trigger (12h is > 1h and <= 24h)
        self.assertEqual(mock_db.create_reminder_campaign.await_count, 1)
        mock_db.create_reminder_campaign.assert_awaited_once_with(2026, 1, "Race", "1d")
        self.assertEqual(bot.send_message.await_count, 1)
        mock_db.mark_campaign_completed.assert_awaited_once_with(1)

    @patch("scheduler.api_client")
    @patch("scheduler.db")
    async def test_check_and_send_reminders_resume_in_progress(self, mock_db, mock_api_client):
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        session_start = now_utc + datetime.timedelta(hours=5)
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
        # Simulate an in_progress campaign from prior run
        mock_db.get_in_progress_campaigns = AsyncMock(return_value=[
            {"id": 42, "season": 2026, "round": 1, "session_key": "Race", "reminder_type": "1d"}
        ])
        mock_db.create_reminder_campaign = AsyncMock(return_value=None) # Already created
        mock_db.get_pending_deliveries = AsyncMock(side_effect=[
            [{"id": 1, "tg_id": 999}], []
        ])
        mock_db.update_delivery_status = AsyncMock()
        mock_db.mark_campaign_completed = AsyncMock()

        bot = AsyncMock()
        await scheduler.check_and_send_reminders(bot)
        await asyncio.sleep(0.05)

        self.assertEqual(bot.send_message.await_count, 1)
        mock_db.mark_campaign_completed.assert_awaited_once_with(42)


if __name__ == "__main__":
    unittest.main()
