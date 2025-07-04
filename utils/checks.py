from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from config import CHANNEL_USERNAME
import logging

logger = logging.getLogger(__name__)


async def check_subscription(bot: Bot, user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал
    :param bot: Экземпляр бота
    :param user_id: ID пользователя
    :return: True если подписан, False если нет
    """
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        return False
