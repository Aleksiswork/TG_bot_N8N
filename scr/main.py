"""
Telegram Bot v1.3
Обновления:
Надежный экспорт в CSV с правильным форматированием
Проверку размера файла
Инструкцию по открытию
Автоматическую очистку временных файлов

Функционал:
- Проверка подписки на канал
- Раздача гайдов (!БД, !Фишки)
- Админ-команды (/stats, /version)
- Хранение пользователей в SQLite
"""
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton
)
from aiogram.enums import ChatMemberStatus
from dotenv import load_dotenv
import asyncio
import logging
import os
import aiosqlite
import csv
from datetime import datetime


class BroadcastState(StatesGroup):
    waiting_message = State()


# Загрузка переменных окружения
load_dotenv()

# Конфигурация бота
BOT_VERSION = "1.3"
CHANNEL_USERNAME = "@Info_IT_news"
CHANNEL_LINK = "https://t.me/Info_IT_news"
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
FILES_DIR = "d:/vps/VSCode/tgbot/files/"
DB_NAME = "bot_users.db"

os.makedirs(FILES_DIR, exist_ok=True)  # Создаст папку если её нет

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format=f'%(asctime)s - %(name)s - v{BOT_VERSION} - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ======================
# КЛАВИАТУРЫ
# ======================


def get_subscribe_keyboard():
    """Клавиатура для подписки на канал"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_LINK)]
        ]
    )


def get_main_keyboard(user_id: int):
    """Главное меню (разное для админа и пользователей)"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="!БД"), KeyboardButton(text="!Фишки")],
        ],
        resize_keyboard=True
    )

    # Добавляем кнопку управления только для админа
    if user_id == ADMIN_ID:
        keyboard.keyboard.append([KeyboardButton(text="⚙️ Управление")])

    return keyboard


def get_admin_keyboard():
    """Админ-панель с кнопкой рассылки"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"),
             KeyboardButton(text="🔄 Версия бота")],
            [KeyboardButton(text="✉️ Сообщение пользователям")],
            [KeyboardButton(text="📁 Выгрузить БД (CSV)")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# ======================
# РАБОТА С БАЗОЙ ДАННЫХ
# ======================


async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT,
                last_active TEXT
            )
        ''')
        await db.commit()


async def save_user(user: types.User):
    """Сохранение/обновление пользователя в БД"""
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.now().isoformat()
        cursor = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (user.id,))
        exists = await cursor.fetchone()

        if exists:
            await db.execute(
                "UPDATE users SET username=?, first_name=?, last_name=?, last_active=? WHERE user_id=?",
                (user.username, user.first_name, user.last_name, now, user.id)
            )
        else:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, last_name, created_at, last_active) VALUES (?, ?, ?, ?, ?, ?)",
                (user.id, user.username, user.first_name, user.last_name, now, now)
            )
        await db.commit()


# ======================
# ВЫГРУЗКА БД
# ======================


@dp.message(F.text == '📁 Выгрузить БД (CSV)')
async def export_db_csv_handler(message: types.Message):
    """Улучшенный экспорт в CSV с гарантией правильного отображения столбцов"""
    if message.from_user.id != ADMIN_ID:
        return

    temp_file = None
    try:
        # Подготовка файла
        os.makedirs(FILES_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bot_users_export_{timestamp}.csv"
        temp_file = os.path.join(FILES_DIR, filename)

        # Получение данных
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT * FROM users")
            users = await cursor.fetchall()

            if not users:
                await message.answer("🔄 База данных пуста")
                return

            # Создаем CSV с настройками для Excel
            with open(temp_file, 'w', encoding='utf-8-sig', newline='') as f:
                # Явно указываем разделитель и другие параметры
                writer = csv.writer(f,
                                    delimiter=';',  # Используем точку с запятой
                                    quoting=csv.QUOTE_ALL)  # Все значения в кавычках

                # Заголовки
                writer.writerow([
                    'ID', 'Username', 'Имя',
                    'Фамилия', 'Дата регистрации', 'Последняя активность'
                ])

                # Данные
                for user in users:
                    writer.writerow([
                        user[0],  # ID
                        f'"{user[1]}"' if user[1] else '',  # Username
                        f'"{user[2]}"' if user[2] else '',  # Имя
                        f'"{user[3]}"' if user[3] else '',  # Фамилия
                        user[4],  # Дата регистрации
                        user[5]   # Последняя активность
                    ])

        # Проверка размера файла
        file_size = os.path.getsize(temp_file) / (1024 * 1024)
        if file_size > 45:
            await message.answer("⚠️ Файл слишком большой для отправки (>45 МБ)")
            return

        # Отправка файла с инструкцией
        document = FSInputFile(temp_file, filename=filename)
        sent_msg = await message.answer_document(
            document,
            caption=(
                f"📊 Экспорт БД ({len(users)} записей)\n"
                f"ℹ️ Для корректного открытия:\n"
                f"1. В Excel: 'Данные' → 'Из текста/CSV'\n"
                f"2. Укажите кодировку UTF-8 и разделитель ';'"
            )
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка экспорта: {str(e)}")
        logger.exception("Export error:")
    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
# ======================
# ОСНОВНЫЕ ФУНКЦИИ
# ======================


async def check_subscription(user_id: int) -> bool:
    """Проверка подписки на канал"""
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

# ======================
# ОБРАБОТЧИКИ КОМАНД
# ======================


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    """Обработчик команды /start"""
    await save_user(message.from_user)

    text = "Привет! Я бот для помощи с гайдами. Доступные команды:"

    # Разный текст для админа
    if message.from_user.id == ADMIN_ID:
        text += "\n\n⚙️ Доступно админ-меню"

    await message.answer(
        text,
        reply_markup=get_main_keyboard(message.from_user.id)
    )


@dp.message(F.text == '⚙️ Управление')
async def admin_panel(message: types.Message):
    """Открытие админ-панели"""
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "Админ-панель:",
        reply_markup=get_admin_keyboard()
    )


@dp.message(F.text == '⬅️ Назад')
async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


@dp.message(F.text == '📊 Статистика')
async def stats_handler(message: types.Message):
    """Показ статистики (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]

        cursor = await db.execute("""
            SELECT first_name, username, last_active 
            FROM users 
            ORDER BY last_active DESC 
            LIMIT 5
        """)
        recent_users = await cursor.fetchall()

    stats_text = f"📊 Статистика (v{BOT_VERSION}):\n"
    stats_text += f"👥 Пользователей: {total_users}\n\n"
    stats_text += "⚡ Последние активные:\n"

    for user in recent_users:
        stats_text += f"- {user[0]} (@{user[1]}) - {user[2][:10]}\n"

    await message.answer(stats_text)


