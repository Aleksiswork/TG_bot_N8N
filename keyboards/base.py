from config import ADMIN_IDS
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from config import CHANNEL_LINK, ADMIN_IDS


def get_subscribe_keyboard():
    """Клавиатура для подписки на канал"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_LINK)]
        ]
    )


def get_main_keyboard(user_id: int):
    """Создает главную клавиатуру с корректной структурой"""
    keyboard = [
        [KeyboardButton(text="Установка БД"), KeyboardButton(text="Фишки")],
        [KeyboardButton(text="Установка N8N"), KeyboardButton(
            text="Фаервол и ssh-keygen")],
        [KeyboardButton(text="📨 Обратная связь")]
    ]

    if user_id in ADMIN_IDS:
        keyboard.append([KeyboardButton(text="⚙️ Управление")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
