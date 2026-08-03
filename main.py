import asyncio
import os
import logging
import datetime
from dotenv import load_dotenv
from aiohttp import web

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F, Router, Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode, ButtonStyle
from aiogram.client.default import DefaultBotProperties
from aiogram.filters.callback_data import CallbackData

import db
import scheduler
import api_client
from constants import (
    COUNTRY_FLAGS,
    TIMING_LABELS,
    SESSIONS_LABELS,
    ALLOWED_TIMINGS,
    ALLOWED_SESSIONS,
)
from utils import format_session_datetime, check_race_status

load_dotenv()

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


def get_main_menu_text_and_markup():
    builder = InlineKeyboardBuilder()
    builder.button(text="Расписание", callback_data="races")
    builder.button(text="Напоминания о гонках", callback_data="notifications", style=ButtonStyle.PRIMARY)
    builder.button(text="Помощь", callback_data="help")
    builder.adjust(1)
    return "Привет!", builder.as_markup()


class RaceCallback(CallbackData, prefix="race"):
    round: int


class RaceResultsCallback(CallbackData, prefix="race_res"):
    round: int


class QualiResultsCallback(CallbackData, prefix="quali_res"):
    round: int


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    if user:
        exists = await db.check_user(user.id)
        if not exists:
            created = await db.create_user(user.username, user.first_name, user.last_name, user.id)
            print(f"Зареган ли юзер: {created}")

    text, markup = get_main_menu_text_and_markup()
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "races")
async def get_races(callback: types.CallbackQuery):
    data = await api_client.get_races_data(datetime.date.today().year)
    if data is None:
        await callback.answer("Ошибка при загрузке данных, попробуйте позже", show_alert=True)
        return
    races = data["MRData"]["RaceTable"]["Races"]
    print(races)
    builder = InlineKeyboardBuilder()
    for race in races:
        status = check_race_status(race["date"], race.get("time"))
        if status == "🏁":
            style = ButtonStyle.DANGER
        elif status == "🟢":
            style = ButtonStyle.SUCCESS
        else:
            style = None

        flag = COUNTRY_FLAGS.get(race["Circuit"]["Location"]["country"], "")
        builder.button(
            text=f" {status} {flag} {race['Circuit']['Location']['locality']} ",
            callback_data=RaceCallback(round=int(race["round"])),
            style=style
        )
    await callback.answer("")

    if callback.message:
        builder.adjust(3)
        builder.button(text="В меню", callback_data="to_menu")
        builder.adjust(3, 3, 3, 3, 3, 3, 3, 1)

        await callback.message.edit_text("Гран-при этого сезона:", reply_markup=builder.as_markup())


@router.callback_query(RaceCallback.filter())
async def get_race_details(callback: types.CallbackQuery, callback_data: RaceCallback):
    round_number = callback_data.round
    data = await api_client.get_race_data(datetime.date.today().year, round_number)
    if data is None:
        await callback.answer("Ошибка при загрузке данных, попробуйте позже", show_alert=True)
        return
    races = data["MRData"]["RaceTable"]["Races"]

    if not races:
        await callback.answer("Гонка не найдена", show_alert=True)
        return

    race = races[0]

    location = race["Circuit"]["Location"]
    circuit = race["Circuit"]
    text = (
        f"🏁 <a href='{race['url']}'>{race['raceName']}</a>\n"
        f"📍 {location['locality']}, {location['country']}\n"
        f"🏟 <a href='{circuit['url']}'>{circuit['circuitName']}</a>\n"
        f"📅 Гонка: {format_session_datetime(race['date'], race.get('time'))}\n"
    )

    sessions = [
        ("🟢 FP1", race.get("FirstPractice")),
        ("🟡 FP2", race.get("SecondPractice")),
        ("🟠 FP3", race.get("ThirdPractice")),
        ("🔴 Спринт-квалификация", race.get("SprintQualifying")),
        ("🏎 Спринт", race.get("Sprint")),
        ("🔵 Квалификация", race.get("Qualifying")),
    ]

    session_lines = []
    for label, session in sessions:
        if session:
            session_lines.append(f"{label}: {format_session_datetime(session['date'], session.get('time'))}")

    if session_lines:
        text += "\n" + "\n".join(session_lines)

    builder = InlineKeyboardBuilder()
    if check_race_status(race["date"], race.get("time")) == "🏁":
        builder.button(text="Результаты гонки", callback_data=RaceResultsCallback(round=round_number), style=ButtonStyle.SUCCESS)
        builder.button(text="Результаты квалификации", callback_data=QualiResultsCallback(round=round_number), style=ButtonStyle.PRIMARY)
    builder.button(text="Назад", callback_data="races")
    builder.adjust(1)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    await callback.answer()


