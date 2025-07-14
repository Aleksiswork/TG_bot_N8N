"""
Общие обработчики команд
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from database import Database
from keyboards import (
    get_main_keyboard,
    get_guides_keyboard,
    get_feedback_keyboard,
    get_subscribe_keyboard
)
from utils.checks import check_subscription, is_admin, get_user_info
from config import config, BOT_VERSION

router = Router()
logger = logging.getLogger(__name__)

# Инициализация базы данных
try:
    db = Database()
except Exception as e:
    db = None
    logger.error(f"Ошибка инициализации Database: {e}")


@router.message(Command("start"))
async def start_command(message: Message, bot: Bot):
    """Обработчик команды /start"""
    if not message.from_user:
        return

    user_info = get_user_info(message.from_user)

    # Сохраняем пользователя в БД
    if db:
        try:
            await db.save_user(message.from_user)  # type: ignore
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователя: {e}")

    # Приветствие (без обязательной подписки)
    if config.channel_username:
        is_subscribed = await check_subscription(user_info['id'], bot)
        if not is_subscribed:
            await message.answer(
                "👋 Добро пожаловать! Подпишитесь на наш канал для получения обновлений и доступ ко всей информации:",
                reply_markup=get_subscribe_keyboard()
            )
            # Продолжаем работу бота даже без подписки

    # Приветственное сообщение
    welcome_text = f"""
🎉 Добро пожаловать в бот v{BOT_VERSION}!

📚 Здесь вы найдете полезные гайды и материалы.
📨 Обратная связь - вопросы, предложения и заказы на разработку.

Выберите нужный раздел:
"""

    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(user_info['id'])
    )


@router.message(Command("help"))
async def help_command(message: Message):
    """Обработчик команды /help"""
    help_text = f"""
🤖 Помощь по боту v{BOT_VERSION}

📚 **Гайды** - полезные материалы и инструкции
📨 **Обратная связь** - вопросы, предложения и заказы на разработку
ℹ️ **О боте** - информация о боте

💡 **Полезные команды:**
/start - Главное меню
/help - Эта справка
/guides - Гайды
/feedback - Обратная связь
/status - Статус бота

🔧 **Для администраторов:**
/admin - Админ панель
/stats - Статистика
"""

    await message.answer(help_text)


@router.message(Command("status"))
async def status_command(message: Message):
    """Обработчик команды /status"""
    if not message.from_user:
        return

    user_info = get_user_info(message.from_user)

    status_text = f"""
📊 Статус бота v{BOT_VERSION}

👤 **Ваш профиль:**
ID: {user_info['id']}
Username: @{user_info['username']}
Имя: {user_info['first_name']} {user_info['last_name']}
Роль: {'Администратор' if user_info['is_admin'] else 'Пользователь'}

🔧 **Настройки:**
Макс. размер файла: {config.max_file_size_mb}MB
Макс. файлов на сообщение: {config.max_files_per_submission}
Макс. длина текста: {config.max_submission_length} символов

📁 Папка файлов: {config.files_dir}
"""

    await message.answer(status_text)


@router.message(Command("guides"))
async def guides_command(message: Message):
    """Обработчик команды /guides"""
    await message.answer(
        "📚 Выберите нужный гайд:",
        reply_markup=get_guides_keyboard()
    )


@router.message(Command("feedback"))
async def feedback_command(message: Message):
    """Обработчик команды /feedback"""
    await message.answer(
        "📨 Отправьте ваше сообщение:\n\n"
        "• Вопросы по гайдам\n"
        "• Предложения по улучшению\n"
        "• Заказы на разработку автоматизации\n\n"
        "Можете добавить текст + до 5 фото/файлов. Отправьте несколько сообщений подряд, затем нажмите 'Отправить':",
        reply_markup=get_feedback_keyboard()
    )


@router.message(Command("admin"))
async def admin_command(message: Message):
    """Обработчик команды /admin"""
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ панели")
        return

    from keyboards import get_admin_keyboard
    await message.answer("⚙️ Админ-панель:", reply_markup=get_admin_keyboard())


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot):
    """Проверка подписки на канал"""
    if not callback.from_user:
        await callback.answer("Ошибка: не удалось определить пользователя")
        return

    is_subscribed = await check_subscription(callback.from_user.id, bot)

    if is_subscribed:
        if callback.message:
            await callback.message.edit_text(  # type: ignore
                "✅ Спасибо за подписку! Теперь вы можете использовать бота.",
                reply_markup=None
            )
            await callback.message.answer(  # type: ignore
                "🎉 Добро пожаловать! Выберите нужный раздел:",
                reply_markup=get_main_keyboard(callback.from_user.id)
            )
    else:
        await callback.answer(
            "❌ Вы не подписаны на канал. Пожалуйста, подпишитесь и попробуйте снова.",
            show_alert=True
        )


@router.message(F.text == "📚 Гайды")
async def guides_handler(message: Message):
    """Обработчик кнопки 'Гайды'"""
    await guides_command(message)


@router.message(F.text == "ℹ️ О боте")
async def about_bot_handler(message: Message):
    """Обработчик кнопки 'О боте'"""
    about_text = f"""
🤖 **О боте v{BOT_VERSION}**

Этот бот создан для распространения полезных материалов и гайдов по автоматизации.

📚 **Возможности:**
• Просмотр гайдов и инструкций
• Вопросы и предложения
• Заказы на разработку автоматизации
• Загрузка файлов и документов

🔧 **Техническая информация:**
• Версия: {BOT_VERSION}
• Макс. размер файла: {config.max_file_size_mb}MB
• Макс. файлов: {config.max_files_per_submission}
• Макс. текст: {config.max_submission_length} символов

📞 **Связь:**
Для вопросов, предложений и заказов используйте раздел "📨 Обратная связь".

Спасибо за использование нашего бота! 🙏
"""

    await message.answer(about_text)


@router.message(F.text == "⬅️ Назад")
async def back_handler(message: Message):
    """Обработчик кнопки 'Назад'"""
    if not message.from_user:
        return

    await message.answer(
        "🏠 Главное меню:",
        reply_markup=get_main_keyboard(message.from_user.id)
    )
