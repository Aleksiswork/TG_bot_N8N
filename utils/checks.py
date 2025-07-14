"""
Утилиты для проверок и валидации
"""
import logging
from typing import Optional, Union
from aiogram import Bot
from aiogram.types import Message, User
from config import config

logger = logging.getLogger(__name__)


async def check_subscription(user_id: int, bot: Bot) -> bool:
    """
    Проверяет подписку пользователя на канал

    Args:
        user_id: ID пользователя
        bot: Экземпляр бота

    Returns:
        bool: True если пользователь подписан, False иначе
    """
    if not config.channel_username and not config.channel_id:
        return True

    # Пробуем разные варианты chat_id
    chat_variants = []

    # Если есть ID канала, используем его первым
    if config.channel_id:
        try:
            chat_variants.append(int(config.channel_id))
        except ValueError:
            logger.warning(f"Некорректный CHANNEL_ID: {config.channel_id}")

    # Добавляем варианты с username (убираем дублирование @)
    if config.channel_username:
        # Убираем @ если он уже есть в начале
        clean_username = config.channel_username.lstrip('@')
        chat_variants.extend([
            f"@{clean_username}",
            clean_username
        ])

    for chat_id in chat_variants:
        try:
            chat_member = await bot.get_chat_member(
                chat_id=chat_id,
                user_id=user_id
            )
            return chat_member.status not in ["left", "kicked"]
        except Exception as e:
            logger.warning(f"Ошибка проверки подписки: {e}")
            continue

    # При ошибке считаем, что пользователь подписан
    return True


def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором

    Args:
        user_id: ID пользователя

    Returns:
        bool: True если пользователь админ
    """
    return user_id in config.admin_ids


def validate_file_size(file_size: int) -> bool:
    """
    Проверяет размер файла

    Args:
        file_size: Размер файла в байтах

    Returns:
        bool: True если размер допустим
    """
    max_size = config.max_file_size_mb * 1024 * 1024  # Конвертируем в байты
    return file_size <= max_size


def validate_text_length(text: str) -> bool:
    """
    Проверяет длину текста

    Args:
        text: Текст для проверки

    Returns:
        bool: True если длина допустима
    """
    return len(text) <= config.max_submission_length


def get_user_info(user: User) -> dict:
    """
    Получает информацию о пользователе

    Args:
        user: Объект пользователя

    Returns:
        dict: Информация о пользователе
    """
    return {
        'id': user.id,
        'username': user.username or "unknown",
        'first_name': user.first_name or "",
        'last_name': user.last_name or "",
        'is_admin': is_admin(user.id)
    }


def format_file_size(size_bytes: int) -> str:
    """
    Форматирует размер файла в читаемый вид

    Args:
        size_bytes: Размер в байтах

    Returns:
        str: Отформатированный размер
    """
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def sanitize_filename(filename: str) -> str:
    """
    Очищает имя файла от недопустимых символов

    Args:
        filename: Исходное имя файла

    Returns:
        str: Очищенное имя файла
    """
    import re
    # Удаляем недопустимые символы
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Ограничиваем длину
    if len(filename) > 100:
        name, ext = filename.rsplit(
            '.', 1) if '.' in filename else (filename, '')
        filename = name[:95] + '.' + ext
    return filename


def validate_message_content(message: Message) -> tuple[bool, str]:
    """
    Валидирует содержимое сообщения

    Args:
        message: Сообщение для проверки

    Returns:
        tuple[bool, str]: (валидно, описание ошибки)
    """
    # Проверяем наличие контента
    if not message.text and not message.caption and not message.photo and not message.document:
        return False, "Сообщение не содержит контента"

    # Проверяем длину текста
    text = message.text or message.caption or ""
    if text and not validate_text_length(text):
        return False, f"Текст слишком длинный (максимум {config.max_submission_length} символов)"

    # Проверяем размер файла
    if message.document and message.document.file_size:
        if not validate_file_size(message.document.file_size):
            return False, f"Файл слишком большой (максимум {config.max_file_size_mb}MB)"

    return True, ""


def get_error_message(error: Exception) -> str:
    """
    Получает понятное сообщение об ошибке

    Args:
        error: Исключение

    Returns:
        str: Понятное сообщение об ошибке
    """
    error_type = type(error).__name__

    if "Forbidden" in str(error):
        return "❌ Бот заблокирован пользователем"
    elif "Chat not found" in str(error):
        return "❌ Чат не найден"
    elif "User not found" in str(error):
        return "❌ Пользователь не найден"
    elif "File too large" in str(error):
        return f"❌ Файл слишком большой (максимум {config.max_file_size_mb}MB)"
    elif "Message too long" in str(error):
        return f"❌ Сообщение слишком длинное (максимум {config.max_submission_length} символов)"
    else:
        logger.error(f"Неизвестная ошибка: {error}")
        return "❌ Произошла неизвестная ошибка"
