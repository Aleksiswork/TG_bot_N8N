from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    ReplyKeyboardRemove
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import BOT_TOKEN, ADMIN_ID, BOT_VERSION, FILES_DIR, CHANNEL_USERNAME
from database.db import Database
from keyboards import get_subscribe_keyboard, get_main_keyboard, get_admin_keyboard
from utils import check_subscription
import asyncio
import logging
import os
import csv
from datetime import datetime

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
# ОБРАБОТЧИКИ КОМАНД
# ======================


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    """Обработчик команды /start"""
    await db.save_user(message.from_user)

    text = "Привет! Я бот для помощи с гайдами. Доступные команды:"

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

    total_users, recent_users = await db.get_users_stats()

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


@dp.message(F.text == '📁 Выгрузить БД (CSV)')
async def export_db_csv_handler(message: types.Message):
    """Экспорт БД в CSV"""
    if message.from_user.id != ADMIN_ID:
        return

    temp_file = None
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bot_users_export_{timestamp}.csv"
        temp_file = os.path.join(FILES_DIR, filename)

        users = await db.get_all_users()

        if not users:
            await message.answer("🔄 База данных пуста")
            return

        with open(temp_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_ALL)
            writer.writerow(['ID', 'Username', 'Имя', 'Фамилия',
                             'Дата регистрации', 'Последняя активность'])
            for user in users:
                writer.writerow([
                    user[0],
                    f'"{user[1]}"' if user[1] else '',
                    f'"{user[2]}"' if user[2] else '',
                    f'"{user[3]}"' if user[3] else '',
                    user[4],
                    user[5]
                ])

        file_size = os.path.getsize(temp_file) / (1024 * 1024)
        if file_size > 45:
            await message.answer("⚠️ Файл слишком большой для отправки (>45 МБ)")
            return

        document = FSInputFile(temp_file, filename=filename)
        await message.answer_document(
            document,
            caption=(
                f"📊 Экспорт БД ({len(users)} записей, v{BOT_VERSION})\n"
                f"ℹ️ Для открытия в Excel:\n"
                f"1. 'Данные' → 'Из текста/CSV'\n"
                f"2. Кодировка: 65001 UTF-8\n"
                f"3. Разделитель: точка с запятой"
            )
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка экспорта: {str(e)}")
    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)


@dp.message(F.text == '✉️ Сообщение пользователям')
async def broadcast_handler(message: types.Message, state: FSMContext):
    """Обработчик рассылки сообщений"""
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "Введите сообщение для рассылки всем пользователям:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(BroadcastState.waiting_message)


@dp.message(BroadcastState.waiting_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    """Обработка введённого сообщения для рассылки"""
    await state.clear()

    if message.from_user.id != ADMIN_ID:
        return

    sender_id = message.from_user.id
    await message.answer("⏳ Начинаю рассылку...", reply_markup=get_admin_keyboard())

    try:
        users = await db.get_all_users()
        user_ids = [user[0] for user in users if user[0] != sender_id]

        results = {"success": 0, "failed": 0}

        for user_id in user_ids:
            try:
                await bot.send_message(user_id, message.text)
                results["success"] += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
                results["failed"] += 1

        await message.answer(
            f"✅ Рассылка завершена:\n"
            f"• Получателей: {len(user_ids)}\n"
            f"• Доставлено: {results['success']}\n"
            f"• Ошибок: {results['failed']}",
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при рассылке: {e}")
        await message.answer(
            f"❌ Ошибка при рассылке: {str(e)}",
            reply_markup=get_admin_keyboard()
        )


@dp.message(F.text == 'Установка БД')
async def send_db_guide(message: types.Message):
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
        if not os.path.exists(file_path):
            raise FileNotFoundError
        document = FSInputFile(file_path, filename="guide_bd.txt")
        await message.answer_document(document, caption="📚 Гайд по базам данных")
    except FileNotFoundError:
        await message.answer("⚠️ Файл с гайдом временно недоступен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@dp.message(F.text == 'Фаервол и ssh-keygen')
async def send_firewall_guide(message: types.Message):
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
        if not os.path.exists(file_path):
            raise FileNotFoundError
        document = FSInputFile(file_path, filename="bonus.pdf")
        await message.answer_document(document, caption="📚 Гайд по установке фаервола и ssh-keygen")
    except FileNotFoundError:
        await message.answer("⚠️ Файл с гайдом временно недоступен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@dp.message(F.text == 'Фишки')
async def send_tips(message: types.Message):
    """Отправка полезных фишек"""
    await db.save_user(message.from_user)

    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "❌ Для доступа к материалам необходимо подписаться на канал!",
            reply_markup=get_subscribe_keyboard()
        )
        return

    await message.answer("Здесь будут полезные фишки...")


@dp.message(F.text == 'Установка N8N')
async def send_n8n_guide(message: types.Message):
    """Отправка гайда по установке N8N"""
    await db.save_user(message.from_user)

    file_path = os.path.join(FILES_DIR, 'install.pdf')
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError
        document = FSInputFile(file_path, filename="install.pdf")
        await message.answer_document(document, caption="📚 Гайд по установке N8N на сервер")
    except FileNotFoundError:
        await message.answer("⚠️ Файл с гайдом временно недоступен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# ======================
# ЗАПУСК БОТА
# ======================


async def main():
    """Основная функция запуска"""
    await db.init_db()
    logger.info(f"🚀 Бот v{BOT_VERSION} запущен")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())
