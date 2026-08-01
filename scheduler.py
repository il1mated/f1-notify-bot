import asyncio
import datetime
import logging
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


async def send_reminder_to_subscribers(bot: Bot, subscribers: list[int], text: str):
    if not subscribers:
        logger.info("No matching subscribers for this reminder.")
        return

    logger.info("Sending reminder to %d subscribers...", len(subscribers))
    for tg_id in subscribers:
        try:
            await bot.send_message(chat_id=tg_id, text=text, disable_web_page_preview=True)
            await asyncio.sleep(0.05)
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


async def check_and_send_reminders(bot: Bot):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    current_year = now_utc.year

    races_data = await api_client.get_races_data(current_year)
    if not races_data:
        return

    races = races_data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    for race in races:
        season = int(race.get("season", current_year))
        round_num = int(race.get("round", 0))
        race_name = race.get("raceName", "Гран-при")
        country = race.get("Circuit", {}).get("Location", {}).get("country", "")
        locality = race.get("Circuit", {}).get("Location", {}).get("locality", "")
        flag = COUNTRY_FLAGS.get(country, "🏎")

        sessions = extract_race_sessions(race)
        for session_key, session_dt in sessions:
            time_until_session = (session_dt - now_utc).total_seconds()

            # Windows to evaluate
            windows = []
            if 0 <= time_until_session <= 3600:
                windows.append(("1h", "через 1 час"))
            if 0 <= time_until_session <= 900:
                windows.append(("15m", "через 15 минут"))

            for reminder_type, time_label in windows:
                already_sent = await db.is_reminder_sent(season, round_num, session_key, reminder_type)
                if not already_sent:
                    subscribers = await db.get_matching_subscribers(session_key, reminder_type)
                    if subscribers:
                        session_title = SESSION_TITLES.get(session_key, session_key)
                        msk_time = format_msk_time(session_dt)

                        text = (
                            f"⏰ <b>Напоминание о F1!</b>\n\n"
                            f"{flag} <b>{race_name}</b>\n"
                            f"📍 {locality}, {country}\n"
                            f"🏎 Сессия: <b>{session_title}</b>\n"
                            f"📅 Начало: <b>{msk_time}</b> ({time_label})\n"
                        )

                        await send_reminder_to_subscribers(bot, subscribers, text)
                    await db.mark_reminder_sent(season, round_num, session_key, reminder_type)


async def start_reminder_scheduler(bot: Bot, check_interval: int = 60):
    logger.info("F1 Reminder Scheduler started.")
    while True:
        try:
            await check_and_send_reminders(bot)
        except asyncio.CancelledError:
            logger.info("F1 Reminder Scheduler cancelled.")
            break
        except Exception:
            logger.exception("Error in reminder scheduler loop.")

        await asyncio.sleep(check_interval)