@dp.message(F.text == '🔄 Версия бота')
async def version_handler(message: types.Message):
    """Показ версии бота (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(f"🔧 Текущая версия: {BOT_VERSION}")


@dp.message(F.text == '!БД')
async def send_db_guide(message: types.Message):
    """Отправка гайда по базам данных"""
    await save_user(message.from_user)

    if not await check_subscription(message.from_user.id):
        await message.answer(
            "❌ Для доступа к материалам необходимо подписаться на канал!",
            reply_markup=get_subscribe_keyboard()
        )
        return

    file_path = os.path.join(FILES_DIR, 'temp.txt')
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError
        document = FSInputFile(file_path, filename="guide_bd.txt")
        await message.answer_document(document, caption="📚 Гайд по базам данных")
    except FileNotFoundError:
        await message.answer("⚠️ Файл с гайдом временно недоступен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@dp.message(F.text == '!Фишки')
async def send_tips(message: types.Message):
    """Отправка полезных фишек"""
    await save_user(message.from_user)

    if not await check_subscription(message.from_user.id):
        await message.answer(
            "❌ Для доступа к материалам необходимо подписаться на канал!",
            reply_markup=get_subscribe_keyboard()
        )
        return

    await message.answer("Здесь будут полезные фишки...")


# ======================
# ОБРАБОТЧИК РАССЫЛКИ
# ======================


@dp.message(F.text == '✉️ Сообщение пользователям')
async def broadcast_handler(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "Введите сообщение для рассылки всем пользователям:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(BroadcastState.waiting_message)


@dp.message(BroadcastState.waiting_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    """Обработка рассылки сообщения всем пользователям, кроме отправителя"""
    await state.clear()

    if message.from_user.id != ADMIN_ID:
        return

    sender_id = message.from_user.id
    await message.answer("⏳ Начинаю рассылку...", reply_markup=get_admin_keyboard())

    try:
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE user_id != ?", (sender_id,))
            users = await cursor.fetchall()

        results = {"success": 0, "failed": 0}

        for user in users:
            try:
                await bot.send_message(user[0], message.text)
                results["success"] += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user[0]}: {e}")
                results["failed"] += 1

        report = (
            f"📊 Отчет о рассылке:\n"
            f"• Получателей: {len(users)}\n"
            f"• Доставлено: {results['success']}\n"
            f"• Ошибок: {results['failed']}"
        )

        await message.answer(report, reply_markup=get_admin_keyboard())

    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")
        await message.answer(
            f"❌ Ошибка рассылки: {str(e)}",
            reply_markup=get_admin_keyboard()
        )


# ======================
# ЗАПУСК БОТА
# ======================


async def main():
    """Основная функция запуска"""
    await init_db()
    logger.info(f"🚀 Бот v{BOT_VERSION} запущен")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())
