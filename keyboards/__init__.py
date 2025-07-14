"""
Клавиатуры для бота
"""
from .base import (
    get_main_keyboard,
    get_guides_keyboard,
    get_feedback_keyboard,
    get_subscribe_keyboard,
    get_pagination_keyboard,
    get_confirmation_keyboard,
    create_reply_keyboard,
    create_inline_keyboard
)
from .admin import (
    get_admin_keyboard,
    get_bans_keyboard,
    get_ban_user_keyboard,
    get_unban_user_keyboard
)

__all__ = [
    'get_main_keyboard',
    'get_guides_keyboard',
    'get_feedback_keyboard',
    'get_admin_keyboard',
    'get_subscribe_keyboard',
    'get_pagination_keyboard',
    'get_confirmation_keyboard',
    'create_reply_keyboard',
    'create_inline_keyboard',
    'get_bans_keyboard',
    'get_ban_user_keyboard',
    'get_unban_user_keyboard'
]
