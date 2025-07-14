from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional


def get_admin_keyboard():
    """Админ-панель"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="🔄 Версия бота")
            ],
            [
                KeyboardButton(text="📁 Выгрузить БД (CSV)"),
                KeyboardButton(text="📋 Посмотреть предложку")
            ],
            [
                KeyboardButton(text="✉️ Сообщение пользователям"),
                KeyboardButton(text="🚫 Блокировки")
            ],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )


def get_bans_keyboard():
    """Клавиатура управления блокировками"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📋 Список заблокированных"),
                KeyboardButton(text="📊 Статистика блокировок")
            ],
            [
                KeyboardButton(text="🔍 Найти пользователя"),
                KeyboardButton(text="🧹 Очистить истекшие")
            ],
            [KeyboardButton(text="⬅️ Назад в админ-панель")]
        ],
        resize_keyboard=True
    )


def get_ban_user_keyboard(user_id: int, username: Optional[str] = None):
    """Клавиатура для блокировки пользователя"""
    display_name = f"@{username}" if username else f"ID: {user_id}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🚫 Заблокировать {display_name}",
                    callback_data=f"ban_user:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_ban"
                )
            ]
        ]
    )


def get_unban_user_keyboard(user_id: int, username: Optional[str] = None):
    """Клавиатура для разблокировки пользователя"""
    display_name = f"@{username}" if username else f"ID: {user_id}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Разблокировать {display_name}",
                    callback_data=f"unban_user:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_unban"
                )
            ]
        ]
    )
