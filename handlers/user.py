from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from database import Database
from keyboards import (
    get_subscribe_keyboard,
    get_main_keyboard
)
from utils import check_subscription
from config import FILES_DIR
import os
import logging

router = Router()
db = Database()
logger = logging.getLogger(__name__)

# -------------------------------
# Обработчики материалов
# -------------------------------


@router.message(F.text == 'Установка БД')
async def send_db_guide(message: Message, bot: Bot):
    """Отправка гайда по базам данных"""
    await db.save_user(message.from_user)

    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "❌ Для доступа к материалам необходимо подписаться на канал!",
            reply_markup=get_subscribe_keyboard()
        )
        return

    file_path = os.path.join(FILES_DIR, 'temp.txt')
    try:
        document = FSInputFile(file_path, filename="guide_bd.txt")
        await message.answer_document(document, caption="📚 Гайд по базам данных")
    except FileNotFoundError:
        await message.answer("⚠️ Файл с гайдом временно недоступен.")
    except Exception as e:
        logger.error(f"Ошибка при отправке гайда БД: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(F.text == 'Фаервол и ssh-keygen')
async def send_firewall_guide(message: Message, bot: Bot):
    """Отправка гайда по фаерволу"""
    await db.save_user(message.from_user)

    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "❌ Для доступа к материалам необходимо подписаться на канал!",
            reply_markup=get_subscribe_keyboard()
        )
        return

    file_path = os.path.join(FILES_DIR, 'bonus.pdf')
    try:
        document = FSInputFile(file_path, filename="bonus.pdf")
        await message.answer_document(document, caption="📚 Гайд по фаерволу и ssh-keygen")
    except FileNotFoundError:
        await message.answer("⚠️ Файл с гайдом временно недоступен.")
    except Exception as e:
        logger.error(f"Ошибка при отправке гайда: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(F.text == 'Установка N8N')
async def send_n8n_guide(message: Message, bot: Bot):
    """Отправка гайда по N8N"""
    await db.save_user(message.from_user)

    file_path = os.path.join(FILES_DIR, 'install.pdf')
    try:
        document = FSInputFile(file_path, filename="install.pdf")
        await message.answer_document(document, caption="📚 Гайд по установке N8N")
    except FileNotFoundError:
        await message.answer("⚠️ Файл с гайдом временно недоступен.")
    except Exception as e:
        logger.error(f"Ошибка при отправке гайда: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")

# -------------------------------
# Прочие обработчики
# -------------------------------


@router.message(F.text == 'Фишки')
async def send_tips(message: Message, bot: Bot):
    """Полезные фишки"""
    await db.save_user(message.from_user)

    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "❌ Для доступа необходимо подписаться на канал!",
            reply_markup=get_subscribe_keyboard()
        )
        return

    await message.answer("Здесь будут полезные фишки...")


@router.message(F.text == '⬅️ Назад')
async def back_to_main(message: Message):
    """Возврат в главное меню"""
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard(message.from_user.id)
    )
