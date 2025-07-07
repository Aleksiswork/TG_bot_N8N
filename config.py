"""
Telegram Bot v1.8
Обновления:
-Все распределнно по разным файлам
-Добавлены кнопка и обработка получения сообщения от пользователя
-Добавлена возможность сохранения нескольких ID для админов
"""
import os
from dotenv import load_dotenv, find_dotenv
from typing import List
from pathlib import Path
# from config import FILES_DIR, ADMIN_IDS
# Загрузка .env файла
# Версия бота задаётся статически, не из .env
BOT_VERSION = "1.9"

# Найти и залогировать путь к .env
env_path = find_dotenv()
print(
    f"🔧 Используется .env: {env_path if env_path else 'Файл .env не найден!'}")
load_dotenv(env_path)

# Логируем путь к .env и все переменные окружения
ENV_PATH = Path(__file__).parent / '.env'


BASE_DIR = Path(__file__).parent
DB_SUBMISSIONS_PATH = os.getenv(
    "DB_SUBMISSIONS_PATH", os.path.join(BASE_DIR, 'data', 'submissions.db'))
print("🔧 Путь к submissions.db:", DB_SUBMISSIONS_PATH)
print("🔧 ENV_PATH:", ENV_PATH)


def parse_admin_ids(env_str: str) -> List[int]:
    """Парсит строку с ID администраторов в список чисел"""
    admin_ids = []
    if not env_str:
        return admin_ids

    for admin_id in env_str.split(","):
        try:
            admin_id = admin_id.strip()
            if admin_id.isdigit():
                admin_ids.append(int(admin_id))
            else:
                print(f"⚠️ Некорректный ID администратора: {admin_id}")
        except ValueError as e:
            print(f"⛔ Ошибка парсинга ID: {admin_id}. {e}")
    return admin_ids


# Обязательные переменные
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = parse_admin_ids(os.getenv("ADMIN_IDS", ""))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")
FILES_DIR = os.getenv("FILES_DIR", "files").replace("\\", "/")
DB_NAME = r"d:/vps/Cursor/TG_bot_N8N/data/bot_users.db"

# Валидация конфигурации
if not BOT_TOKEN:
    raise ValueError("❌ Отсутствует BOT_TOKEN в .env")

if not ADMIN_IDS:
    print("⚠️ Внимание: не указаны ADMIN_IDS в .env")

if not CHANNEL_USERNAME or not CHANNEL_LINK:
    print("⚠️ Внимание: канал не настроен (CHANNEL_USERNAME/CHANNEL_LINK)")

# Создаем папку для файлов если не существует
os.makedirs(FILES_DIR, exist_ok=True)
