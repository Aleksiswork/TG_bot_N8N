from aiogram import Router, F, Bot, types
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, InputMediaDocument
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import Database
from keyboards import get_admin_keyboard, get_bans_keyboard, get_ban_user_keyboard, get_unban_user_keyboard
from config import FILES_DIR, BOT_VERSION, ADMIN_IDS
from utils.checks import is_user_banned, ban_user, unban_user, get_ban_info, get_banned_db
from datetime import datetime
import os
import csv
import logging
import asyncio
from aiogram.types import ReplyKeyboardRemove
from database.submissions import SubmissionDB
import json
from typing import Union, Optional, Any
import platform

router = Router()
logger = logging.getLogger(__name__)
try:
    db = Database()
except Exception as e:
    db = None
    logger.error(f"Ошибка инициализации Database: {e}")
submission_db = SubmissionDB()


class BroadcastState(StatesGroup):
    waiting_message = State()


class SubmissionsViewState(StatesGroup):
    viewing_list = State()
    viewing_detail = State()
    waiting_response = State()
    confirm_delete = State()


# -------------------------------
# Команды администрирования
# -------------------------------


@router.message(F.text == '⚙️ Управление')
async def admin_panel(message: Message):
    """Отображение админ-панели"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Админ-панель:", reply_markup=get_admin_keyboard())


@router.message(F.text == '📊 Статистика')
async def stats_handler(message: Message):
    """Показ статистики бота"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    if db is None:
        await message.answer("❌ Ошибка: не удалось инициализировать подключение к базе данных. Обратитесь к администратору.")
        return
    stats = await db.get_users_stats()
    hostname = platform.node()

    stats_text = f"📊 Статистика (v{BOT_VERSION}):\n"
    stats_text += f"🖥️ Сервер: {hostname}\n"
    stats_text += f"👥 Пользователей: {stats[0]}\n\n"
    stats_text += "⚡ Последние активные:\n"

    for user in stats[1]:
        stats_text += f"- {user[0]} (@{user[1]}) - {user[2][:10]}\n"

    await message.answer(stats_text)


@router.message(F.text == '🔄 Версия бота')
async def version_handler(message: Message):
    """Показ версии бота"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(f"🔧 Текущая версия: {BOT_VERSION}")


@router.message(F.text == '📁 Выгрузить БД (CSV)')
async def export_db_csv_handler(message: Message):
    """Экспорт пользователей с контролем размера файла"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    try:
        if db is None:
            await message.answer("❌ Ошибка: не удалось получить пользователей из базы данных.")
            return
        users = await db.get_all_users()
        total_users = len(list(users))

        if not users:
            await message.answer("🔄 База данных пуста")
            return

        MAX_FILE_SIZE_MB = 45  # Лимит Telegram
        BATCH_SIZE = 10000     # Записей на файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        batches = [list(users)[i:i + BATCH_SIZE]
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

        if sent_files == 0:
            await message.answer("❌ Не удалось отправить ни одного файла")
        else:
            await message.answer(f"✅ Отправлено файлов: {sent_files}")

    except Exception as e:
        logger.error(f"🚨 Критическая ошибка: {e}")
        await message.answer(f"🚨 Критическая ошибка: {str(e)}")


