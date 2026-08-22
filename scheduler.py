import asyncio
from asyncio import Event
import datetime
import logging
import time
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
import db
import api_client
from constants import COUNTRY_FLAGS, SESSION_TITLES
from utils import (
    parse_session_datetime,
    format_msk_time,
    extract_race_sessions,
)

logger = logging.getLogger(__name__)


class AsyncRateLimiter:
    """Token bucket rate limiter to control outgoing Telegram API calls."""
    def __init__(self, rate: float = 25.0, burst: float = 25.0):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.burst, self.tokens + elapsed * self.rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait_time = (1.0 - self.tokens) / self.rate
            await asyncio.sleep(wait_time)


global_rate_limiter = AsyncRateLimiter(rate=25.0, burst=25.0)


def build_reminder_text(
    race_name: str,
    country: str,
    locality: str,
    session_key: str,
    session_dt: datetime.datetime,
    time_label: str,
) -> str:
    flag = COUNTRY_FLAGS.get(country, "🏎")
    session_title = SESSION_TITLES.get(session_key, session_key)
    msk_time = format_msk_time(session_dt)
    return (
        f"⏰ <b>Напоминание о F1!</b>\n\n"
        f"{flag} <b>{race_name}</b>\n"
        f"📍 {locality}, {country}\n"
        f"🏎 Сессия: <b>{session_title}</b>\n"
        f"📅 Начало: <b>{msk_time}</b> ({time_label})\n"
    )


async def process_campaign_deliveries(
    bot: Bot,
    campaign_id: int,
    text: str,
    rate_limiter: AsyncRateLimiter | None = None,
    concurrency: int = 10,
    batch_size: int = 500,
):
    limiter = rate_limiter or global_rate_limiter
    semaphore = asyncio.Semaphore(concurrency)

    async def send_single(delivery: dict):
        delivery_id = delivery["id"]
        tg_id = delivery["tg_id"]
        async with semaphore:
            await limiter.acquire()
            try:
                await bot.send_message(chat_id=tg_id, text=text, disable_web_page_preview=True)
                await db.update_delivery_status(delivery_id, "sent")
            except TelegramForbiddenError:
                logger.info("User %s blocked the bot. Deactivating subscription.", tg_id)
                await db.update_delivery_status(delivery_id, "blocked", error_message="Bot blocked by user")
                await db.deactivate_subscription(tg_id)
            except TelegramRetryAfter as e:
                logger.warning("Rate limited by Telegram for %s. Waiting %s seconds.", tg_id, e.retry_after)
                await asyncio.sleep(e.retry_after)
                await limiter.acquire()
                try:
                    await bot.send_message(chat_id=tg_id, text=text, disable_web_page_preview=True)
                    await db.update_delivery_status(delivery_id, "sent")
                except Exception as retry_err:
                    logger.error("Failed to resend message to %s: %s", tg_id, retry_err)
                    await db.update_delivery_status(delivery_id, "failed", error_message=str(retry_err))
            except TelegramAPIError as e:
                logger.error("Telegram API error sending to %s: %s", tg_id, e)
                await db.update_delivery_status(delivery_id, "failed", error_message=str(e))
            except Exception as e:
                logger.error("Unexpected error sending to %s: %s", tg_id, e)
                await db.update_delivery_status(delivery_id, "failed", error_message=str(e))

    try:
        while True:
            pending_batch = await db.get_pending_deliveries(campaign_id, limit=batch_size)
            if not pending_batch:
                break

            tasks = [asyncio.create_task(send_single(item)) for item in pending_batch]
            await asyncio.gather(*tasks)

        await db.mark_campaign_completed(campaign_id)
        logger.info("Campaign %d completed successfully.", campaign_id)
    except Exception as e:
        logger.error("Error processing deliveries for campaign %d: %s", campaign_id, e)


