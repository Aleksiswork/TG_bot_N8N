"""
Telegram Bot v1.4
Обновления:
Надежный экспорт в CSV с правильным форматированием
Проверку размера файла
Инструкцию по открытию
Автоматическую очистку временных файлов

Функционал:
- Добавил 2 гайда (Установка N8N и Фаервол и ssh-keygen)
"""
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Проверка обязательных переменных
required_vars = {
    'BOT_TOKEN': os.getenv("BOT_TOKEN"),
    'ADMIN_ID': os.getenv("ADMIN_ID"),
    'CHANNEL_USERNAME': os.getenv("CHANNEL_USERNAME"),
    'CHANNEL_LINK': os.getenv("CHANNEL_LINK"),
    'FILES_DIR': os.getenv("FILES_DIR")
}

missing_vars = [name for name, value in required_vars.items() if not value]
if missing_vars:
    raise ValueError(
        f"Отсутствуют обязательные переменные в .env: {', '.join(missing_vars)}")

# Конфигурационные константы
BOT_VERSION = "1.4"
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
FILES_DIR = os.getenv("FILES_DIR").replace('\\', '/')  # Нормализация путей
DB_NAME = "bot_users.db"
