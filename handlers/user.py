from aiogram import Router, F, Bot, types
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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
from database.submissions import SubmissionDB


class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()


class BroadcastState(StatesGroup):
    waiting_message = State()


# Создаем глобальный экземпляр базы данных
submission_db = SubmissionDB()
router = Router()
db = Database()
logger = logging.getLogger(__name__)

# -------------------------------
# Обработчики материалов
# -------------------------------


@router.message(F.text == "📨 Обратная связь")
async def start_feedback(message: Message, state: FSMContext):
    """Начало процесса отправки обратной связи"""
    # Создаем клавиатуру с кнопками "Отправить", "История" и "Отменить"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 Отправить")],
            [KeyboardButton(text="📜 История")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "Отправьте ваше сообщение (текст + до 5 фото/файлов). Вы можете отправить несколько сообщений подряд, а затем нажать 'Отправить':",
        reply_markup=keyboard
    )
    await state.set_state(FeedbackStates.waiting_for_feedback)
    await state.update_data(accumulated_files=[], accumulated_text="")


# Новый обработчик для кнопки 'История' (должен быть выше универсального!)
@router.message(FeedbackStates.waiting_for_feedback, F.text == "📜 История")
async def show_user_history(message: types.Message, state: FSMContext, bot: Bot):
    await submission_db.init()
    if not submission_db.connection:
        if message:
            await message.answer("Ошибка: соединение с базой не установлено.")
        return
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.answer("Ошибка: не удалось определить пользователя.")
        return
    async with submission_db.connection.cursor() as cursor:
        await cursor.execute('SELECT id, text_content, file_ids, status, created_at FROM submissions WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = await cursor.fetchall()
    rows = list(rows) if rows else []
    if not rows:
        await message.answer("У вас пока нет обращений.")
        return
    # Формируем список обращений с кнопками
    buttons = []
    for row in rows[:10]:
        sub_id, text, file_ids, status, created_at = row
        preview = (
            text[:30] + "...") if text and len(text) > 30 else (text or "(без текста)")
        btn_text = f"{created_at[:16]}: {preview}"
        buttons.append([InlineKeyboardButton(
            text=btn_text, callback_data=f"mymsg_{sub_id}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Ваша история обращений:", reply_markup=keyboard)


# Универсальный обработчик для текста/фото/документов
@router.message(FeedbackStates.waiting_for_feedback, F.photo | F.document | F.text)
async def handle_feedback_content(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка обратной связи с накоплением текста и файлов"""
    try:
        if not message.from_user:
            logger.error("❌ Не удалось определить пользователя")
            await message.answer("❌ Ошибка: не удалось определить пользователя")
            await state.clear()
            return

        logger.info(f"🔄 Начало обработки сообщения от {message.from_user.id}")

        # Проверяем, не нажал ли пользователь кнопку "Отменить"
        if message.text == "❌ Отменить":
            logger.info("❌ Пользователь отменил отправку")
            await message.answer(
                "❌ Отправка отменена.",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
            await state.clear()
            return

        # Проверяем, не нажал ли пользователь кнопку "Отправить"
        if message.text == "📤 Отправить":
            logger.info("📤 Пользователь нажал 'Отправить'")
            user_data = await state.get_data()
            accumulated_text = user_data.get('accumulated_text', '') or ''
            accumulated_text = accumulated_text.strip()
            accumulated_files = user_data.get('accumulated_files', [])

            logger.info(
                f"📊 Данные для отправки: текст={len(accumulated_text)} символов, файлов={len(accumulated_files)}")

            if not accumulated_text and not accumulated_files:
                logger.warning("⚠️ Пользователь не отправил контент")
                await message.answer(
                    "❌ Вы не отправили ни текста, ни файлов. Пожалуйста, добавьте контент перед отправкой.",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard=[
                            [KeyboardButton(text="📤 Отправить")],
                            [KeyboardButton(text="❌ Отменить")]
                        ],
                        resize_keyboard=True
                    )
                )
                return

            # Инициализируем базу данных если нужно
            try:
                logger.info("🔗 Инициализация БД...")
                await submission_db.init()
                logger.info("✅ База данных инициализирована")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации БД: {e}")
                await message.answer("❌ Ошибка подключения к базе данных. Попробуйте позже.")
                return

            logger.info("💾 Начинаем сохранение в базу данных...")
            logger.info(f"👤 User ID: {message.from_user.id}")
            logger.info(
                f"👤 Username: {message.from_user.username or 'unknown'}")
            logger.info(f"📝 Text: {accumulated_text}")
            logger.info(f"📁 Files: {accumulated_files}")

            try:
                await submission_db.add_submission(
                    user_id=message.from_user.id,
                    username=message.from_user.username or "unknown",
                    text=accumulated_text,
                    file_ids=accumulated_files[:5]  # Ограничиваем 5 файлами
                )

                logger.info("✅ Успешно сохранено в базу данных!")
                user_id = message.from_user.id if message.from_user else 0
                await message.answer(
                    "✅ Сообщение отправлено! Спасибо за обратную связь.",
                    reply_markup=get_main_keyboard(user_id)
                )
                await state.clear()
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения в БД: {e}")
                logger.error(f"❌ Детали ошибки: {type(e).__name__}: {str(e)}")
                user_id = message.from_user.id if message.from_user else 0
                await message.answer(
                    "❌ Ошибка при сохранении сообщения. Попробуйте позже.",
                    reply_markup=get_main_keyboard(user_id)
                )
                await state.clear()
            return

        user_id = message.from_user.id if message.from_user else "unknown"
        username = message.from_user.username if message.from_user else "unknown"
        logger.info(
            f"📝 Получено сообщение от пользователя {user_id} (@{username})")
        message_type = "текст"
        if message.photo:
            message_type = "фото"
        elif message.document:
            message_type = "документ"
        if message.caption:
            message_type += " с подписью"
        logger.info(f"📄 Тип сообщения: {message_type}")

        user_data = await state.get_data()
        accumulated_files = user_data.get('accumulated_files', [])
        accumulated_text = user_data.get('accumulated_text', '') or ''

        # Обработка медиа
        if message.photo:
            logger.info("📸 Обработка фото...")
            file_id = message.photo[-1].file_id
            accumulated_files.append(file_id)
            logger.info(f"📸 Добавлено фото: {file_id}")
        elif message.document:
            logger.info("📄 Обработка документа...")
            file_id = message.document.file_id
            accumulated_files.append(file_id)
            logger.info(f"📄 Добавлен документ: {file_id}")

        # Обработка текста (включая caption к медиа)
        text_to_add = None
        if message.text:
            logger.info("📝 Обработка текста из message.text...")
            text_to_add = message.text
        elif message.caption:
            logger.info("📝 Обработка текста из message.caption...")
            text_to_add = message.caption

        if text_to_add:
            logger.info(f"📝 Добавляем текст: {text_to_add[:50]}...")
            if accumulated_text:
                new_text = accumulated_text + "\n\n" + text_to_add
            else:
                new_text = text_to_add
            accumulated_text = new_text
            logger.info(
                f"📝 Итоговый накопленный текст: {len(accumulated_text)} символов")

        # Обновляем состояние
        logger.info("💾 Обновление состояния...")
        await state.update_data(accumulated_files=accumulated_files, accumulated_text=accumulated_text)

        # Показываем клавиатуру с кнопками "Отправить" и "Отменить"
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📤 Отправить")],
                [KeyboardButton(text="❌ Отменить")]
            ],
            resize_keyboard=True
        )

        # Формируем сообщение о текущем состоянии
        status_message = f"✅ Контент добавлен!\n"
        if accumulated_text:
            status_message += f"📝 Текст: {len(accumulated_text)} символов\n"
        if accumulated_files:
            status_message += f"📁 Файлов: {len(accumulated_files)}/5\n"

        status_message += f"\nПродолжайте добавлять контент или нажмите 'Отправить' для завершения."

        logger.info("📤 Отправка статусного сообщения...")
        await message.answer(status_message, reply_markup=keyboard)
        logger.info("✅ Обработка сообщения завершена успешно")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в handle_feedback_content: {e}")
        logger.error(f"❌ Тип ошибки: {type(e).__name__}")
        logger.error(f"❌ Детали ошибки: {str(e)}")

        try:
            user_id = message.from_user.id if message.from_user else 0
            await message.answer(
                "❌ Произошла ошибка при обработке сообщения. Попробуйте еще раз.",
                reply_markup=get_main_keyboard(user_id)
            )
            await state.clear()
        except Exception as cleanup_error:
            logger.error(f"❌ Ошибка при очистке состояния: {cleanup_error}")


@router.message(F.text == '✉️ Сообщение пользователям')
async def broadcast_handler(message: Message, state: FSMContext):
    """Запуск процесса рассылки"""
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    # Клавиатура с кнопками 'Отправить' и 'Отменить'
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 Отправить")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "Введите сообщение для рассылки. Вы можете отправить несколько сообщений подряд, а затем нажать 'Отправить':",
        reply_markup=keyboard
    )
    await state.set_state(BroadcastState.waiting_message)
    await state.update_data(accumulated_text="")


# Обработчик для накопления текста, фото и документов, а также кнопок 'Отправить'/'Отменить' в рассылке
@router.message(BroadcastState.waiting_message, F.photo | F.document | F.text)
async def handle_broadcast_content(message: types.Message, state: FSMContext, bot: Bot):
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return
    user_id = message.from_user.id
    user_data = await state.get_data()
    accumulated_text = user_data.get('accumulated_text', '') or ''
    accumulated_files = user_data.get(
        'accumulated_files', []) if user_data.get('accumulated_files') else []

    # Кнопка отмены
    if message.text == "❌ Отменить":
        await message.answer(
            "❌ Рассылка отменена.",
            reply_markup=get_main_keyboard(user_id)
        )
        await state.clear()
        return

    # Кнопка отправки
    if message.text == "📤 Отправить":
        accumulated_text = accumulated_text.strip()
        if not accumulated_text and not accumulated_files:
            await message.answer(
                "❌ Вы не ввели текст или файлы для рассылки. Пожалуйста, добавьте контент перед отправкой.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="📤 Отправить")],
                        [KeyboardButton(text="❌ Отменить")]
                    ],
                    resize_keyboard=True
                )
            )
            return
        # Получаем всех пользователей
        users = await db.get_all_users()
        success = 0
        failed = 0
        for user in users:
            try:
                # Сначала отправляем файлы, если есть
                for file_id in accumulated_files[:5]:
                    await bot.send_photo(user[0], file_id)
                # Затем текст, если есть
                if accumulated_text:
                    await bot.send_message(user[0], accumulated_text)
                success += 1
            except Exception:
                failed += 1
        await message.answer(
            f"✅ Рассылка завершена.\nДоставлено: {success}\nНе доставлено: {failed}",
            reply_markup=get_main_keyboard(user_id)
        )
        await state.clear()
        return

    # Накопление фото
    if message.photo:
        file_id = message.photo[-1].file_id
        accumulated_files.append(file_id)
    # Накопление документов
    elif message.document:
        file_id = message.document.file_id
        accumulated_files.append(file_id)
    # Накопление текста
    text_to_add = None
    if message.text and message.text not in ["📤 Отправить", "❌ Отменить"]:
        text_to_add = message.text
    elif message.caption:
        text_to_add = message.caption
    if text_to_add:
        if accumulated_text:
            new_text = accumulated_text + "\n" + text_to_add
        else:
            new_text = text_to_add
        accumulated_text = new_text
    await state.update_data(accumulated_text=accumulated_text, accumulated_files=accumulated_files)
    # Показываем статус
    status_message = f"✅ Контент добавлен!\n"
    if accumulated_text:
        status_message += f"📝 Текст: {len(accumulated_text)} символов\n"
    if accumulated_files:
        status_message += f"📁 Файлов: {len(accumulated_files)}/5\n"
    status_message += f"\nПродолжайте добавлять контент или нажмите 'Отправить' для рассылки."
    await message.answer(
        status_message,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📤 Отправить")],
                [KeyboardButton(text="❌ Отменить")]
            ],
            resize_keyboard=True
        )
    )


@router.message(F.text == 'Установка БД')
async def send_db_guide(message: Message, bot: Bot):
    """Отправка гайда по базам данных"""
    if not message.from_user:
        await message.answer("❌ Ошибка: не удалось определить пользователя")
        return

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
    if not message.from_user:
        await message.answer("❌ Ошибка: не удалось определить пользователя")
        return

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
    if not message.from_user:
        await message.answer("❌ Ошибка: не удалось определить пользователя")
        return

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
    if not message.from_user:
        await message.answer("❌ Ошибка: не удалось определить пользователя")
        return

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
    if not message.from_user:
        await message.answer("❌ Ошибка: не удалось определить пользователя")
        return

    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


# Обработчик для просмотра конкретного обращения пользователя
@router.callback_query(F.data.startswith("mymsg_"))
async def show_user_submission_detail(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await submission_db.init()
    if not submission_db.connection:
        if callback.message:
            await callback.message.answer("Ошибка: соединение с базой не установлено.")
        await callback.answer()
        return
    if not callback.data:
        await callback.answer()
        return
    sub_id = int(callback.data.split("_")[1])
    async with submission_db.connection.cursor() as cursor:
        await cursor.execute('SELECT text_content, file_ids, status, admin_response, created_at FROM submissions WHERE id = ?', (sub_id,))
        row = await cursor.fetchone()
    if not row:
        if callback.message:
            await callback.message.answer("Обращение не найдено")
        await callback.answer()
        return
    row = list(row)
    text, file_ids, status, admin_response, created_at = row
    response = f"💬 Ваше обращение #{sub_id}\n"
    response += f"📅 Дата: {created_at}\n\n"
    response += f"📝 Текст:\n{text or '(нет текста)'}\n\n"
    # Добавляем кнопку "Назад"
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="myhistory_back")]
    ])
    if callback.message:
        await callback.message.answer(response, reply_markup=back_keyboard)
    # Если есть файлы, отправляем их отдельно
    if file_ids:
        import json
        files = json.loads(file_ids)
        for file_id in files[:5]:
            try:
                await bot.send_photo(callback.from_user.id, file_id)
            except Exception:
                pass
    await callback.answer()

# Обработчик для кнопки "Назад" в истории обращений


@router.callback_query(F.data == "myhistory_back")
async def back_to_user_history(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await submission_db.init()
    if not submission_db.connection:
        if callback.message:
            await callback.message.answer("Ошибка: соединение с базой не установлено.")
        await callback.answer()
        return
    user_id = callback.from_user.id if callback.from_user else None
    if not user_id:
        await callback.answer("Ошибка: не удалось определить пользователя.")
        return
    async with submission_db.connection.cursor() as cursor:
        await cursor.execute('SELECT id, text_content, file_ids, status, created_at FROM submissions WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = await cursor.fetchall()
    rows = list(rows) if rows else []
    if not rows:
        if callback.message:
            await callback.message.answer("У вас пока нет обращений.")
        await callback.answer()
        return
    buttons = []
    for row in rows[:10]:
        sub_id, text, file_ids, status, created_at = row
        preview = (
            text[:30] + "...") if text and len(text) > 30 else (text or "(без текста)")
        btn_text = f"{created_at[:16]}: {preview}"
        buttons.append([InlineKeyboardButton(
            text=btn_text, callback_data=f"mymsg_{sub_id}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer("Ваша история обращений:", reply_markup=keyboard)
    await callback.answer()
