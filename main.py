import asyncio
import os
from dotenv import load_dotenv
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F
from aiogram import Router
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode, ButtonStyle
from aiogram.client.default import DefaultBotProperties
from aiogram.filters.callback_data import CallbackData
import logging
import api
import datetime

load_dotenv()

TOKEN = os.getenv("TOKEN")

COUNTRY_FLAGS = {
    "Australia": "🇦🇺",
    "China": "🇨🇳",
    "Japan": "🇯🇵",
    "Bahrain": "🇧🇭",
    "Saudi Arabia": "🇸🇦",
    "USA": "🇺🇸",
    "Italy": "🇮🇹",
    "Monaco": "🇲🇨",
    "Canada": "🇨🇦",
    "Spain": "🇪🇸",
    "Austria": "🇦🇹",
    "UK": "🇬🇧",
    "Belgium": "🇧🇪",
    "Hungary": "🇭🇺",
    "Netherlands": "🇳🇱",
    "Azerbaijan": "🇦🇿",
    "Singapore": "🇸🇬",
    "Mexico": "🇲🇽",
    "Brazil": "🇧🇷",
    "Qatar": "🇶🇦",
    "UAE": "🇦🇪",
}

MSK = datetime.timezone(datetime.timedelta(hours=3))
def format_session_datetime(date_str: str, time_str: str | None) -> str:
    if not time_str:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")

    dt = datetime.datetime.fromisoformat(
        f"{date_str}T{time_str.replace('Z', '+00:00')}"
    ).astimezone(MSK)
    return dt.strftime("%d.%m.%Y, %H:%M МСК")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

def get_main_menu_text_and_markup():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Расписание", callback_data="races")
    builder.button(text="Помощь", callback_data="help")
    builder.adjust(1)
    return "Привет!", builder.as_markup()

def check_race_status(date, time):
    dt_str = f"{date}T{time.replace('Z', '+00:00')}"
    event_dt = datetime.datetime.fromisoformat(dt_str)
    delta = datetime.datetime.now(datetime.timezone.utc) - event_dt

    if delta.total_seconds() < 0:
        return ""
    elif delta < datetime.timedelta(hours=2):
        return "🟢"
    else:
        return "🏁"


class RaceCallback(CallbackData, prefix="race"):
    round: int

class RaceResultsCallback(CallbackData, prefix="race_res"):
    round: int

class QualiResultsCallback(CallbackData, prefix="quali_res"):
    round: int



@router.message(CommandStart())
async def cmd_start(message: types.Message):
    text, markup = get_main_menu_text_and_markup()
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "races")
async def get_races(callback: types.CallbackQuery):
    data = api.get_races_data(datetime.date.today().year)
    races = data["MRData"]["RaceTable"]["Races"]
    print(races)
    builder = InlineKeyboardBuilder()
    for race in races:
        if check_race_status(race["date"], race["time"]) == "🏁":
            style = ButtonStyle.DANGER
        if check_race_status(race["date"], race["time"]) == "🟢":
            style = ButtonStyle.SUCCESS
        if check_race_status(race["date"], race["time"]) == "":
            style=None
        builder.button(text=f" {check_race_status(race["date"], race["time"])} {COUNTRY_FLAGS.get(race["Circuit"]["Location"]["country"])} {race["Circuit"]["Location"]["locality"]} ",
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
    round_number = int(callback.data.split(":")[1])
    data = api.get_race_data(datetime.date.today().year, round_number)
    print(data)
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
    if check_race_status(race["date"], race["time"]) == "🏁" :
        builder.button(text="Результаты гонки", callback_data=RaceResultsCallback(round=round_number), style=ButtonStyle.SUCCESS)
        builder.button(text="Результаты квалификации", callback_data=QualiResultsCallback(round=round_number),style=ButtonStyle.PRIMARY)
    builder.button(text="Назад", callback_data="races")
    builder.adjust(1)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    await callback.answer()

@router.callback_query(RaceResultsCallback.filter())
async def get_race_results_handler(callback: types.CallbackQuery, callback_data: RaceResultsCallback):
    round_number = callback_data.round
    data = api.get_race_results(datetime.date.today().year, round_number)
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
    data = api.get_qualifying_results(datetime.date.today().year, round_number)
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
async def help(callback: types.CallbackQuery):
    await callback.answer("")
    await callback.message.answer("бог поможет")


async def main():
  logging.basicConfig(level=logging.INFO)
  await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