@router.message(F.text == '📋 Просмотр записей')
async def view_submissions_handler(message: Message):
    """Просмотр всех записей из базы данных submissions"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    try:
        await submission_db.init()
        submissions = await submission_db.get_all_submissions()

        if not submissions:
            await message.answer("📭 База данных submissions пуста")
            return

        # Формируем сообщение с записями
        submissions_list = list(submissions)
        response = f"📋 Записи в базе данных ({len(submissions_list)} шт.):\n\n"

        # Показываем первые 10
        for i, submission in enumerate(submissions_list[:10], 1):
            id_, user_id, username, text, file_ids, created_at = submission
            text_preview = text[:50] + "..." if len(text) > 50 else text
            files_count = len(json.loads(file_ids)) if file_ids else 0

            response += f"{i}. ID: {id_}\n"
            response += f"   👤 User: {user_id} (@{username})\n"
            response += f"   📝 Text: {text_preview}\n"
            response += f"   📁 Files: {files_count}\n"
            response += f"   📅 Date: {created_at}\n\n"

        if len(submissions_list) > 10:
            response += f"... и ещё {len(submissions_list) - 10} записей"

        await message.answer(response, reply_markup=get_admin_keyboard())

    except Exception as e:
        logger.error(f"Ошибка при просмотре записей: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=get_admin_keyboard())


async def send_submissions_menu(message: Union[Message, CallbackQuery, Any]):
    """Отправляет меню предложки для любого типа сообщения"""
    try:
        await submission_db.init()
        stats = await submission_db.get_statistics()

        response = f"📋 Обратная связь\n\n"
        response += f"📊 Статистика:\n"
        response += f"• Всего: {stats['total']}\n"
        response += f"• Новые: {stats['new']}\n"
        response += f"• Решенные: {stats['solved']}\n"
        response += f"• Просмотренные: {stats['viewed']}\n\n"
        response += f"Выберите категорию для просмотра:"

        # Создаем inline клавиатуру
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 Все сообщения", callback_data="submissions_all"),
                    InlineKeyboardButton(
                        text="🆕 Новые", callback_data="submissions_new")
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Решенные", callback_data="submissions_solved"),
                    InlineKeyboardButton(
                        text="👁️ Просмотренные", callback_data="submissions_viewed")
                ]
            ]
        )

        if isinstance(message, Message):
            await message.answer(response, reply_markup=keyboard)
        elif isinstance(message, CallbackQuery) and message.message and isinstance(message.message, Message) and hasattr(message.message, 'edit_text'):
            try:
                await message.message.edit_text(response, reply_markup=keyboard)
            except Exception as e:
                # Игнорируем ошибку "message is not modified"
                if "message is not modified" not in str(e):
                    logger.error(f"Ошибка при редактировании сообщения: {e}")
                    await message.answer(response, reply_markup=keyboard)
        elif isinstance(message, CallbackQuery):
            await message.answer("Меню обновлено")
            # Отправляем новое сообщение с клавиатурой
            if message.message and message.message.chat and message.bot:
                try:
                    await message.bot.send_message(
                        chat_id=message.message.chat.id,
                        text=response,
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки нового сообщения: {e}")
        else:
            logger.error(f"Неизвестный тип сообщения: {type(message)}")

    except Exception as e:
        logger.error(f"Ошибка при отправке меню предложки: {e}")
        if isinstance(message, CallbackQuery):
            await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=get_admin_keyboard())


@router.message(F.text == '📋 Посмотреть предложку')
async def view_submissions_menu(message: Message):
    """Главное меню просмотра обратной связи"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return
    await send_submissions_menu(message)


@router.callback_query(F.data.startswith("submissions_"))
async def handle_submissions_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка callback для просмотра предложенных сообщений"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        if not callback.data:
            await callback.answer("❌ Ошибка данных")
            return

        action = callback.data.split("_")[1]

        # Обрабатываем "back" здесь же
        if action == "back":
            try:
                await send_submissions_menu(callback)
                await state.clear()
            except Exception as e:
                logger.error(f"Ошибка при возврате в меню предложки: {e}")
                await callback.answer("❌ Ошибка при возврате в меню предложки")
            return

        await submission_db.init()

        if action == "all":
            submissions = await submission_db.get_all_submissions()
            status_filter = "all"
        elif action in ["new", "solved", "viewed"]:
            submissions = await submission_db.get_submissions_by_status(action)
            status_filter = action
        else:
            await callback.answer("❌ Неизвестное действие")
            return

        if not submissions:
            await callback.answer(f"📭 Нет сообщений в категории '{action}'")
            return

        # Показываем список сообщений (первые 10)
        await show_submissions_list(callback, submissions[:10], 0, status_filter)
        await state.set_state(SubmissionsViewState.viewing_list)
        await state.update_data(submissions=submissions, current_page=0, status_filter=status_filter)

    except Exception as e:
        logger.error(f"Ошибка при обработке callback предложок: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}")


async def show_submissions_list(message: Union[Message, CallbackQuery, Any], submissions: list, page: int, status_filter: str):
    """Показывает список предложенных сообщений"""
    total_pages = (len(submissions) - 1) // 10 + 1
    start_idx = page * 10
    end_idx = min(start_idx + 10, len(submissions))

    response = f"📋 Обратная связь ({len(submissions)} шт.)\n"
    if status_filter != "all":
        status_names = {"new": "🆕 Новые",
                        "solved": "✅ Решенные", "viewed": "👁️ Просмотренные"}
        response += f"Фильтр: {status_names.get(status_filter, status_filter)}\n"
    response += f"\n"
    response += f"Выберите сообщение для просмотра:\n\n"

    # Навигационные кнопки
    keyboard_buttons = []

    # Кнопки для каждой идеи
    for i, submission in enumerate(submissions[start_idx:end_idx], start_idx + 1):
        id_, user_id, username, text, file_ids, status, admin_response, processed_at, viewed_at, created_at = submission
        text_preview = text[:30] + "..." if len(text) > 30 else text
        status_emoji = {"new": "🆕", "viewed": "👁️", "solved": "✅"}
        status_display = status_emoji.get(status, "❓")
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{status_display} {i}. @{username}: {text_preview}",
                callback_data=f"view_{id_}"
            )
        ])

    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Назад", callback_data=f"page_{page-1}"))
        nav_row.append(InlineKeyboardButton(
            text=f"{page+1}/{total_pages}", callback_data="page_info"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                text="Вперед ▶️", callback_data=f"page_{page+1}"))
        keyboard_buttons.append(nav_row)

    keyboard_buttons.append([InlineKeyboardButton(
        text="⬅️ Назад к меню", callback_data="submissions_back")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    if isinstance(message, Message):
        await message.answer(response, reply_markup=keyboard)
    elif isinstance(message, CallbackQuery) and message.message and isinstance(message.message, Message) and hasattr(message.message, 'edit_text'):
        try:
            await message.message.edit_text(response, reply_markup=keyboard)
        except Exception as e:
            # Игнорируем ошибку "message is not modified"
            if "message is not modified" not in str(e):
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                await message.answer(response, reply_markup=keyboard)
    elif isinstance(message, CallbackQuery):
        await message.answer(response, reply_markup=keyboard)


@router.callback_query(F.data.startswith("page_"))
async def handle_page_navigation(callback: CallbackQuery, state: FSMContext):
    """Обработка навигации по страницам"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        if not callback.data:
            await callback.answer("❌ Ошибка данных")
            return

        user_data = await state.get_data()
        submissions = user_data.get('submissions', [])
        status_filter = user_data.get('status_filter', 'all')

        if callback.data == "page_info":
            await callback.answer("Информация о странице")
            return

        page = int(callback.data.split("_")[1])
        await state.update_data(current_page=page)

        await show_submissions_list(callback, submissions, page, status_filter)

    except Exception as e:
        logger.error(f"Ошибка при навигации по страницам: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("view_"))
async def handle_view_submission(callback: CallbackQuery, state: FSMContext):
    """Обработка просмотра детальной информации о сообщении"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        if not callback.data:
            await callback.answer("❌ Ошибка данных")
            return

        submission_id = int(callback.data.split("_")[1])

        await submission_db.init()
        submission = await submission_db.get_submission_by_id(submission_id)

        if not submission:
            await callback.answer("❌ Сообщение не найдено")
            return

        # Отмечаем как просмотренное
        await submission_db.mark_as_viewed(submission_id)

        # Показываем детальную информацию
        await show_submission_detail(callback, submission, callback.bot)
        await state.set_state(SubmissionsViewState.viewing_detail)
        await state.update_data(current_submission_id=submission_id)

    except Exception as e:
        logger.error(f"Ошибка при просмотре сообщения: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}")


async def send_media_group_with_text(bot: Bot, message: Union[Message, CallbackQuery, Any], files: list, text: str, id_: int, username: str, status_display: str, created_at: str, keyboard: InlineKeyboardMarkup):
    """Отправляет медиа-группу с текстом и отдельное сообщение с кнопками"""
    try:
        # Ограничиваем количество файлов до 10 (лимит Telegram)
        files = files[:10]
        media_group = []
        for i, file_id in enumerate(files):
            if i == 0:
                media_item = InputMediaPhoto(
                    media=file_id,
                    caption=text
                )
            else:
                media_item = InputMediaPhoto(media=file_id)
            media_group.append(media_item)
        # Определяем chat_id
        chat_id = None
        if hasattr(message, 'from_user') and message.from_user:
            chat_id = message.from_user.id
        elif isinstance(message, CallbackQuery) and message.message and hasattr(message.message, 'chat'):
            chat_id = message.message.chat.id
        else:
            raise ValueError("Не удалось определить chat_id")
        # 1. Отправляем медиа-группу
        await bot.send_media_group(chat_id=chat_id, media=media_group)
        # 2. Отправляем отдельное сообщение с кнопками
        info_text = f"💬 Сообщение #{id_} от @{username}\n"
        info_text += f"📅 Дата: {created_at}\n"
        info_text += f"Статус: {status_display}\n\n"
        info_text += f"📝 Текст:\n{text}"
        await bot.send_message(
            chat_id=chat_id,
            text=info_text,
            reply_markup=keyboard
        )
        logger.info(
            f"✅ Медиа-группа и меню управления отправлены: {len(files)} файлов")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке медиа-группы: {e}")
        raise


async def show_submission_detail(message: Union[Message, CallbackQuery, Any], submission, bot: Optional[Bot] = None):
    """Показывает детальную информацию о сообщении"""
    id_, user_id, username, text, file_ids, status, admin_response, processed_at, viewed_at, created_at = submission
    status_names = {"new": "🆕 Новая",
                    "viewed": "👁️ Просмотрена", "solved": "✅ Решена"}
    status_display = status_names.get(status, "❓ Неизвестно")
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Решена", callback_data=f"solve_{id_}"),
                InlineKeyboardButton(
                    text="❌ Удалить", callback_data=f"delete_{id_}")
            ],
            [
                InlineKeyboardButton(
                    text="📤 Ответить", callback_data=f"reply_{id_}"),
                InlineKeyboardButton(
                    text="⬅️ Назад", callback_data="back_to_list")
            ]
        ]
    )
    # Если есть файлы, отправляем медиа-группу и отдельное меню
    if file_ids and bot:
        try:
            files = json.loads(file_ids)
            if files:
                await send_media_group_with_text(bot, message, files, text, id_, username, status_display, created_at, keyboard)
                return
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке медиа-группы: {e}")
    # Если нет файлов или произошла ошибка, отправляем обычное текстовое сообщение с кнопками
    response = f"💬 Сообщение #{id_} от @{username}\n"
    response += f"📅 Дата: {created_at}\n"
    response += f"Статус: {status_display}\n\n"
    response += f"📝 Текст:\n{text}\n\n"
    if file_ids:
        files = json.loads(file_ids)
        response += f"📁 Файлы ({len(files)}):\n"
        for i, file_id in enumerate(files, 1):
            response += f"{i}. {file_id}\n"
    if isinstance(message, Message):
        await message.answer(response, reply_markup=keyboard)
    elif isinstance(message, CallbackQuery) and message.message and isinstance(message.message, Message) and hasattr(message.message, 'edit_text'):
        try:
            await message.message.edit_text(response, reply_markup=keyboard)
        except Exception as e:
            if "message is not modified" not in str(e):
                logger.error(f"Ошибка при редактировании сообщения: {e}")
            await message.answer(response, reply_markup=keyboard)
    elif isinstance(message, CallbackQuery):
        await message.answer(response, reply_markup=keyboard)


