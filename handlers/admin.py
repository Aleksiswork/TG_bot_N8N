from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from keyboards import get_admin_keyboard
from config import FILES_DIR, BOT_VERSION, ADMIN_IDS
from datetime import datetime
import os
import csv
import logging
import asyncio  # Добавить в блок импортов
from datetime import datetime
from aiogram.types import ReplyKeyboardRemove

router = Router()
db = Database()
logger = logging.getLogger(__name__)


class BroadcastState(StatesGroup):
    waiting_message = State()

# -------------------------------
# Команды администрирования
# -------------------------------


@router.message(F.text == '⚙️ Управление')
async def admin_panel(message: Message):
    """Отображение админ-панели"""
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Админ-панель:", reply_markup=get_admin_keyboard())


@router.message(F.text == '📊 Статистика')
async def stats_handler(message: Message):
    """Показ статистики бота"""
    if message.from_user.id not in ADMIN_IDS:
        return

    total_users, recent_users = await db.get_users_stats()

    stats_text = f"📊 Статистика (v{BOT_VERSION}):\n"
    stats_text += f"👥 Пользователей: {total_users}\n\n"
    stats_text += "⚡ Последние активные:\n"

    for user in recent_users:
        stats_text += f"- {user[0]} (@{user[1]}) - {user[2][:10]}\n"

    await message.answer(stats_text)


@router.message(F.text == '🔄 Версия бота')
async def version_handler(message: Message):
    """Показ версии бота"""
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(f"🔧 Текущая версия: {BOT_VERSION}")


@router.message(F.text == '📁 Выгрузить БД (CSV)')
async def export_db_csv_handler(message: Message):
    """Экспорт пользователей с контролем размера файла"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        all_users = await db.get_all_users()
        total_users = len(all_users)

        if not all_users:
            await message.answer("🔄 База данных пуста")
            return

        MAX_FILE_SIZE_MB = 45  # Лимит Telegram
        BATCH_SIZE = 10000     # Записей на файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        batches = [all_users[i:i + BATCH_SIZE]
                   for i in range(0, total_users, BATCH_SIZE)]
        sent_files = 0

        for i, batch in enumerate(batches, 1):
            temp_file = os.path.join(
                FILES_DIR, f"users_part{i}_{timestamp}.csv")

            try:
                # Запись данных в CSV
                with open(temp_file, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(
                        f, delimiter=';', quoting=csv.QUOTE_ALL)
                    writer.writerow(
                        ['ID', 'Username', 'Имя', 'Фамилия', 'Дата регистрации', 'Последняя активность'])
                    for user in batch:
                        writer.writerow([
                            user[0],
                            f'"{user[1]}"' if user[1] else '',
                            f'"{user[2]}"' if user[2] else '',
                            f'"{user[3]}"' if user[3] else '',
                            user[4],
                            user[5]
                        ])

                # Проверка размера файла
                file_size_mb = os.path.getsize(temp_file) / (1024 * 1024)
                if file_size_mb > MAX_FILE_SIZE_MB:
                    logger.warning(
                        f"Файл part{i} превысил лимит: {file_size_mb:.2f}MB")
                    await message.answer(f"⚠️ Файл part{i} слишком большой ({file_size_mb:.2f}MB)")
                    continue

                # Отправка файла
                await message.answer_document(
                    FSInputFile(temp_file),
                    caption=f"Part {i}/{len(batches)} ({len(batch)} users)"
                )
                sent_files += 1

            except Exception as e:
                logger.error(f"Ошибка в part{i}: {e}")
                await message.answer(f"❌ Ошибка в part{i}: {str(e)}")

            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

        # Итоговый отчет
        await message.answer(
            f"✅ Экспорт завершен\n"
            f"• Всего пользователей: {total_users}\n"
            f"• Успешно отправлено: {sent_files}/{len(batches)} файлов\n"
            f"• Макс. размер файла: {MAX_FILE_SIZE_MB}MB"
        )

    except Exception as e:
        logger.critical(f"Критическая ошибка экспорта: {e}")
        await message.answer(f"🚨 Критическая ошибка: {str(e)}")

# -------------------------------
# Рассылка сообщений
# -------------------------------


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


@router.message(BroadcastState.waiting_message)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    """Обработка рассылки с исключением отправителя"""
    await state.clear()

    if message.from_user.id not in ADMIN_IDS:
        return

    users = await db.get_all_users()
    success = 0
    failed = 0
    sender_id = message.from_user.id  # ID отправителя рассылки

    await message.answer("⏳ Начинаю рассылку...", reply_markup=get_admin_keyboard())

    for user in users:
        user_id = user[0]  # Получаем ID пользователя из БД
        if user_id == sender_id:  # Пропускаем отправителя
            continue

        try:
            await bot.send_message(user_id, message.text)
            success += 1
            await asyncio.sleep(0.1)  # Задержка против флуда
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
            failed += 1

    # Добавляем информацию о пропуске отправителя
    await message.answer(
        f"✅ Рассылка завершена:\n"
        f"• Получателей: {len(users)-1}\n"  # -1 за счет отправителя
        f"• Доставлено: {success}\n"
        f"• Не доставлено: {failed}\n"
        f"• Пропущено (отправитель): 1",
        reply_markup=get_admin_keyboard()
    )


@router.message(F.text == '⬅️ Назад')
async def back_to_admin_menu(message: Message):
    """Возврат в админ-меню"""
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Админ-панель:", reply_markup=get_admin_keyboard())
