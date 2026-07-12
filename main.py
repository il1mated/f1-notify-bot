import asyncio
import os
from dotenv import load_dotenv
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F
from aiogram import Router
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import logging
import api
import datetime
from zoneinfo import ZoneInfo

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
        builder.button(text=f" {COUNTRY_FLAGS.get(race["Circuit"]["Location"]["country"])} {race["Circuit"]["Location"]["locality"]} {check_race_status(race["date"],race["time"] )}",
                       callback_data=f'race:{race["round"]}'
                       )
    await callback.answer("")

    if callback.message:
        builder.adjust(3)
        builder.button(text="В меню", callback_data="to_menu")
        builder.adjust(3, 3, 3, 3, 3, 3, 3, 1)

        await callback.message.edit_text("Гран-при этого сезона:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("race:"))
async def get_race_details(callback: types.CallbackQuery):
    round_number = callback.data.split(":")[1]
    data = api.get_race_data(datetime.date.today().year, round_number)
    print(data)
    races = data["MRData"]["RaceTable"]["Races"]

    if not races:
        await callback.answer("Гонка не найдена", show_alert=True)
        return

    race = races[0]

    location = race["Circuit"]["Location"]
    dt = datetime.datetime.fromisoformat(
        f"{race['date']}T{race.get('time', '00:00:00').replace('Z', '+00:00')}"
    ).astimezone(datetime.timezone(datetime.timedelta(hours=3)))
    text = (
        f"🏁 Гран-При: {race['raceName']}\n"
        f"📍 Где: {location['locality']}, {location['country']}\n"
        f"🏟 Трек: {race['Circuit']['circuitName']}\n"
        f"📅 Дата: {dt:%d.%m.%Y %H:%M} МСК"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data="races")
    if callback.message:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())

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
