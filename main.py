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
from datetime import date


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


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    text, markup = get_main_menu_text_and_markup()
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "races")
async def get_races(callback: types.CallbackQuery):
    data = api.get_race_data(date.today().year)
    races = data["MRData"]["RaceTable"]["Races"]
    print(races)
    builder = InlineKeyboardBuilder()
    for race in races:
      builder.button(text=f"{COUNTRY_FLAGS.get(race["Circuit"]["Location"]["country"])} {race["Circuit"]["Location"]["locality"]}", callback_data=race["raceName"])
    await callback.answer("")

    if callback.message:
        builder.adjust(3)
        builder.button(text="В меню", callback_data="to_menu")
        builder.adjust(3, 3, 3, 3, 3, 3, 3, 1)

        await callback.message.edit_text("Гран-при этого сезона:", reply_markup=builder.as_markup())

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
