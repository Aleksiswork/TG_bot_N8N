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
from database.submissions import SubmissionDB
from config import DB_SUBMISSIONS_PATH


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

# Отключаем лишние INFO-логи от aiogram.event
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
# Отключаем INFO-логи от handlers.user
logging.getLogger("handlers.user").setLevel(logging.WARNING)
logging.getLogger("handlers.admin").setLevel(logging.WARNING)
logging.getLogger("database.db").setLevel(logging.WARNING)
logging.getLogger("database.submissions").setLevel(logging.WARNING)


class BroadcastState(StatesGroup):
    waiting_message = State()


# ======================
# ЗАПУСК БОТА
# ======================


async def main():
    # Инициализация всех БД и таблиц ДО запуска бота
    from database.db import Database
    await Database.init_all()

    # Явно создаём экземпляр SubmissionDB для последующего закрытия
    from database.submissions import SubmissionDB
    submission_db = SubmissionDB()

    # Проверяем что BOT_TOKEN установлен (должен быть проверен в config.py)
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Подключаем роутеры ПЕРЕД стартом бота
    dp.include_router(common_router)
    dp.include_router(user_router)
    dp.include_router(admin_router)

    logger.info(f"🚀 Бот v{BOT_VERSION} запущен")
    try:
        await dp.start_polling(bot)  # Теперь бот видит все обработчики
    finally:
        logger.info("🔄 Завершение работы бота...")
        await submission_db.close()
        await bot.session.close()
        logger.info("✅ Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
