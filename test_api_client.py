import unittest
from unittest.mock import AsyncMock, patch

import api_client


class ApiClientTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await api_client.init_session()

    async def asyncTearDown(self):
        await api_client.close_session()

    @patch("api_client.db")
    async def test_get_races_data_calls_fetch_when_no_cache(self, mock_db):
        mock_db.cache = None
        with patch("api_client._get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"races": []}
            res = await api_client.get_races_data(2026)
            self.assertEqual(res, {"races": []})
            mock_get.assert_awaited_once_with("https://api.jolpi.ca/ergast/f1/2026/races")

    @patch("api_client.db")
    async def test_get_race_data_uses_cache(self, mock_db):
        mock_cache = AsyncMock()
        mock_cache.get_or_fetch.return_value = {"race": 1}
        mock_db.cache = mock_cache

        res = await api_client.get_race_data(2026, 1)
        self.assertEqual(res, {"race": 1})
        mock_cache.get_or_fetch.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
