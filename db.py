import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
dsn=os.getenv("dsn")


pool: asyncpg.Pool | None = None

async def init_pool():
    global pool
    pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        ssl="require",
        statement_cache_size=0,
    )

async def close_pool():
    await pool.close()

async def init_db():
    await pool.execute("CREATE TABLE IF NOT EXISTS users"
                       "(id BIGSERIAL PRIMARY KEY,"
                       "tg_id BIGINT UNIQUE NOT NULL,"
                       "username TEXT NOT NULL,"
                       "first_name TEXT"
                       "last_name TEXT"
                       "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                       "notifications BOOLEAN NOT NULL DEFAULT FALSE,)")
    await pool.execute("CREATE INDEX idx_users_tg_id ON users(tg_id)")

async def check_user(username):
    rows = await pool.fetch("SELECT 1 FROM users WHERE username = $1", username)
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

async def switch_subscription(user_id):
    try:
        await pool.execute("UPDATE users SET is_subscribed = NOT is_subscribed WHERE tg_id = $1", user_id)
        return True
    except asyncpg.PostgresError as e:
        print(f"DB error while getting user: {e}")
        raise

    except Exception as e:
        print(f"Unexpected error while getting user: {e}")
        raise