import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg


logger = logging.getLogger(__name__)


class JolpicaCache:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get(self, cache_key: str) -> dict | list | None:
        row = await self.pool.fetchrow(
            """
            SELECT payload, expires_at
            FROM fcache
            WHERE cache_key = $1
            """,
            cache_key,
        )
        if row is None:
            return None

        if row["expires_at"] <= datetime.now(timezone.utc):
            return None

        return json.loads(row["payload"])

    async def set(self, cache_key: str, payload: Any, ttl_hours: float = 6) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        await self.pool.execute(
            """
            INSERT INTO fcache (cache_key, payload, fetched_at, expires_at)
            VALUES ($1, $2::jsonb, now(), $3)
            ON CONFLICT (cache_key)
            DO UPDATE SET
                payload = EXCLUDED.payload,
                fetched_at = now(),
                expires_at = EXCLUDED.expires_at
            """,
            cache_key,
            json.dumps(payload),
            expires_at,
        )

    async def get_or_fetch(
        self,
        cache_key,
        fetch_fn,
        ttl_hours: float = 6,
    ):
        try:
            cached = await asyncio.wait_for(self.get(cache_key), timeout=2)
        except Exception:
            logger.exception("Cache read failed for %s", cache_key)
            return await fetch_fn()

        if cached is not None:
            return cached

        fresh_data = await fetch_fn()
        if fresh_data is None:
            return None

        try:
            await asyncio.wait_for(
                self.set(cache_key, fresh_data, ttl_hours),
                timeout=2,
            )
        except Exception:
            logger.exception("Cache write failed for %s", cache_key)

        return fresh_data
