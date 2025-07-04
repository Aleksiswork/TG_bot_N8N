from aiogram import Router, F, types
from aiogram.filters import Command
from database import Database
from keyboards import get_main_keyboard

router = Router()
db = Database()


@router.message(Command("start"))
async def start_handler(message: types.Message):
    await db.save_user(message.from_user)
    text = "Привет! Я бот для помощи с гайдами..."
    await message.answer(text, reply_markup=get_main_keyboard(message.from_user.id))
