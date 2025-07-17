import asyncio
import time
from typing import Optional
from aiogram import Router, F, Bot, types
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from database import Database
from keyboards import (
    get_subscribe_keyboard,
    get_main_keyboard
)
from utils import check_subscription
from utils.checks import is_user_banned, ban_user, get_user_info, get_ban_info
from config import FILES_DIR, ADMIN_IDS
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
import os
import logging
from database.submissions import SubmissionDB


class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()
    waiting_for_reply = State()


class BroadcastState(StatesGroup):
    waiting_message = State()


# Создаем глобальный экземпляр базы данных
submission_db = SubmissionDB()
router = Router()
logger = logging.getLogger(__name__)
try:
    db = Database()
except Exception as e:
    db = None
    logger.error(f"Ошибка инициализации Database: {e}")

# Система отслеживания активности для автоматической блокировки
user_activity = {}  # {user_id: {'messages': [], 'last_message': timestamp}}


async def check_user_activity(user_id: int, message_text: Optional[str] = None) -> tuple[bool, str]:
    """
    Проверяет активность пользователя и автоматически блокирует при нарушении правил

    Returns:
        tuple[bool, str]: (можно продолжить, причина блокировки если заблокирован)
    """
    current_time = time.time()

    if user_id not in user_activity:
        user_activity[user_id] = {
            'messages': [],
            'last_message': current_time,
            'duplicate_count': 0,
            'last_text': None
        }

    user_data = user_activity[user_id]

    # Очищаем старые сообщения (старше 1 минуты)
    user_data['messages'] = [msg for msg in user_data['messages']
                             if current_time - msg < 60]

    # Добавляем текущее сообщение
    user_data['messages'].append(current_time)
    user_data['last_message'] = current_time

    # Проверяем количество сообщений за минуту
    if len(user_data['messages']) > 5:
        reason = "Спам: более 5 сообщений за минуту"
        await auto_ban_user(user_id, reason)
        return False, reason

    # Проверяем дублирование сообщений
    if message_text:
        if user_data['last_text'] == message_text:
            user_data['duplicate_count'] += 1
            if user_data['duplicate_count'] >= 3:
                reason = "Спам: отправка одинаковых сообщений"
                await auto_ban_user(user_id, reason)
                return False, reason
        else:
            user_data['duplicate_count'] = 0
            user_data['last_text'] = message_text

    return True, ""


async def auto_ban_user(user_id: int, reason: str):
    """Автоматически блокирует пользователя"""
    try:
        # Получаем информацию о пользователе из БД или создаем базовую
        username = "unknown"
        try:
            if db:
                # Получаем всех пользователей и ищем нужного
                users = await db.get_all_users()
                for user in users:
                    if user[0] == user_id:  # user[0] is user_id
                        username = user[1] or "unknown"  # user[1] is username
                        break
                else:
                    username = "unknown"
        except:
            username = "unknown"

        # Блокируем пользователя
        # 0 = система
        ban_result = await ban_user(user_id, username, reason, 0)

        # Уведомляем всех админов
        if bot:
            for admin_id in ADMIN_IDS:
                try:
                    ban_count = ban_result.get('ban_count', 1)
                    duration = "24 часа" if ban_count == 1 else "7 дней" if ban_count == 2 else "навсегда"

                    await bot.send_message(
                        admin_id,
                        f"🚫 Автоматическая блокировка пользователя:\n"
                        f"ID: {user_id}\n"
                        f"Username: @{username}\n"
                        f"Причина: {reason}\n"
                        f"Блокировка: {duration}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка уведомления админа {admin_id}: {e}")

    except ValueError as e:
        if "администратора" in str(e):
            logger.info(
                f"Попытка автоматической блокировки администратора {user_id} отклонена")
        else:
            logger.error(f"Ошибка автоматической блокировки: {e}")
    except Exception as e:
        logger.error(f"Ошибка автоматической блокировки: {e}")


# Глобальная переменная для бота (будет установлена в main.py)
bot = None


def set_bot_instance(bot_instance):
    """Устанавливает глобальный экземпляр бота"""
    global bot
    bot = bot_instance

# -------------------------------
# Обработчики материалов
# -------------------------------


