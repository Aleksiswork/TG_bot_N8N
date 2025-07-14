"""
Telegram Bot v3.0
Обновления:
- Улучшенная архитектура и типизация
- Расширенные настройки конфигурации
- Улучшенная валидация и обработка ошибок
- Поддержка множественных админов
- Настройки логирования
"""
import os
from dotenv import load_dotenv, find_dotenv
from typing import List, Optional
from pathlib import Path
from dataclasses import dataclass
import logging

# Загрузка .env файла
env_path = find_dotenv()
print(
    f"Используется .env: {env_path if env_path else 'Файл .env не найден!'}")
load_dotenv(env_path)

# Версия бота
BOT_VERSION = "3.1"

# Базовые пути
BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / '.env'


@dataclass
class BotConfig:
    """Конфигурация бота"""
    token: str
    admin_ids: List[int]
    db_users_path: str
    db_submissions_path: str
    version: str = BOT_VERSION
    channel_username: Optional[str] = None
    channel_id: Optional[str] = None
    channel_link: Optional[str] = None
    files_dir: str = "files"
    max_file_size_mb: int = 50
    max_files_per_submission: int = 5
    max_submission_length: int = 4000
    polling_timeout: int = 30
    max_retries: int = 5

    def __post_init__(self):
        if self.admin_ids is None:
            self.admin_ids = []
        # Нормализуем пути
        self.files_dir = self.files_dir.replace("\\", "/")
        if not self.db_submissions_path:
            self.db_submissions_path = str(
                BASE_DIR / 'data' / 'submissions.db')


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
                print(f"Некорректный ID администратора: {admin_id}")
        except ValueError as e:
            print(f"Ошибка парсинга ID: {admin_id}. {e}")
    return admin_ids


def setup_logging(level: str = "INFO") -> None:
    """Настройка логирования"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format=f'%(asctime)s - %(name)s - v{BOT_VERSION} - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(BASE_DIR / 'bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


# Загружаем конфигурацию
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = parse_admin_ids(os.getenv("ADMIN_IDS", ""))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # ID канала (альтернатива username)
CHANNEL_LINK = os.getenv("CHANNEL_LINK")
FILES_DIR = os.getenv("FILES_DIR", "files").replace("\\", "/")
DB_NAME = os.getenv('DB_USERS_PATH')
DB_SUBMISSIONS_PATH = os.getenv(
    "DB_SUBMISSIONS_PATH", str(BASE_DIR / 'data' / 'submissions.db'))

# Настройки логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
setup_logging(LOG_LEVEL)

# Создаем конфигурационный объект
config = BotConfig(
    token=BOT_TOKEN or "",
    admin_ids=ADMIN_IDS,
    channel_username=CHANNEL_USERNAME,
    channel_id=CHANNEL_ID,
    channel_link=CHANNEL_LINK,
    files_dir=FILES_DIR,
    db_users_path=DB_NAME or "",
    db_submissions_path=DB_SUBMISSIONS_PATH,
    max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
    max_files_per_submission=int(os.getenv("MAX_FILES_PER_SUBMISSION", "5")),
    max_submission_length=int(os.getenv("MAX_SUBMISSION_LENGTH", "4000"))
)

# Валидация конфигурации
if not config.token:
    raise ValueError("Отсутствует BOT_TOKEN в .env")

if not config.admin_ids:
    print("Внимание: не указаны ADMIN_IDS в .env")

if not config.channel_username or not config.channel_link:
    print("Внимание: канал не настроен (CHANNEL_USERNAME/CHANNEL_LINK)")

if not config.db_users_path:
    raise ValueError('Отсутствует DB_USERS_PATH в .env')

# Создаем папку для файлов если не существует
os.makedirs(config.files_dir, exist_ok=True)
os.makedirs(os.path.dirname(config.db_submissions_path), exist_ok=True)

print("Путь к submissions.db:", config.db_submissions_path)
