from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_admin_keyboard():
    """Админ-панель"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="🔄 Версия бота")
            ],
            [KeyboardButton(text="📁 Выгрузить БД (CSV)")],
            [KeyboardButton(text="✉️ Сообщение пользователям")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )
