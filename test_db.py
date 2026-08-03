import unittest
from unittest.mock import AsyncMock

import asyncpg

import db


class SubscriptionTest(unittest.IsolatedAsyncioTestCase):
    async def test_reconnects_and_sets_requested_state(self):
        db.pool = AsyncMock()
        db.pool.fetchrow.side_effect = [
            asyncpg.ConnectionDoesNotExistError("closed"),
            {"is_subscribed": True},
        ]

        self.assertTrue(await db.set_subscription(42, True))
        self.assertEqual(db.pool.fetchrow.await_count, 2)

    async def test_get_subscribed_user_ids(self):
        db.pool = AsyncMock()
        db.pool.fetch.return_value = [{"tg_id": 100}, {"tg_id": 200}]
        subscribed = await db.get_subscribed_user_ids()
        self.assertEqual(subscribed, [100, 200])

    async def test_is_reminder_sent(self):
        db.pool = AsyncMock()
        db.pool.fetchrow.return_value = {"1": 1}
        self.assertTrue(await db.is_reminder_sent(2026, 1, "Race", "1h"))

        db.pool.fetchrow.return_value = None
        self.assertFalse(await db.is_reminder_sent(2026, 1, "Race", "1h"))

    async def test_mark_reminder_sent(self):
        db.pool = AsyncMock()
        await db.mark_reminder_sent(2026, 1, "Race", "1h")
        db.pool.execute.assert_awaited_once()

    async def test_deactivate_subscription(self):
        db.pool = AsyncMock()
        await db.deactivate_subscription(12345)
        db.pool.execute.assert_awaited_once_with(
            "UPDATE users SET is_subscribed = FALSE WHERE tg_id = $1", 12345
        )

    async def test_update_user_settings(self):
        db.pool = AsyncMock()
        await db.update_user_settings(100, notify_timing="15m", notify_sessions="all")
        self.assertEqual(db.pool.execute.await_count, 2)

    async def test_get_matching_subscribers(self):
        db.pool = AsyncMock()
        db.pool.fetch.return_value = [{"tg_id": 100}]
        subscribers = await db.get_matching_subscribers("Race", "1h")
        self.assertEqual(subscribers, [100])


if __name__ == "__main__":
    unittest.main()