@router.callback_query(RaceResultsCallback.filter())
async def get_race_results_handler(callback: types.CallbackQuery, callback_data: RaceResultsCallback):
    round_number = callback_data.round
    data = await api_client.get_race_results(datetime.date.today().year, round_number)
    if data is None:
        await callback.answer("Ошибка при загрузке данных, попробуйте позже", show_alert=True)
        return
    races = data["MRData"]["RaceTable"]["Races"]

    if not races or not races[0].get("Results"):
        await callback.answer("Результаты ещё не доступны", show_alert=True)
        return

    race = races[0]
    results = race["Results"]

    text = f"🏆 Результаты: {race['raceName']}\n\n"
    for result in results[:10]:  # пока только топ10
        position = result["position"]
        driver = result["Driver"]
        driver_name = f"{driver['givenName']} {driver['familyName']}"
        constructor = result["Constructor"]["name"]
        time_info = result.get("Time", {}).get("time") or result.get("status", "")
        text += f"<b>{position}. {driver_name}</b> ({constructor}) — {time_info}\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data=RaceCallback(round=round_number))
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(QualiResultsCallback.filter())
async def get_qualifying_results_handler(callback: types.CallbackQuery, callback_data: QualiResultsCallback):
    round_number = callback_data.round
    data = await api_client.get_qualifying_results(datetime.date.today().year, round_number)
    if data is None:
        await callback.answer("Ошибка при загрузке данных, попробуйте позже", show_alert=True)
        return
    races = data["MRData"]["RaceTable"]["Races"]

    if not races or not races[0].get("QualifyingResults"):
        await callback.answer("Результаты квалификации ещё не доступны", show_alert=True)
        return

    race = races[0]
    results = race["QualifyingResults"]

    text = f"⏱ Квалификация: {race['raceName']}\n\n"
    for result in results:
        position = result["position"]
        driver = result["Driver"]
        driver_name = f"{driver['givenName']} {driver['familyName']}"
        q3 = result.get("Q3") or result.get("Q2") or result.get("Q1", "")
        text += f"<b>{position}. {driver_name} </b> — {q3}\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data=RaceCallback(round=round_number))
    builder.adjust(1)

    if callback.message:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data == "to_menu")
async def to_menu(callback: types.CallbackQuery):
    text, markup = get_main_menu_text_and_markup()
    await callback.answer("")
    if callback.message:
        await callback.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "help")
async def help_handler(callback: types.CallbackQuery):
    await callback.answer("")
    if callback.message:
        await callback.message.answer("бог поможет")


