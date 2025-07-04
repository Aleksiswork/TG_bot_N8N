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
# import os
# from dotenv import load_dotenv

# # Загрузка переменных окружения
# load_dotenv()

# # Проверка обязательных переменных
# required_vars = {
#     'BOT_TOKEN': os.getenv("BOT_TOKEN"),
#     'ADMIN_ID': os.getenv("ADMIN_ID"),
#     'CHANNEL_USERNAME': os.getenv("CHANNEL_USERNAME"),
#     'CHANNEL_LINK': os.getenv("CHANNEL_LINK"),
#     'FILES_DIR': os.getenv("FILES_DIR")
# }

# missing_vars = [name for name, value in required_vars.items() if not value]
# if missing_vars:
#     raise ValueError(
#         f"Отсутствуют обязательные переменные в .env: {', '.join(missing_vars)}")

# # Конфигурационные константы
# BOT_VERSION = "1.4"
# CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
# CHANNEL_LINK = os.getenv("CHANNEL_LINK")
# BOT_TOKEN = os.getenv("BOT_TOKEN")
# ADMIN_ID = int(os.getenv("ADMIN_ID"))
# FILES_DIR = os.getenv("FILES_DIR").replace('\\', '/')  # Нормализация путей
# DB_NAME = "bot_users.db"

import os
from dotenv import load_dotenv
from typing import List

# Загрузка .env файла
load_dotenv()


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
BOT_VERSION = "1.4"
DB_NAME = "bot_users.db"

# Валидация конфигурации
if not BOT_TOKEN:
    raise ValueError("❌ Отсутствует BOT_TOKEN в .env")

if not ADMIN_IDS:
    print("⚠️ Внимание: не указаны ADMIN_IDS в .env")

if not CHANNEL_USERNAME or not CHANNEL_LINK:
    print("⚠️ Внимание: канал не настроен (CHANNEL_USERNAME/CHANNEL_LINK)")

# Создаем папку для файлов если не существует
os.makedirs(FILES_DIR, exist_ok=True)

# Пример использования (для тестирования)
if __name__ == "__main__":
    print("\n🔧 Конфигурация бота:")
    print(f"BOT_TOKEN: {'установлен' if BOT_TOKEN else 'отсутствует'}")
    print(f"ADMIN_IDS: {ADMIN_IDS}")
    print(f"CHANNEL: @{CHANNEL_USERNAME}")
    print(f"FILES_DIR: {FILES_DIR}")
    print(f"DB_NAME: {DB_NAME}")
    print(f"VERSION: {BOT_VERSION}\n")
