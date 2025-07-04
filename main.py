from aiogram import Bot, Dispatcher, F
from aiogram.fsm.state import State, StatesGroup
from config import BOT_TOKEN, BOT_VERSION, FILES_DIR
from database import Database
from keyboards import get_subscribe_keyboard, get_main_keyboard, get_admin_keyboard
import asyncio
import logging
import os
from handlers.common import router as common_router
from handlers.user import router as user_router
from handlers.admin import router as admin_router


# Инициализация базы данных
db = Database()

# Создаем папку для файлов если не существует
os.makedirs(FILES_DIR, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format=f'%(asctime)s - %(name)s - v{BOT_VERSION} - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Состояния FSM


class BroadcastState(StatesGroup):
    waiting_message = State()


# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ======================
# ЗАПУСК БОТА
# ======================


async def main():
    """Основная функция запуска"""
    await db.init_db()
    dp.include_router(common_router)
    dp.include_router(user_router)
    dp.include_router(admin_router)
    logger.info(f"🚀 Бот v{BOT_VERSION} запущен")
    try:
        await dp.start_polling(bot)

    finally:
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
