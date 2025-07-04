from config import ADMIN_ID
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from config import CHANNEL_LINK, ADMIN_ID


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
        [KeyboardButton(text="📨 Предложить идею")]
    ]

    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton(text="⚙️ Управление")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# def get_main_keyboard(user_id: int):
#     """Главное меню (разное для админа и пользователей)"""
#     buttons = [
#         [
#             KeyboardButton(text="Установка БД"),
#             KeyboardButton(text="Фишки"),
#             KeyboardButton(text="Установка N8N"),
#             KeyboardButton(text="Фаервол и ssh-keygen"),
#             [KeyboardButton(text="📨 Предложить пост")]
#         ]
#     ]

#     if user_id == ADMIN_ID:
#         buttons.append([KeyboardButton(text="⚙️ Управление")])

#     return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