async def send_reminder_to_subscribers(bot: Bot, subscribers: list[int], text: str):
    """Legacy helper for direct subscriber list sending."""
    if not subscribers:
        logger.info("No matching subscribers for this reminder.")
        return

    logger.info("Sending reminder to %d subscribers...", len(subscribers))
    semaphore = asyncio.Semaphore(10)

    async def send_single(tg_id: int):
        async with semaphore:
            await global_rate_limiter.acquire()
            try:
                await bot.send_message(chat_id=tg_id, text=text, disable_web_page_preview=True)
            except TelegramForbiddenError:
                logger.info("User %s blocked the bot. Deactivating subscription.", tg_id)
                await db.deactivate_subscription(tg_id)
            except TelegramRetryAfter as e:
                logger.warning("Rate limited by Telegram. Waiting %s seconds.", e.retry_after)
                await asyncio.sleep(e.retry_after)
                try:
                    await bot.send_message(chat_id=tg_id, text=text, disable_web_page_preview=True)
                except Exception as retry_err:
                    logger.error("Failed to resend message to %s: %s", tg_id, retry_err)
            except TelegramAPIError as e:
                logger.error("Telegram API error sending to %s: %s", tg_id, e)
            except Exception as e:
                logger.error("Unexpected error sending to %s: %s", tg_id, e)

    tasks = [asyncio.create_task(send_single(tg_id)) for tg_id in subscribers]
    await asyncio.gather(*tasks)


async def check_and_send_reminders(bot: Bot):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    current_year = now_utc.year

    races_data = await api_client.get_races_data(current_year)
    if not races_data:
        return

    races = races_data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    sessions_map = {}

    for race in races:
        season = int(race.get("season", current_year))
        round_num = int(race.get("round", 0))
        race_name = race.get("raceName", "Гран-при")
        country = race.get("Circuit", {}).get("Location", {}).get("country", "")
        locality = race.get("Circuit", {}).get("Location", {}).get("locality", "")

        sessions = extract_race_sessions(race)
        for session_key, session_dt in sessions:
            sessions_map[(season, round_num, session_key)] = {
                "race_name": race_name,
                "country": country,
                "locality": locality,
                "session_dt": session_dt,
            }

            time_until_session = (session_dt - now_utc).total_seconds()

            # Windows to evaluate
            windows = []
            if 0 <= time_until_session <= 86400:
                windows.append(("1d", "через 1 день"))
            if 0 <= time_until_session <= 3600:
                windows.append(("1h", "через 1 час"))
            if 0 <= time_until_session <= 900:
                windows.append(("15m", "через 15 минут"))

            for reminder_type, time_label in windows:
                campaign_id = await db.create_reminder_campaign(season, round_num, session_key, reminder_type)
                if campaign_id is not None:
                    count = await db.populate_campaign_deliveries(campaign_id, reminder_type, session_key)
                    if count > 0:
                        text = build_reminder_text(race_name, country, locality, session_key, session_dt, time_label)
                        asyncio.create_task(
                            process_campaign_deliveries(bot, campaign_id, text)
                        )
                    else:
                        await db.mark_campaign_completed(campaign_id)

    # Check and resume any interrupted campaigns
    in_progress = await db.get_in_progress_campaigns()
    if in_progress:
        for camp in in_progress:
            camp_id = camp["id"]
            key = (camp["season"], camp["round"], camp["session_key"])
            info = sessions_map.get(key)
            if info:
                time_label = "скоро"
                if camp["reminder_type"] == "1d":
                    time_label = "через 1 день"
                elif camp["reminder_type"] == "1h":
                    time_label = "через 1 час"
                elif camp["reminder_type"] == "15m":
                    time_label = "через 15 минут"

                text = build_reminder_text(
                    info["race_name"], info["country"], info["locality"],
                    camp["session_key"], info["session_dt"], time_label
                )
                asyncio.create_task(
                    process_campaign_deliveries(bot, camp_id, text)
                )


async def start_reminder_scheduler(
    bot: Bot,
    check_interval: int = 60,
    polling_healthy: Event | None = None,
):
    logger.info("F1 Reminder Scheduler started.")
    while True:
        try:
            # If polling health tracking is enabled, skip work while polling is unhealthy
            # (e.g. stuck in TelegramConflictError retry loop)
            if polling_healthy is not None and not polling_healthy.is_set():
                logger.warning(
                    "Polling is unhealthy — scheduler skipping this cycle."
                )
            else:
                await check_and_send_reminders(bot)
        except asyncio.CancelledError:
            logger.info("F1 Reminder Scheduler cancelled.")
            break
        except Exception:
            logger.exception("Error in reminder scheduler loop.")

        await asyncio.sleep(check_interval)
