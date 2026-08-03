import unittest
from unittest.mock import AsyncMock

from cache import JolpicaCache


class JolpicaCacheTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_fresh_data_when_cache_fails(self):
        cache = JolpicaCache(AsyncMock())
        cache.get = AsyncMock(side_effect=RuntimeError("cache unavailable"))
        fetch = AsyncMock(return_value={"ok": True})

        self.assertEqual(await cache.get_or_fetch("test", fetch), {"ok": True})
        fetch.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