@router.callback_query(F.data.startswith("solve_"))
async def handle_solve_submission(callback: CallbackQuery, state: FSMContext):
    """Обработка отметки сообщения как решенного"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        if not callback.data:
            await callback.answer("❌ Ошибка данных")
            return

        submission_id = int(callback.data.split("_")[1])

        await submission_db.init()
        await submission_db.mark_as_solved(submission_id)

        await callback.answer("✅ Сообщение отмечено как решенное")

        # Обновляем отображение
        submission = await submission_db.get_submission_by_id(submission_id)
        if submission and callback.message:
            await show_submission_detail(callback.message, submission, callback.bot)

    except Exception as e:
        logger.error(f"Ошибка при отметке как решенного: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("delete_"))
async def handle_delete_submission(callback: CallbackQuery, state: FSMContext):
    """Обработка удаления сообщения"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        if not callback.data:
            await callback.answer("❌ Ошибка данных")
            return

        submission_id = int(callback.data.split("_")[1])

        logger.info(f"🗑️ Запрос на удаление записи {submission_id}")

        # Показываем подтверждение
        response = f"⚠️ Подтверждение удаления\n\n"
        response += f"Сообщение #{submission_id} будет удалено безвозвратно.\n\n"
        response += f"Вы уверены?"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Да, удалить", callback_data=f"confirm_delete_{submission_id}"),
                    InlineKeyboardButton(
                        text="❌ Отмена", callback_data="cancel_delete")
                ]
            ]
        )

        if isinstance(callback.message, Message):
            await callback.message.edit_text(response, reply_markup=keyboard)
            await state.set_state(SubmissionsViewState.confirm_delete)
            await state.update_data(submission_to_delete=submission_id)

    except Exception as e:
        logger.error(f"Ошибка при удалении: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("confirm_delete_"))
async def handle_confirm_delete(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        if not callback.data:
            await callback.answer("❌ Ошибка данных")
            return

        submission_id = int(callback.data.split("_")[2])  # confirm_delete_ID

        logger.info(f"🗑️ Попытка удаления записи {submission_id}")
        await submission_db.init()
        await submission_db.delete_submission(submission_id)
        logger.info(f"✅ Запись {submission_id} успешно удалена из БД")

        await callback.answer("✅ Сообщение удалено")

        # Удаляем сообщение с подтверждением удаления
        if isinstance(callback.message, Message):
            try:
                await callback.message.delete()
                logger.info("🗑️ Сообщение с подтверждением удаления удалено")
            except Exception as e:
                logger.error(
                    f"❌ Не удалось удалить сообщение с подтверждением: {e}")

        # Возвращаемся к списку
        await state.set_state(SubmissionsViewState.viewing_list)
        user_data = await state.get_data()
        submissions = user_data.get('submissions', [])
        current_page = user_data.get('current_page', 0)
        status_filter = user_data.get('status_filter', 'all')

        # Удаляем удаленное сообщение из списка
        submissions = [s for s in submissions if s[0] != submission_id]
        await state.update_data(submissions=submissions)

        # Отправляем обновлённый список сообщений вместо админ-панели
        if callback.from_user:
            try:
                if callback.message:
                    await show_submissions_list(
                        callback.message,
                        submissions,
                        current_page,
                        status_filter
                    )
                    await state.set_state(SubmissionsViewState.viewing_list)
                else:
                    await callback.answer("✅ Запись удалена. Вернитесь к списку сообщений.")
            except Exception as e:
                logger.error(f"❌ Ошибка при возврате к списку сообщений: {e}")
                await callback.answer("✅ Запись удалена")

    except Exception as e:
        logger.error(f"Ошибка при подтверждении удаления: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "cancel_delete")
async def handle_cancel_delete(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        user_data = await state.get_data()
        submission_id = user_data.get('current_submission_id')

        if submission_id and callback.message:
            await submission_db.init()
            submission = await submission_db.get_submission_by_id(submission_id)
            if submission:
                await show_submission_detail(callback.message, submission, callback.bot)
                await state.set_state(SubmissionsViewState.viewing_detail)

    except Exception as e:
        logger.error(f"Ошибка при отмене удаления: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("reply_"))
async def handle_reply_submission(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на сообщение"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        if not callback.data:
            await callback.answer("❌ Ошибка данных")
            return

        submission_id = int(callback.data.split("_")[1])

        await state.set_state(SubmissionsViewState.waiting_response)
        await state.update_data(submission_to_reply=submission_id)

        response = f"📤 Ответ на сообщение #{submission_id}\n\n"
        response += f"Введите ваш ответ пользователю:"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text="❌ Отмена", callback_data="cancel_reply")]]
        )

        if isinstance(callback.message, Message):
            await callback.message.edit_text(response, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка при ответе: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "cancel_reply")
async def handle_cancel_reply(callback: CallbackQuery, state: FSMContext):
    """Отмена ответа"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        user_data = await state.get_data()
        submission_id = user_data.get('current_submission_id')

        if submission_id and callback.message:
            await submission_db.init()
            submission = await submission_db.get_submission_by_id(submission_id)
            if submission:
                await show_submission_detail(callback.message, submission, callback.bot)
                await state.set_state(SubmissionsViewState.viewing_detail)

    except Exception as e:
        logger.error(f"Ошибка при отмене ответа: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}")


@router.message(SubmissionsViewState.waiting_response)
async def handle_response_text(message: Message, state: FSMContext, bot: Bot):
    """Обработка текста ответа"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    try:
        user_data = await state.get_data()
        submission_id = user_data.get('submission_to_reply')

        if not submission_id:
            await message.answer("❌ Ошибка: ID сообщения не найден")
            await state.clear()
            return

        await submission_db.init()
        submission = await submission_db.get_submission_by_id(submission_id)

        if not submission:
            await message.answer("❌ Сообщение не найдено")
            await state.clear()
            return

        # Отправляем ответ пользователю
        user_id = submission[1]  # user_id из записи
        response_text = f"💬 Ответ на ваше сообщение #{submission_id}:\n\n{message.text}"

        try:
            await bot.send_message(user_id, response_text)
            await message.answer("✅ Ответ отправлен пользователю")
        except Exception as e:
            logger.error(f"Ошибка отправки ответа пользователю: {e}")
            await message.answer("❌ Не удалось отправить ответ пользователю")

        # Возвращаемся к детальному просмотру
        await show_submission_detail(message, submission, bot)
        await state.set_state(SubmissionsViewState.viewing_detail)
        await state.update_data(current_submission_id=submission_id)

    except Exception as e:
        logger.error(f"Ошибка при обработке ответа: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()


@router.callback_query(F.data == "back_to_list")
async def handle_back_to_list(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку сообщений"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещен")
        return

    try:
        user_data = await state.get_data()
        submissions = user_data.get('submissions', [])
        current_page = user_data.get('current_page', 0)
        status_filter = user_data.get('status_filter', 'all')

        if callback.message:
            await show_submissions_list(callback.message, submissions, current_page, status_filter)
            await state.set_state(SubmissionsViewState.viewing_list)

    except Exception as e:
        logger.error(f"Ошибка при возврате к списку: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}")


# -------------------------------
# Рассылка сообщений
# -------------------------------


@router.message(F.text == '✉️ Сообщение пользователям')
async def broadcast_handler(message: Message, state: FSMContext):
    """Запуск процесса рассылки"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
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

    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    if db is None:
        await message.answer("❌ Ошибка: не удалось инициализировать подключение к базе данных. Обратитесь к администратору.")
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
            await bot.send_message(user_id, message.text or "")
            success += 1
            await asyncio.sleep(0.1)  # Задержка против флуда
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
            failed += 1

    # Добавляем информацию о пропуске отправителя
    await message.answer(
        f"✅ Рассылка завершена:\n"
        f"• Получателей: {len(list(users))-1}\n"  # -1 за счет отправителя
        f"• Доставлено: {success}\n"
        f"• Не доставлено: {failed}\n"
        f"• Пропущено (отправитель): 1",
        reply_markup=get_admin_keyboard()
    )


@router.message(F.text == '⬅️ Назад')
async def back_to_admin_menu(message: Message, state: FSMContext):
    """Возврат назад: если в деталях — к списку сообщений, иначе — в админ-меню"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return
    current_state = await state.get_state()
    if current_state == SubmissionsViewState.viewing_detail.state:
        # Возврат к списку сообщений
        user_data = await state.get_data()
        submissions = user_data.get('submissions', [])
        current_page = user_data.get('current_page', 0)
        status_filter = user_data.get('status_filter', 'all')
        await show_submissions_list(message, submissions, current_page, status_filter)
        await state.set_state(SubmissionsViewState.viewing_list)
    else:
        await message.answer("Админ-панель:", reply_markup=get_admin_keyboard())


# -------------------------------
# Обработчики блокировок
# -------------------------------


@router.message(F.text == '🚫 Блокировки')
async def bans_menu_handler(message: Message):
    """Меню управления блокировками"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    await message.answer("🚫 Управление блокировками:", reply_markup=get_bans_keyboard())


@router.message(F.text == '📋 Список заблокированных')
async def banned_list_handler(message: Message):
    """Показ списка заблокированных пользователей"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    try:
        banned_db = get_banned_db()
        banned_users = await banned_db.get_banned_list()

        if not banned_users:
            await message.answer("✅ Нет заблокированных пользователей")
            return

        response = f"📋 Заблокированные пользователи ({len(banned_users)}):\n\n"

        for i, user in enumerate(banned_users[:10], 1):
            user_id = user['user_id']
            username = user['username'] or "unknown"
            reason = user['reason'][:50] + \
                "..." if len(user['reason']) > 50 else user['reason']
            ban_count = user['ban_count']
            banned_at = user['banned_at'][:16]

            if user['is_permanent']:
                status = "🔴 НАВСЕГДА"
            elif user['expires_at']:
                status = f"🟡 До {user['expires_at'][:16]}"
            else:
                status = "🟠 Временная"

            response += f"{i}. @{username} (ID: {user_id})\n"
            response += f"   Причина: {reason}\n"
            response += f"   Статус: {status}\n"
            response += f"   Блокировок: {ban_count}\n"
            response += f"   Дата: {banned_at}\n\n"

        if len(banned_users) > 10:
            response += f"... и ещё {len(banned_users) - 10} пользователей"

        await message.answer(response)

    except Exception as e:
        logger.error(f"Ошибка получения списка заблокированных: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(F.text == '📊 Статистика блокировок')
async def bans_stats_handler(message: Message):
    """Показ статистики блокировок"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    try:
        banned_db = get_banned_db()
        stats = await banned_db.get_ban_stats()

        response = f"📊 Статистика блокировок:\n\n"
        response += f"🔴 Всего заблокированных: {stats['total']}\n"
        response += f"🟡 Временные блокировки: {stats['temporary']}\n"
        response += f"🔴 Постоянные блокировки: {stats['permanent']}\n"
        response += f"📅 Заблокировано сегодня: {stats['today']}\n"

        await message.answer(response)

    except Exception as e:
        logger.error(f"Ошибка получения статистики блокировок: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(F.text == '🔍 Найти пользователя')
async def find_user_handler(message: Message, state: FSMContext):
    """Поиск пользователя для блокировки/разблокировки"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "🔍 Введите ID пользователя или @username для поиска:\n"
        "Примеры:\n"
        "- 123456789\n"
        "- @username\n"
        "- username (без @)"
    )
    await state.set_state("waiting_user_search")


@router.message(F.text == '🧹 Очистить истекшие')
async def cleanup_expired_handler(message: Message):
    """Очистка истекших блокировок"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    try:
        banned_db = get_banned_db()
        cleaned_count = await banned_db.cleanup_expired_bans()

        await message.answer(f"✅ Очищено {cleaned_count} истекших блокировок")

    except Exception as e:
        logger.error(f"Ошибка очистки истекших блокировок: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(F.text == '⬅️ Назад в админ-панель')
async def back_to_admin_from_bans(message: Message, state: FSMContext):
    """Возврат из меню блокировок в админ-панель"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    await message.answer("Админ-панель:", reply_markup=get_admin_keyboard())
    await state.clear()


# Состояния для поиска пользователей
class BanStates(StatesGroup):
    waiting_user_search = State()
    waiting_ban_reason = State()


@router.message(BanStates.waiting_user_search)
async def process_user_search(message: Message, state: FSMContext):
    """Обработка поиска пользователя"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    search_query = message.text.strip() if message.text else ""

    try:
        # Парсим ID или username
        user_id = None
        username = None

        if search_query.isdigit():
            user_id = int(search_query)
        elif search_query.startswith('@'):
            username = search_query[1:]
        else:
            username = search_query

        # Проверяем, заблокирован ли пользователь
        if user_id:
            is_banned = await is_user_banned(user_id)
            ban_info = await get_ban_info(user_id) if is_banned else None
        else:
            # Для username нужно найти ID (упрощенная версия)
            await message.answer("⚠️ Поиск по username пока не поддерживается. Используйте ID пользователя.")
            await state.clear()
            return

        if is_banned and ban_info:
            # Пользователь заблокирован - предлагаем разблокировать
            keyboard = get_unban_user_keyboard(
                user_id, ban_info.get('username'))
            await message.answer(
                f"🔍 Найден заблокированный пользователь:\n\n"
                f"ID: {user_id}\n"
                f"Username: @{ban_info.get('username', 'unknown')}\n"
                f"Причина: {ban_info.get('reason', 'Не указана')}\n"
                f"Блокировок: {ban_info.get('ban_count', 1)}\n"
                f"Дата: {ban_info.get('banned_at', 'Неизвестно')[:16]}\n\n"
                f"Хотите разблокировать?",
                reply_markup=keyboard
            )
        else:
            # Пользователь не заблокирован - предлагаем заблокировать
            keyboard = get_ban_user_keyboard(user_id, "unknown")
            await message.answer(
                f"🔍 Найден пользователь:\n\n"
                f"ID: {user_id}\n"
                f"Username: @unknown\n\n"
                f"Пользователь не заблокирован. Хотите заблокировать?",
                reply_markup=keyboard
            )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка поиска пользователя: {e}")
        await message.answer(f"❌ Ошибка поиска: {str(e)}")
        await state.clear()


@router.callback_query(F.data.startswith("ban_user:"))
async def ban_user_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка блокировки пользователя"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет доступа")
        return

    user_id = int(callback.data.split(":")[1]) if callback.data else 0

    if callback.message:
        await callback.message.edit_text(  # type: ignore
            f"🚫 Блокировка пользователя {user_id}\n\n"
            f"Введите причину блокировки:"
        )

    await state.update_data(ban_user_id=user_id)
    await state.set_state(BanStates.waiting_ban_reason)


@router.callback_query(F.data.startswith("unban_user:"))
async def unban_user_callback(callback: CallbackQuery):
    """Обработка разблокировки пользователя"""
    if not callback.from_user or callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет доступа")
        return

    user_id = int(callback.data.split(":")[1]) if callback.data else 0

    try:
        success = await unban_user(user_id)

        if success and callback.message:
            await callback.answer(f"✅ Пользователь {user_id} разблокирован")
        elif callback.message:
            await callback.answer(f"❌ Ошибка разблокировки пользователя {user_id}")

    except Exception as e:
        logger.error(f"Ошибка разблокировки: {e}")
        if callback.message:
            await callback.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "cancel_ban")
async def cancel_ban_callback(callback: CallbackQuery):
    """Отмена блокировки"""
    await callback.answer("❌ Блокировка отменена")


@router.callback_query(F.data == "cancel_unban")
async def cancel_unban_callback(callback: CallbackQuery):
    """Отмена разблокировки"""
    await callback.answer("❌ Разблокировка отменена")


@router.message(BanStates.waiting_ban_reason)
async def process_ban_reason(message: Message, state: FSMContext):
    """Обработка причины блокировки"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    user_data = await state.get_data()
    ban_user_id = user_data.get('ban_user_id')
    reason = message.text.strip() if message.text else ""

    if not ban_user_id or not reason:
        await message.answer("❌ Ошибка: не удалось получить данные")
        await state.clear()
        return

    try:
        # Блокируем пользователя
        ban_result = await ban_user(ban_user_id, "unknown", reason, message.from_user.id)

        ban_count = ban_result.get('ban_count', 1)
        duration = "24 часа" if ban_count == 1 else "7 дней" if ban_count == 2 else "навсегда"

        await message.answer(
            f"✅ Пользователь {ban_user_id} заблокирован\n\n"
            f"Причина: {reason}\n"
            f"Длительность: {duration}\n"
            f"Блокировка №{ban_count}"
        )

    except ValueError as e:
        if "администратора" in str(e):
            await message.answer("❌ Невозможно заблокировать администратора")
        else:
            await message.answer(f"❌ Ошибка блокировки: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка блокировки: {e}")
        await message.answer(f"❌ Ошибка блокировки: {str(e)}")

    await state.clear()
