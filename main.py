"""
Telegram Bot v3.0 - Main Entry Point
Улучшенная архитектура с использованием новой конфигурации
Оптимизировано для работы с 1000+ пользователей
"""
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.state import State, StatesGroup
from config import config, BOT_VERSION
from database import Database
from keyboards import get_subscribe_keyboard, get_main_keyboard, get_admin_keyboard
import asyncio
import logging
import os
import time
import psutil
import signal
import sys
import threading
from handlers.common import router as common_router
from handlers.user import router as user_router, set_bot_instance
from handlers.admin import router as admin_router
from database.submissions import SubmissionDB
from database.banned import BannedDB
from contextlib import asynccontextmanager

# Настройка логирования
logger = logging.getLogger(__name__)

# Создаем папку для файлов если не существует
os.makedirs(config.files_dir, exist_ok=True)

# Отключаем лишние логи
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("handlers.user").setLevel(logging.WARNING)
logging.getLogger("handlers.admin").setLevel(logging.WARNING)
logging.getLogger("database.db").setLevel(logging.WARNING)
logging.getLogger("database.submissions").setLevel(logging.WARNING)

# Глобальный флаг для завершения
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    print(f"Получен сигнал {signum}, начинаем корректное завершение...")
    shutdown_event.set()


# Регистрируем обработчики сигналов (только в основном потоке)
if threading.current_thread() is threading.main_thread():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


class BroadcastState(StatesGroup):
    waiting_message = State()


class PerformanceMonitor:
    """Мониторинг производительности бота"""

    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.last_report_time = time.time()

    def increment_request(self):
        self.request_count += 1

    def increment_error(self):
        self.error_count += 1

    def get_stats(self):
        uptime = time.time() - self.start_time
        requests_per_minute = (self.request_count /
                               uptime) * 60 if uptime > 0 else 0
        error_rate = (self.error_count / self.request_count *
                      100) if self.request_count > 0 else 0

        # Системные ресурсы
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        return {
            'uptime_hours': uptime / 3600,
            'requests_per_minute': requests_per_minute,
            'error_rate': error_rate,
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3)
        }

    def log_performance(self):
        """Логирует статистику производительности"""
        stats = self.get_stats()
        logger.info(
            f"📊 Производительность: "
            f"Uptime: {stats['uptime_hours']:.1f}ч, "
            f"RPM: {stats['requests_per_minute']:.1f}, "
            f"Errors: {stats['error_rate']:.1f}%, "
            f"CPU: {stats['cpu_percent']:.1f}%, "
            f"RAM: {stats['memory_percent']:.1f}% "
            f"({stats['memory_available_gb']:.1f}GB free)"
        )


# Глобальный монитор производительности
performance_monitor = PerformanceMonitor()


@asynccontextmanager
async def lifespan():
    """Управление жизненным циклом приложения"""
    logger.info(f"🚀 Запуск бота v{BOT_VERSION}")

    # Инициализация всех БД и таблиц ДО запуска бота
    await Database.init_all()

    # Создаём экземпляры БД для последующего закрытия
    submission_db = SubmissionDB()
    banned_db = BannedDB()

    try:
        yield submission_db
    finally:
        logger.info("🔄 Завершение работы бота...")
        await submission_db.close()
        await banned_db.close()

        # Закрываем соединения с основной БД
        db = Database()
        await db.close_all_connections()

        logger.info("✅ Бот остановлен")


async def setup_bot() -> tuple[Bot, Dispatcher]:
    """Настройка бота и диспетчера"""
    # Проверяем что BOT_TOKEN установлен
    if not config.token:
        raise ValueError("BOT_TOKEN не установлен")

    bot = Bot(
        token=config.token,
        # Оптимизации для высокой нагрузки
        session_timeout=60,
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=30
    )

    # Устанавливаем глобальный экземпляр бота для автоматической блокировки
    set_bot_instance(bot)

    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(common_router)
    dp.include_router(user_router)
    dp.include_router(admin_router)

    return bot, dp


