import aiohttp
import db

session: aiohttp.ClientSession | None = None


async def init_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()


async def close_session():
    global session
    if session and not session.closed:
        await session.close()
        session = None


async def _get(url: str) -> dict:
    global session
    if session is None or session.closed:
        await init_session()
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        resp.raise_for_status()
        return await resp.json()


async def get_races_data(year: int):
    async def _fetch():
        return await _get(f"https://api.jolpi.ca/ergast/f1/{year}/races")

    if db.cache:
        return await db.cache.get_or_fetch(f"races_{year}", _fetch, ttl_hours=24)
    return await _fetch()


async def get_race_data(year: int, round_num: int):
    async def _fetch():
        return await _get(f"https://api.jolpi.ca/ergast/f1/{year}/{round_num}")

    if db.cache:
        return await db.cache.get_or_fetch(f"race_{year}_{round_num}", _fetch, ttl_hours=24)
    return await _fetch()


async def get_race_results(year: int, round_num: int):
    async def _fetch():
        return await _get(f"https://api.jolpi.ca/ergast/f1/{year}/{round_num}/results.json")

    if db.cache:
        return await db.cache.get_or_fetch(f"results_{year}_{round_num}", _fetch, ttl_hours=0.25)
    return await _fetch()


async def get_qualifying_results(year: int, round_num: int):
    async def _fetch():
        return await _get(f"https://api.jolpi.ca/ergast/f1/{year}/{round_num}/qualifying.json")

    if db.cache:
        return await db.cache.get_or_fetch(f"qualifying_{year}_{round_num}", _fetch, ttl_hours=0.25)
    return await _fetch()
