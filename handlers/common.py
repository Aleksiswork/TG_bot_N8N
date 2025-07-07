from aiogram import Router, F, types
from aiogram.filters import Command
from database import Database
from keyboards import get_main_keyboard

router = Router()
try:
    db = Database()
except Exception as e:
    db = None


@router.message(Command("start"))
async def start_handler(message: types.Message):
    if db is None:
        await message.answer("❌ Ошибка: не удалось инициализировать подключение к базе данных. Обратитесь к администратору.")
        return
    await db.save_user(message.from_user)
    text = "Привет! Я бот для помощи с гайдами..."
    user_id = message.from_user.id if message.from_user else 0
    await message.answer(text, reply_markup=get_main_keyboard(user_id))