async def performance_monitoring_task():
    """Задача мониторинга производительности"""
    while True:
        try:
            await asyncio.sleep(300)  # Каждые 5 минут
            performance_monitor.log_performance()
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга: {e}")


async def main():
    """Главная функция запуска бота"""
    try:
        async with lifespan() as submission_db:
            bot, dp = await setup_bot()

            logger.info(f"🚀 Бот v{BOT_VERSION} запущен")
            logger.info("💡 Для остановки нажмите Ctrl+C")

            # Запускаем мониторинг производительности
            monitoring_task = asyncio.create_task(
                performance_monitoring_task())

            max_retries = 5
            retry_count = 0

            while retry_count < max_retries and not shutdown_event.is_set():
                try:
                    # Создаем задачу для polling
                    polling_task = asyncio.create_task(
                        dp.start_polling(
                            bot,
                            polling_timeout=60,
                            skip_updates=True,
                            allowed_updates=[
                                "message", "callback_query", "chat_member"
                            ]
                        )
                    )

                    # Ждем либо завершения polling, либо сигнала остановки
                    shutdown_task = asyncio.create_task(shutdown_event.wait())
                    done, pending = await asyncio.wait(
                        [polling_task, shutdown_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # Отменяем все pending задачи
                    for task in pending:
                        task.cancel()

                    # Если получили сигнал остановки
                    if shutdown_event.is_set():
                        logger.info("🛑 Получен сигнал остановки")
                        break

                    # Если polling завершился с ошибкой
                    if polling_task in done:
                        try:
                            await polling_task
                        except Exception as e:
                            retry_count += 1
                            performance_monitor.increment_error()
                            logger.error(
                                f"❌ Ошибка подключения (попытка {retry_count}/{max_retries}): {e}")

                            if retry_count < max_retries and not shutdown_event.is_set():
                                wait_time = retry_count * 10
                                logger.info(
                                    f"🔄 Повторная попытка через {wait_time} секунд...")
                                await asyncio.sleep(wait_time)
                            else:
                                logger.error(
                                    "❌ Превышено максимальное количество попыток подключения")
                                break

                except Exception as e:
                    retry_count += 1
                    performance_monitor.increment_error()
                    logger.error(
                        f"❌ Критическая ошибка (попытка {retry_count}/{max_retries}): {e}")

                    if retry_count < max_retries and not shutdown_event.is_set():
                        wait_time = retry_count * 10
                        logger.info(
                            f"🔄 Повторная попытка через {wait_time} секунд...")
                        await asyncio.sleep(wait_time)
                    else:
                        break

            # Корректное завершение
            logger.info("🔄 Начинаем корректное завершение...")

            # Отменяем задачу мониторинга
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass

            # Закрываем сессию бота
            try:
                await bot.session.close()
            except Exception as e:
                logger.error(f"❌ Ошибка закрытия сессии бота: {e}")

            logger.info("✅ Бот корректно остановлен")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в main(): {e}")
        raise


if __name__ == "__main__":
    try:
        # Настройка asyncio для Windows
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy())

        # Проверяем аргументы командной строки
        if len(sys.argv) > 1 and sys.argv[1] == "--simple":
            # Простой режим запуска для разработки
            logger.info("🔧 Запуск в простом режиме (--simple)")
            asyncio.run(main())
        else:
            # Полный режим с обработкой сигналов
            asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        sys.exit(1)
    finally:
        # Агрессивная очистка для предотвращения зависания
        print("🧹 Очистка ресурсов...")

        # Принудительно закрываем все логи
        logging.shutdown()

        # Очищаем все pending задачи
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Отменяем все задачи
                for task in asyncio.all_tasks(loop):
                    if not task.done():
                        task.cancel()

                # Даем время на отмену
                loop.run_until_complete(asyncio.sleep(0.1))

                # Закрываем loop
                if not loop.is_closed():
                    loop.close()
        except Exception:
            pass

        # Принудительно завершаем процесс если нужно
        try:
            import os
            if os.name == 'nt':  # Windows
                # На Windows принудительно завершаем
                os._exit(0)
        except Exception:
            pass

        print("🏁 Программа завершена")