@router.message(F.text == "📨 Обратная связь")
async def start_feedback(message: Message, state: FSMContext):
    """Начало процесса отправки обратной связи"""
    if not message.from_user:
        return

    # Проверяем блокировку
    is_banned = await is_user_banned(message.from_user.id)
    ban_info = await get_ban_info(message.from_user.id) if is_banned else None
    ban_text = ""
    if is_banned and ban_info:
        if ban_info['is_permanent']:
            ban_text = "\n\n🚫 Вы заблокированы навсегда за нарушение правил. Вы можете отправлять только 1 обращение в неделю, пока блокировка не снята."
        else:
            ban_text = f"\n\n🚫 Вы заблокированы до {ban_info['expires_at'][:16]} за нарушение правил. Вы можете отправлять только 1 обращение в неделю, пока блокировка не снята."

    # Создаем клавиатуру с кнопками "Отправить", "История" и "Отменить"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 Отправить")],
            [KeyboardButton(text="📜 История")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )

    rules_text = f"""
📨 **Обратная связь**

Отправьте ваше сообщение (текст + до 5 фото/файлов). Вы можете отправить несколько сообщений подряд, а затем нажать 'Отправить'.

Чтобы продолжить общение по уже созданному обращению, откройте '📜 История', выберете нужное обращение и используйте кнопку 'Ответить'.

⚠️ **Правила:**
• Не спамить (не более 5 сообщений подряд за минуту)
• Не отправлять одинаковые сообщения
• Не превышать лимит файлов (5 файлов на обращение)
• Уважительно относиться к администрации

🚫 **Нарушение правил приведет к блокировке:**
• 1-е нарушение: 24 часа
• 2-е нарушение: 7 дней  
• 3-е нарушение: навсегда
{ban_text}
"""

    await message.answer(rules_text, reply_markup=keyboard)
    await state.set_state(FeedbackStates.waiting_for_feedback)
    await state.update_data(accumulated_files=[], accumulated_text="")


