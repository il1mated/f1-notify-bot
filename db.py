import os
from dotenv import load_dotenv
import asyncpg
from cache import JolpicaCache
import api_client

load_dotenv()

pool: asyncpg.Pool | None = None
cache: JolpicaCache | None = None


async def init_pool():
    global pool, cache
    pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        ssl="require",
        statement_cache_size=0,
        max_inactive_connection_lifetime=300,  # закрывать неиспользуемые соединения через 5 мин, пока сами не протухли
        command_timeout=10,
    )
    cache = JolpicaCache(pool)
    await init_db()


async def close_pool():
    if pool:
        await pool.close()


async def init_db():
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            tg_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_subscribed BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    await pool.execute("""
    CREATE TABLE IF NOT EXISTS fcache (
    cache_key TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
    )
    """)
    await pool.execute("""
    CREATE TABLE IF NOT EXISTS sent_reminders (
        id BIGSERIAL PRIMARY KEY,
        season INT NOT NULL,
        round INT NOT NULL,
        session_key TEXT NOT NULL,
        reminder_type TEXT NOT NULL,
        sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (season, round, session_key, reminder_type)
    )
    """)
    await pool.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_timing TEXT NOT NULL DEFAULT '1h'")
    await pool.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_sessions TEXT NOT NULL DEFAULT 'main'")


async def check_user(tg_id):
    rows = await pool.fetch("SELECT 1 FROM users WHERE tg_id = $1", tg_id)
    return len(rows) > 0


async def create_user(username, first_name, last_name, tg_id):
    try:
        await pool.execute(
            """
            INSERT INTO users (tg_id, username, first_name, last_name)
            VALUES ($1, $2, $3, $4)
            """,
            tg_id, username, first_name, last_name
        )
        return True

    except asyncpg.UniqueViolationError:
        print(f"User with tg_id={tg_id} already exists")
        return False

    except asyncpg.PostgresError as e:
        print(f"DB error while creating user tg_id={tg_id}: {e}")
        raise

    except Exception as e:
        print(f"Unexpected error while creating user tg_id={tg_id}: {e}")
        raise


async def get_all_user_ids():
    try:
        rows = await pool.fetch("SELECT tg_id FROM users")
        return [row["tg_id"] for row in rows]

    except asyncpg.PostgresError as e:
        print(f"DB error while getting user_ids: {e}")
        raise

    except Exception as e:
        print(f"Unexpected error while checking users: {e}")
        raise


async def get_subscribed_user_ids():
    try:
        rows = await pool.fetch("SELECT tg_id FROM users WHERE is_subscribed = TRUE")
        return [row["tg_id"] for row in rows]
    except asyncpg.PostgresError as e:
        print(f"DB error while getting subscribed user_ids: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error while getting subscribed users: {e}")
        raise


async def is_reminder_sent(season: int, round_num: int, session_key: str, reminder_type: str) -> bool:
    try:
        row = await pool.fetchrow(
            """
            SELECT 1 FROM sent_reminders
            WHERE season = $1 AND round = $2 AND session_key = $3 AND reminder_type = $4
            """,
            season, round_num, session_key, reminder_type
        )
        return row is not None
    except asyncpg.PostgresError as e:
        print(f"DB error while checking sent reminder: {e}")
        return False


async def mark_reminder_sent(season: int, round_num: int, session_key: str, reminder_type: str):
    try:
        await pool.execute(
            """
            INSERT INTO sent_reminders (season, round, session_key, reminder_type)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (season, round, session_key, reminder_type) DO NOTHING
            """,
            season, round_num, session_key, reminder_type
        )
    except asyncpg.PostgresError as e:
        print(f"DB error while marking reminder sent: {e}")


async def deactivate_subscription(tg_id: int):
    try:
        await pool.execute(
            "UPDATE users SET is_subscribed = FALSE WHERE tg_id = $1", tg_id
        )
    except asyncpg.PostgresError as e:
        print(f"DB error while deactivating subscription for tg_id={tg_id}: {e}")


async def update_user_settings(tg_id: int, notify_timing: str | None = None, notify_sessions: str | None = None):
    try:
        if notify_timing is not None:
            await pool.execute("UPDATE users SET notify_timing = $2 WHERE tg_id = $1", tg_id, notify_timing)
        if notify_sessions is not None:
            await pool.execute("UPDATE users SET notify_sessions = $2 WHERE tg_id = $1", tg_id, notify_sessions)
    except asyncpg.PostgresError as e:
        print(f"DB error while updating user settings for tg_id={tg_id}: {e}")
        raise


async def get_matching_subscribers(session_key: str, reminder_type: str) -> list[int]:
    try:
        rows = await pool.fetch(
            """
            SELECT tg_id FROM users
            WHERE is_subscribed = TRUE
              AND (notify_timing = 'both' OR notify_timing = $1)
              AND (
                notify_sessions = 'all'
                OR (notify_sessions = 'main' AND $2 = ANY(ARRAY['Qualifying', 'SprintQualifying', 'Sprint', 'Race']))
              )
            """,
            reminder_type,
            session_key
        )
        return [row["tg_id"] for row in rows]
    except asyncpg.PostgresError as e:
        print(f"DB error while getting matching subscribers: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error while getting matching subscribers: {e}")
        return []


async def get_user(tg_id):
    try:
        row = await pool.fetchrow("SELECT * FROM users WHERE tg_id = $1", tg_id)
        return row

    except asyncpg.PostgresError as e:
        print(f"DB error while getting user: {e}")
        raise

    except Exception as e:
        print(f"Unexpected error while getting user: {e}")
        raise


async def set_subscription(user_id, is_subscribed):
    for attempt in range(2):
        try:
            row = await pool.fetchrow(
                """
                UPDATE users
                SET is_subscribed = $2
                WHERE tg_id = $1
                RETURNING is_subscribed
                """,
                user_id,
                is_subscribed,
            )
            return row["is_subscribed"] if row else None
        except asyncpg.ConnectionDoesNotExistError:
            if attempt:
                raise


# Delegated API calls for backwards compatibility
async def get_races_data(year):
    return await api_client.get_races_data(year)


async def get_race_data(year, round):
    return await api_client.get_race_data(year, round)


async def get_race_results(year, round):
    return await api_client.get_race_results(year, round)


async def get_qualifying_results(year, round):
    return await api_client.get_qualifying_results(year, round)