async def get_notifications_text_and_markup(tg_id: int):
    user_data = await db.get_user(tg_id)
    if not user_data:
        builder = InlineKeyboardBuilder()
        builder.button(text="В меню", callback_data="to_menu")
        return "Пользователь не найден. Нажмите /start", builder.as_markup()

    is_subscribed = user_data.get("is_subscribed", False)
    notify_timing = user_data.get("notify_timing", "1h")
    notify_sessions = user_data.get("notify_sessions", "main")

    status_str = "<b>Подписаны</b> 🔔" if is_subscribed else "<b>Не подписаны</b> 🔕"
    timing_str = TIMING_LABELS.get(notify_timing, notify_timing)
    sessions_str = SESSIONS_LABELS.get(notify_sessions, notify_sessions)

    text = (
        f"⚙️ <b>Настройки уведомлений</b>\n\n"
        f"Статус: {status_str}\n"
        f"⏱ Время: <b>{timing_str}</b>\n"
        f"🏎 Сессии: <b>{sessions_str}</b>\n\n"
        f"<i>Нажмите кнопки ниже для изменения настроек:</i>"
    )

    builder = InlineKeyboardBuilder()

    if is_subscribed:
        builder.button(text="🔴 Отписаться от уведомлений", callback_data="unsubscribe", style=ButtonStyle.DANGER)
    else:
        builder.button(text="🟢 Подписаться на уведомления", callback_data="subscribe", style=ButtonStyle.SUCCESS)

    timing_1h_mark = "✅ " if notify_timing == "1h" else ""
    timing_15m_mark = "✅ " if notify_timing == "15m" else ""
    timing_both_mark = "✅ " if notify_timing == "both" else ""

    builder.button(text=f"{timing_1h_mark}⏱ 1 час", callback_data="set_timing:1h")
    builder.button(text=f"{timing_15m_mark}⏱ 15 мин", callback_data="set_timing:15m")
    builder.button(text=f"{timing_both_mark}⏱ 1ч + 15мин", callback_data="set_timing:both")

    sess_main_mark = "✅ " if notify_sessions == "main" else ""
    sess_all_mark = "✅ " if notify_sessions == "all" else ""

    builder.button(text=f"{sess_main_mark}🏎 Важные", callback_data="set_sessions:main")
    builder.button(text=f"{sess_all_mark}🏁 Все сессии", callback_data="set_sessions:all")

    builder.button(text="🔙 В меню", callback_data="to_menu")

    builder.adjust(1, 3, 2, 1)
    return text, builder.as_markup()


@router.callback_query(F.data == "notifications")
async def user_notifications(callback: types.CallbackQuery):
    user = callback.from_user
    text, markup = await get_notifications_text_and_markup(user.id)
    await callback.answer("")
    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "subscribe")
async def subscribe(callback: types.CallbackQuery):
    user = callback.from_user
    await db.set_subscription(user.id, True)
    text, markup = await get_notifications_text_and_markup(user.id)
    await callback.answer("Вы подписались на уведомления")
    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "unsubscribe")
async def unsubscribe(callback: types.CallbackQuery):
    user = callback.from_user
    await db.set_subscription(user.id, False)
    text, markup = await get_notifications_text_and_markup(user.id)
    await callback.answer("Вы отписались от уведомлений")
    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("set_timing:"))
async def set_timing(callback: types.CallbackQuery):
    user = callback.from_user
    timing = callback.data.split(":")[1]
    if timing not in ALLOWED_TIMINGS:
        await callback.answer("Некорректное значение времени", show_alert=True)
        return
    await db.update_user_settings(user.id, notify_timing=timing)
    text, markup = await get_notifications_text_and_markup(user.id)
    await callback.answer(f"Время: {TIMING_LABELS.get(timing)}")
    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("set_sessions:"))
async def set_sessions(callback: types.CallbackQuery):
    user = callback.from_user
    sessions = callback.data.split(":")[1]
    if sessions not in ALLOWED_SESSIONS:
        await callback.answer("Некорректное значение сессий", show_alert=True)
        return
    await db.update_user_settings(user.id, notify_sessions=sessions)
    text, markup = await get_notifications_text_and_markup(user.id)
    await callback.answer("Виды сессий обновлены")
    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def main():
    await db.init_pool()
    await api_client.init_session()

    logging.basicConfig(level=logging.INFO)

    # Start health-check HTTP server
    health_app = web.AppRunner(web.Application())
    health_app.app.router.add_get("/health", health_handler)
    await health_app.setup()
    site = web.TCPSite(health_app, "0.0.0.0", int(os.getenv("PORT", "8080")))
    await site.start()
    logging.info("Health endpoint listening on port %s", os.getenv("PORT", "8080"))

    scheduler_task = asyncio.create_task(scheduler.start_reminder_scheduler(bot))
    try:
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()
        await health_app.cleanup()
        await api_client.close_session()
        await db.close_pool()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
