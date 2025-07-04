from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from database import Database
from keyboards import (
    get_subscribe_keyboard,
    get_main_keyboard
)
from utils import check_subscription
from config import FILES_DIR, ADMIN_IDS
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
import os
import logging


class IdeaStates(StatesGroup):
    waiting_for_idea = State()


class BroadcastState(StatesGroup):
    waiting_message = State()


router = Router()
db = Database()
logger = logging.getLogger(__name__)

# -------------------------------
# Обработчики материалов
# -------------------------------


@router.message(F.text == "📨 Предложить идею")
async def start_idea_suggestion(message: Message, state: FSMContext):
    """Начало процесса предложения идеи"""
    await message.answer(
        "Напишите вашу идею или предложение одним сообщением:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(IdeaStates.waiting_for_idea)


@router.message(F.text == '✉️ Сообщение пользователям')
async def broadcast_handler(message: Message, state: FSMContext):
    """Запуск процесса рассылки"""
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "Введите сообщение для рассылки:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(BroadcastState.waiting_message)


@router.message(IdeaStates.waiting_for_idea)
async def process_idea(message: Message, state: FSMContext, bot: Bot):
    """Обработка идеи без сохранения в БД"""
    try:
        # Просто выводим в логи
        logger.info(f"Идея от @{message.from_user.username}: {message.text}")

        await message.answer(
            "✅ Спасибо за ваше предложение!",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

        # Можно добавить уведомление админу (опционально)
        await bot.send_message(
            ADMIN_IDS,
            f"Новая идея от @{message.from_user.username}"
        )

    except Exception as e:
        logger.error(f"Ошибка обработки идеи: {e}")
        await message.answer(
            "❌ Произошла ошибка",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
    finally:
        await state.clear()


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
