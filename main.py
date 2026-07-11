import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import logging

load_dotenv()

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

 
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет")


async def main():
  logging.basicConfig(level=logging.INFO)
  await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())