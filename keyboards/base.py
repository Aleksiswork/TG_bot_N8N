"""
Базовые клавиатуры для бота
"""
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from typing import List, Optional, Union
from config import config
from utils.checks import is_admin


def create_reply_keyboard(
    buttons: List[List[str]],
    resize_keyboard: bool = True,
    one_time_keyboard: bool = False,
    selective: bool = False
) -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру с кнопками

    Args:
        buttons: Список списков кнопок
        resize_keyboard: Изменять размер клавиатуры
        one_time_keyboard: Скрывать клавиатуру после нажатия
        selective: Показывать только определенным пользователям

    Returns:
        ReplyKeyboardMarkup: Клавиатура
    """
    keyboard_buttons = [[KeyboardButton(text=text)
                         for text in row] for row in buttons]

    return ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=resize_keyboard,
        one_time_keyboard=one_time_keyboard,
        selective=selective
    )


def create_inline_keyboard(
    buttons: List[List[dict]],
    row_width: int = 2
) -> InlineKeyboardMarkup:
    """
    Создает inline клавиатуру

    Args:
        buttons: Список кнопок с параметрами
        row_width: Количество кнопок в ряду

    Returns:
        InlineKeyboardMarkup: Inline клавиатура
    """
    keyboard_buttons = []

    for row in buttons:
        keyboard_row = []
        for button_data in row:
            keyboard_row.append(InlineKeyboardButton(**button_data))
        keyboard_buttons.append(keyboard_row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """
    Главная клавиатура пользователя

    Args:
        user_id: ID пользователя

    Returns:
        ReplyKeyboardMarkup: Главная клавиатура
    """
    buttons = [
        ["📚 Гайды", "📨 Обратная связь"],
        ["ℹ️ О боте"]
    ]

    # Добавляем админские кнопки
    if is_admin(user_id):
        buttons.append(["⚙️ Управление"])

    return create_reply_keyboard(buttons)


def get_guides_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура с гайдами

    Returns:
        ReplyKeyboardMarkup: Клавиатура гайдов
    """
    buttons = [
        ["Установка БД", "Фаервол и ssh-keygen"],
        ["Установка N8N", "Фишки"],
        ["⬅️ Назад"]
    ]
    return create_reply_keyboard(buttons)


def get_feedback_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура для обратной связи

    Returns:
        ReplyKeyboardMarkup: Клавиатура обратной связи
    """
    buttons = [
        ["📤 Отправить"],
        ["📜 История"],
        ["❌ Отменить"]
    ]
    return create_reply_keyboard(buttons)


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """
    Админская клавиатура

    Returns:
        ReplyKeyboardMarkup: Админская клавиатура
    """
    buttons = [
        ["📊 Статистика", "📋 Посмотреть предложку"],
        ["📁 Выгрузить БД (CSV)", "✉️ Сообщение пользователям"],
        ["🔄 Версия бота"],
        ["⬅️ Назад"]
    ]
    return create_reply_keyboard(buttons)


def get_subscribe_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для подписки на канал

    Returns:
        InlineKeyboardMarkup: Клавиатура подписки
    """
    if not config.channel_link:
        return InlineKeyboardMarkup(inline_keyboard=[])

    buttons = [
        [
            InlineKeyboardButton(
                text="📢 Подписаться на канал",
                url=config.channel_link
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Проверить подписку",
                callback_data="check_subscription"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
    extra_buttons: Optional[List[dict]] = None
) -> InlineKeyboardMarkup:
    """
    Клавиатура с пагинацией

    Args:
        current_page: Текущая страница
        total_pages: Общее количество страниц
        callback_prefix: Префикс для callback данных
        extra_buttons: Дополнительные кнопки

    Returns:
        InlineKeyboardMarkup: Клавиатура с пагинацией
    """
    buttons = []

    # Кнопки навигации
    nav_buttons = []

    if current_page > 1:
        nav_buttons.append({
            "text": "◀️",
            "callback_data": f"{callback_prefix}_page_{current_page - 1}"
        })

    nav_buttons.append({
        "text": f"{current_page}/{total_pages}",
        "callback_data": "no_action"
    })

    if current_page < total_pages:
        nav_buttons.append({
            "text": "▶️",
            "callback_data": f"{callback_prefix}_page_{current_page + 1}"
        })

    if nav_buttons:
        buttons.append(nav_buttons)

    # Дополнительные кнопки
    if extra_buttons:
        buttons.extend(extra_buttons)

    return create_inline_keyboard(buttons)


def get_confirmation_keyboard(
    confirm_text: str = "✅ Подтвердить",
    cancel_text: str = "❌ Отменить",
    confirm_callback: str = "confirm",
    cancel_callback: str = "cancel"
) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения

    Args:
        confirm_text: Текст кнопки подтверждения
        cancel_text: Текст кнопки отмены
        confirm_callback: Callback для подтверждения
        cancel_callback: Callback для отмены

    Returns:
        InlineKeyboardMarkup: Клавиатура подтверждения
    """
    buttons = [
        [
            {"text": confirm_text, "callback_data": confirm_callback},
            {"text": cancel_text, "callback_data": cancel_callback}
        ]
    ]
    return create_inline_keyboard(buttons)
