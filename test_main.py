import unittest
from unittest.mock import AsyncMock, patch, MagicMock

import main


class MainHandlersTest(unittest.IsolatedAsyncioTestCase):
    @patch("main.db")
    async def test_get_notifications_text_and_markup_single(self, mock_db):
        mock_db.get_user = AsyncMock(return_value={
            "is_subscribed": True,
            "notify_timing": "1h",
            "notify_sessions": "main",
        })

        text, markup = await main.get_notifications_text_and_markup(12345)
        self.assertIn("Подписаны", text)
        self.assertIn("За 1 час", text)

        # Check buttons
        button_texts = [btn.text for row in markup.inline_keyboard for btn in row]
        self.assertIn("✅ ⏱ 1 час", button_texts)
        self.assertIn("⏱ 1 день", button_texts)
        self.assertIn("⏱ 15 мин", button_texts)
        self.assertNotIn("⏱ 1ч + 15мин", button_texts)

    @patch("main.db")
    async def test_get_notifications_text_and_markup_multi(self, mock_db):
        mock_db.get_user = AsyncMock(return_value={
            "is_subscribed": True,
            "notify_timing": "1d,15m",
            "notify_sessions": "all",
        })

        text, markup = await main.get_notifications_text_and_markup(12345)
        self.assertIn("За 1 день, За 15 минут", text)

        button_texts = [btn.text for row in markup.inline_keyboard for btn in row]
        self.assertIn("✅ ⏱ 1 день", button_texts)
        self.assertIn("⏱ 1 час", button_texts)
        self.assertIn("✅ ⏱ 15 мин", button_texts)

    @patch("main.db")
    async def test_set_timing_toggle_on(self, mock_db):
        mock_db.get_user = AsyncMock(return_value={
            "is_subscribed": True,
            "notify_timing": "1h",
            "notify_sessions": "main",
        })
        mock_db.update_user_settings = AsyncMock()

        callback = MagicMock()
        callback.from_user.id = 12345
        callback.data = "set_timing:1d"
        callback.answer = AsyncMock()
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()

        await main.set_timing(callback)

        mock_db.update_user_settings.assert_awaited_once_with(12345, notify_timing="1d,1h")
        callback.answer.assert_awaited_once()

    @patch("main.db")
    async def test_set_timing_toggle_off(self, mock_db):
        mock_db.get_user = AsyncMock(return_value={
            "is_subscribed": True,
            "notify_timing": "1d,1h",
            "notify_sessions": "main",
        })
        mock_db.update_user_settings = AsyncMock()

        callback = MagicMock()
        callback.from_user.id = 12345
        callback.data = "set_timing:1d"
        callback.answer = AsyncMock()
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()

        await main.set_timing(callback)

        mock_db.update_user_settings.assert_awaited_once_with(12345, notify_timing="1h")

    @patch("main.db")
    async def test_set_timing_prevent_empty(self, mock_db):
        mock_db.get_user = AsyncMock(return_value={
            "is_subscribed": True,
            "notify_timing": "1h",
            "notify_sessions": "main",
        })
        mock_db.update_user_settings = AsyncMock()

        callback = MagicMock()
        callback.from_user.id = 12345
        callback.data = "set_timing:1h"
        callback.answer = AsyncMock()
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()

        await main.set_timing(callback)

        mock_db.update_user_settings.assert_not_awaited()
        callback.answer.assert_awaited_once_with("Выберите хотя бы один вариант времени", show_alert=True)


if __name__ == "__main__":
    unittest.main()