# Новый обработчик для кнопки 'История' (должен быть выше универсального!)
@router.message(FeedbackStates.waiting_for_feedback, F.text == "📜 История")
async def show_user_history(message: types.Message, state: FSMContext, bot: Bot):
    await submission_db.init()
    if not submission_db.connection:
        if message:
            await message.answer("Ошибка: соединение с базой не установлено.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
        return
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.answer("Ошибка: не удалось определить пользователя.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
        return
    async with submission_db.connection.cursor() as cursor:
        await cursor.execute('SELECT id, text_content, file_ids, status, created_at FROM submissions WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = await cursor.fetchall()
    rows = list(rows) if rows else []
    if not rows:
        await message.answer("У вас пока нет обращений.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
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
            await message.answer("❌ Ошибка: не удалось определить пользователя", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
            await state.clear()
            return

        user_id = message.from_user.id
        is_banned = await is_user_banned(user_id)
        ban_info = await get_ban_info(user_id) if is_banned else None

        # Проверяем активность пользователя
        message_text = message.text or message.caption or ""
        can_continue, ban_reason = await check_user_activity(user_id, message_text)

        if not can_continue:
            await message.answer(f"🚫 Вы заблокированы автоматически за: {ban_reason}", reply_markup=get_main_keyboard(user_id))
            return

        # Проверяем, не нажал ли пользователь кнопку "Отменить"
        if message.text == "❌ Отменить":
            await message.answer(
                "❌ Отправка отменена.",
                reply_markup=get_main_keyboard(user_id)
            )
            await state.clear()
            return

        # Проверяем, не нажал ли пользователь кнопку "Отправить"
        if message.text == "📤 Отправить":
            user_data = await state.get_data()
            accumulated_text = user_data.get('accumulated_text', '') or ''
            accumulated_text = accumulated_text.strip()
            accumulated_files = user_data.get('accumulated_files', [])

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

            # --- Новый блок: ограничение для забаненных ---
            if is_banned and ban_info:
                await submission_db.init()
                last_time_str = await submission_db.get_last_submission_time(user_id)
                import datetime
                now = datetime.datetime.now()
                if last_time_str:
                    try:
                        last_time = datetime.datetime.fromisoformat(
                            last_time_str)
                    except Exception:
                        last_time = None
                    if last_time:
                        delta = now - last_time
                        if delta.total_seconds() < 7*24*3600:
                            # осталось времени до следующей попытки
                            left = 7*24*3600 - delta.total_seconds()
                            days = int(left // (24*3600))
                            hours = int((left % (24*3600)) // 3600)
                            minutes = int((left % 3600) // 60)
                            left_str = f"{days}д {hours}ч {minutes}м"
                            if ban_info['is_permanent']:
                                ban_text = f"🚫 Вы заблокированы навсегда. Следующее обращение будет доступно через: {left_str}"
                            else:
                                ban_text = f"🚫 Вы заблокированы до {ban_info['expires_at'][:16]}. Следующее обращение будет доступно через: {left_str}"
                            await message.answer(ban_text, reply_markup=get_main_keyboard(user_id))
                            return
            # --- Конец блока ---

            # Инициализируем базу данных если нужно
            try:
                await submission_db.init()
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации БД: {e}")
                await message.answer("❌ Ошибка подключения к базе данных. Попробуйте позже.", reply_markup=get_main_keyboard(user_id))
                return

            try:
                await submission_db.add_submission(
                    user_id=user_id,
                    username=message.from_user.username or "unknown",
                    text=accumulated_text,
                    file_ids=accumulated_files[:5]  # Ограничиваем 5 файлами
                )

                await message.answer(
                    "✅ Сообщение отправлено! Спасибо за обратную связь.",
                    reply_markup=get_main_keyboard(user_id)
                )
                await state.clear()
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения в БД: {e}")
                await message.answer(
                    "❌ Ошибка при сохранении сообщения. Попробуйте позже.",
                    reply_markup=get_main_keyboard(user_id)
                )
                await state.clear()
            return

        user_id = message.from_user.id if message.from_user else "unknown"
        username = message.from_user.username if message.from_user else "unknown"

        user_data = await state.get_data()
        accumulated_files = user_data.get('accumulated_files', [])
        accumulated_text = user_data.get('accumulated_text', '') or ''

        # Обработка медиа
        if message.photo:
            file_id = message.photo[-1].file_id
            accumulated_files.append(file_id)
        elif message.document:
            file_id = message.document.file_id
            accumulated_files.append(file_id)

        # Обработка текста (включая caption к медиа)
        text_to_add = None
        if message.text:
            text_to_add = message.text
        elif message.caption:
            text_to_add = message.caption

        if text_to_add:
            if accumulated_text:
                new_text = accumulated_text + "\n\n" + text_to_add
            else:
                new_text = text_to_add
            accumulated_text = new_text

        # Обновляем состояние
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

        await message.answer(status_message, reply_markup=keyboard)

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
        if db is not None:
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
        else:
            await message.answer("❌ Ошибка: не удалось получить пользователей из базы данных.", reply_markup=get_main_keyboard(user_id))
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
    if db is None:
        await message.answer("❌ Ошибка: не удалось инициализировать подключение к базе данных. Обратитесь к администратору.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
        return
    if not message.from_user:
        await message.answer("❌ Ошибка: не удалось определить пользователя", reply_markup=get_main_keyboard(0))
        return

    await db.save_user(message.from_user)

    if not await check_subscription(message.from_user.id, bot):
        await message.answer(
            "❌ Для доступа к материалам необходимо подписаться на канал!",
            reply_markup=get_subscribe_keyboard()
        )
        return

    file_path = os.path.join(FILES_DIR, 'temp.txt')
    try:
        document = FSInputFile(file_path, filename="guide_bd.txt")
        await message.answer_document(document, caption="📚 Гайд по базам данных", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
    except FileNotFoundError:
        await message.answer("⚠️ Файл с гайдом временно недоступен.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
    except Exception as e:
        logger.error(f"Ошибка при отправке гайда БД: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))


@router.message(F.text == 'Фаервол и ssh-keygen')
async def send_firewall_guide(message: Message, bot: Bot):
    """Отправка гайда по фаерволу"""
    if not message.from_user:
        await message.answer("❌ Ошибка: не удалось определить пользователя", reply_markup=get_main_keyboard(0))
        return

    if db is None:
        await message.answer("❌ Ошибка: не удалось инициализировать подключение к базе данных. Обратитесь к администратору.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
        return
    await db.save_user(message.from_user)

    if not await check_subscription(message.from_user.id, bot):
        await message.answer(
            "❌ Для доступа к материалам необходимо подписаться на канал!",
            reply_markup=get_subscribe_keyboard()
        )
        return

    file_path = os.path.join(FILES_DIR, 'bonus.pdf')
    try:
        document = FSInputFile(file_path, filename="bonus.pdf")
        await message.answer_document(document, caption="📚 Гайд по фаерволу и ssh-keygen", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
    except FileNotFoundError:
        await message.answer("⚠️ Файл с гайдом временно недоступен.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
    except Exception as e:
        logger.error(f"Ошибка при отправке гайда: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))


@router.message(F.text == 'Установка N8N')
async def send_n8n_guide(message: Message, bot: Bot):
    """Отправка гайда по N8N"""
    if not message.from_user:
        await message.answer("❌ Ошибка: не удалось определить пользователя", reply_markup=get_main_keyboard(0))
        return

    if db is None:
        await message.answer("❌ Ошибка: не удалось инициализировать подключение к базе данных. Обратитесь к администратору.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
        return
    await db.save_user(message.from_user)

    file_path = os.path.join(FILES_DIR, 'install.pdf')
    try:
        document = FSInputFile(file_path, filename="install.pdf")
        await message.answer_document(document, caption="📚 Гайд по установке N8N", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
    except FileNotFoundError:
        await message.answer("⚠️ Файл с гайдом временно недоступен.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
    except Exception as e:
        logger.error(f"Ошибка при отправке гайда: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))

# -------------------------------
# Прочие обработчики
# -------------------------------


@router.message(F.text == 'Фишки')
async def send_tips(message: Message, bot: Bot):
    """Полезные фишки"""
    if not message.from_user:
        await message.answer("❌ Ошибка: не удалось определить пользователя", reply_markup=get_main_keyboard(0))
        return

    if db is None:
        await message.answer("❌ Ошибка: не удалось инициализировать подключение к базе данных. Обратитесь к администратору.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
        return
    await db.save_user(message.from_user)

    if not await check_subscription(message.from_user.id, bot):
        await message.answer(
            "❌ Для доступа необходимо подписаться на канал!",
            reply_markup=get_subscribe_keyboard()
        )
        return

    await message.answer("Здесь будут полезные фишки...", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))


@router.message(F.text == '⬅️ Назад')
async def back_to_main(message: Message):
    """Возврат в главное меню"""
    if not message.from_user:
        await message.answer("❌ Ошибка: не удалось определить пользователя", reply_markup=get_main_keyboard(0))
        return

    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


# === Новый обработчик для кнопки "📜 История" вне состояния обратной связи ===
@router.message(F.text == "📜 История")
async def show_user_history_anytime(message: types.Message, bot: Bot):
    """
    Позволяет любому пользователю (в том числе заблокированному) просматривать свою историю обращений из главного меню.
    """
    await submission_db.init()
    if not submission_db.connection:
        if message:
            await message.answer("Ошибка: соединение с базой не установлено.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
        return
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.answer("Ошибка: не удалось определить пользователя.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
        return
    async with submission_db.connection.cursor() as cursor:
        await cursor.execute('SELECT id, text_content, file_ids, status, created_at FROM submissions WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = await cursor.fetchall()
    rows = list(rows) if rows else []
    if not rows:
        await message.answer("У вас пока нет обращений.", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
        return
    # Формируем список обращений с кнопками
    buttons = []
    for row in rows[:10]:
        sub_id, text, file_ids, status, created_at = row
        preview = (
            text[:30] + "...") if text and len(text) > 30 else (text or "(без текста)")
        # Добавляем индикатор ответа администратора
        response_indicator = " 💬" if status == "answered" else ""
        btn_text = f"{created_at[:16]}: {preview}{response_indicator}"
        buttons.append([InlineKeyboardButton(
            text=btn_text, callback_data=f"mymsg_{sub_id}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Ваша история обращений:", reply_markup=keyboard)


# Обработчик для просмотра конкретного обращения пользователя
@router.callback_query(F.data.startswith("mymsg_"))
async def show_user_submission_detail(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await submission_db.init()
    if not submission_db.connection:
        if callback.message:
            await callback.message.answer("Ошибка: соединение с базой не установлено.", reply_markup=get_main_keyboard(callback.from_user.id if callback.from_user else 0))
        await callback.answer()
        return
    if not callback.data:
        await callback.answer()
        return
    sub_id = int(callback.data.split("_")[1])
    # Получаем историю переписки
    history = await submission_db.get_conversation_history(sub_id)

    if not history:
        if callback.message:
            await callback.message.answer("Обращение не найдено", reply_markup=get_main_keyboard(callback.from_user.id if callback.from_user else 0))
        await callback.answer()
        return

        # Отправляем заголовок истории
    header_text = f"💬 История переписки #{sub_id}\n\n"
    await bot.send_message(callback.from_user.id, header_text, reply_markup=get_main_keyboard(callback.from_user.id if callback.from_user else 0))

    # Отправляем каждое сообщение отдельно с его файлами
    for i, (sender_role, text, file_ids, created_at) in enumerate(history, 1):
        sender_label = "👤 (Вы)" if sender_role == "user" else "👨‍💼 (Админ)"
        message_text = f"{sender_label} - {created_at[:16]}\n{text or '(нет текста)'}"

        # Если есть файлы, отправляем медиа-группу
        if file_ids and file_ids != '[]':
            try:
                import json
                files = json.loads(file_ids)
                if files:
                    # Отправляем медиа-группу с текстом
                    media_group = []
                    for j, file_id in enumerate(files[:5]):
                        if j == 0:  # Первый файл с текстом
                            media_group.append(InputMediaPhoto(
                                media=file_id,
                                caption=message_text
                            ))
                        else:  # Остальные файлы без текста
                            media_group.append(InputMediaPhoto(media=file_id))

                    await bot.send_media_group(callback.from_user.id, media_group)
                else:
                    # Если нет файлов, отправляем только текст
                    await bot.send_message(callback.from_user.id, message_text, reply_markup=get_main_keyboard(callback.from_user.id if callback.from_user else 0))
            except Exception as e:
                logger.error(f"Ошибка отправки медиа-группы: {e}")
                # Если не удалось отправить медиа-группу, отправляем текст
                await bot.send_message(callback.from_user.id, message_text, reply_markup=get_main_keyboard(callback.from_user.id if callback.from_user else 0))
        else:
            # Если нет файлов, отправляем только текст
            await bot.send_message(callback.from_user.id, message_text, reply_markup=get_main_keyboard(callback.from_user.id if callback.from_user else 0))

    # Отправляем кнопки действий в последнем сообщении
    actions_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💬 Ответить", callback_data=f"reply_user_{sub_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="myhistory_back")]
    ])

    await bot.send_message(
        callback.from_user.id,
        "🎯 Ваши действия:",
        reply_markup=actions_keyboard
    )

    await callback.answer()


# Обработчик для кнопки "Ответить" пользователя
@router.callback_query(F.data.startswith("reply_user_"))
async def handle_user_reply(callback: types.CallbackQuery, state: FSMContext):
    """Обработка ответа пользователя на свое обращение"""
    if not callback.data:
        await callback.answer()
        return

    sub_id = int(callback.data.split("_")[2])

    # Сохраняем ID обращения в состоянии
    await state.set_state(FeedbackStates.waiting_for_reply)
    await state.update_data(submission_id=sub_id)

    # Создаем клавиатуру с кнопками "Отправить" и "Отменить"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 Отправить")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )

    response = f"💬 Ответ на обращение #{sub_id}\n\n"
    response += "Отправьте ваше сообщение (текст + до 5 фото/файлов). Вы можете отправить несколько сообщений подряд, а затем нажать 'Отправить'."

    if callback.message:
        await callback.message.answer(response, reply_markup=keyboard)

    await callback.answer()


# Обработчик для ответа пользователя на свое обращение
@router.message(FeedbackStates.waiting_for_reply, F.photo | F.document | F.text)
async def handle_user_reply_content(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка ответа пользователя на свое обращение"""
    try:
        if not message.from_user:
            logger.error("❌ Не удалось определить пользователя")
            await message.answer("❌ Ошибка: не удалось определить пользователя", reply_markup=get_main_keyboard(message.from_user.id if message.from_user else 0))
            await state.clear()
            return

        user_id = message.from_user.id
        user_data = await state.get_data()
        submission_id = user_data.get('submission_id')

        if not submission_id:
            await message.answer("❌ Ошибка: ID обращения не найден", reply_markup=get_main_keyboard(user_id))
            await state.clear()
            return

        # Проверяем, не нажал ли пользователь кнопку "Отменить"
        if message.text == "❌ Отменить":
            await message.answer(
                "❌ Ответ отменен.",
                reply_markup=get_main_keyboard(user_id)
            )
            await state.clear()
            return

        # Проверяем, не нажал ли пользователь кнопку "Отправить"
        if message.text == "📤 Отправить":
            accumulated_text = user_data.get('accumulated_text', '') or ''
            accumulated_text = accumulated_text.strip()
            accumulated_files = user_data.get('accumulated_files', [])

            if not accumulated_text and not accumulated_files:
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

            try:
                await submission_db.init()

                # Получаем conversation_id из submissions
                submission = await submission_db.get_submission_by_id(submission_id)
                if not submission:
                    await message.answer("❌ Обращение не найдено", reply_markup=get_main_keyboard(user_id))
                    await state.clear()
                    return

                # conversation_id в новой структуре
                conversation_id = submission[6]

                # Добавляем сообщение пользователя в переписку
                await submission_db.add_message(
                    conversation_id=conversation_id,
                    sender_id=user_id,
                    receiver_id=0,  # 0 для администраторов
                    sender_role='user',
                    text=accumulated_text,
                    file_ids=accumulated_files[:5]
                )

                await message.answer(
                    "✅ Ваш ответ отправлен!",
                    reply_markup=get_main_keyboard(user_id)
                )
                await state.clear()
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения ответа в БД: {e}")
                await message.answer(
                    "❌ Ошибка при сохранении ответа. Попробуйте позже.",
                    reply_markup=get_main_keyboard(user_id)
                )
                await state.clear()
            return

        # Обработка контента (аналогично handle_feedback_content)
        accumulated_files = user_data.get('accumulated_files', [])
        accumulated_text = user_data.get('accumulated_text', '') or ''

        # Обработка медиа
        if message.photo:
            file_id = message.photo[-1].file_id
            accumulated_files.append(file_id)
        elif message.document:
            file_id = message.document.file_id
            accumulated_files.append(file_id)

        # Обработка текста (включая caption к медиа)
        text_to_add = None
        if message.text:
            text_to_add = message.text
        elif message.caption:
            text_to_add = message.caption

        if text_to_add:
            if accumulated_text:
                new_text = accumulated_text + "\n\n" + text_to_add
            else:
                new_text = text_to_add
            accumulated_text = new_text

        # Обновляем состояние
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

        await message.answer(status_message, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в handle_user_reply_content: {e}")
        try:
            user_id = message.from_user.id if message.from_user else 0
            await message.answer(
                "❌ Произошла ошибка при обработке сообщения. Попробуйте еще раз.",
                reply_markup=get_main_keyboard(user_id)
            )
            await state.clear()
        except Exception as cleanup_error:
            logger.error(f"❌ Ошибка при очистке состояния: {cleanup_error}")


# Обработчик для кнопки "Назад" в истории обращений


@router.callback_query(F.data == "myhistory_back")
async def back_to_user_history(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await submission_db.init()
    if not submission_db.connection:
        if callback.message:
            await callback.message.answer("Ошибка: соединение с базой не установлено.", reply_markup=get_main_keyboard(callback.from_user.id if callback.from_user else 0))
        await callback.answer()
        return
    user_id = callback.from_user.id if callback.from_user else None
    if not user_id:
        await callback.answer("Ошибка: не удалось определить пользователя.", reply_markup=get_main_keyboard(callback.from_user.id if callback.from_user else 0))
        return
    async with submission_db.connection.cursor() as cursor:
        await cursor.execute('SELECT id, text_content, file_ids, status, created_at FROM submissions WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = await cursor.fetchall()
    rows = list(rows) if rows else []
    if not rows:
        if callback.message:
            await callback.message.answer("У вас пока нет обращений.", reply_markup=get_main_keyboard(callback.from_user.id if callback.from_user else 0))
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
    if callback.message:
        await callback.message.answer("Ваша история обращений:", reply_markup=keyboard)
    await callback.answer()
