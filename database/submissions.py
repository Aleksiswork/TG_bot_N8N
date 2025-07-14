import aiosqlite
import json
import logging
from pathlib import Path
from typing import Optional, List
from config import DB_SUBMISSIONS_PATH
import asyncio

logger = logging.getLogger(__name__)


class SubmissionDB:
    _instance = None  # Классовый атрибут для Singleton

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.db_path: Path = Path(DB_SUBMISSIONS_PATH)
            self.connection: Optional[aiosqlite.Connection] = None
            self.ensure_db_directory()
            self.initialized = True

    def ensure_db_directory(self):
        """Создает папку для БД, если её нет"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self):
        """
        Инициализирует соединение с БД
        """
        if self.connection is None:  # Если соединение ещё не создано
            self.connection = await aiosqlite.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False
            )

            # Оптимизации для высокой нагрузки
            await self.connection.execute("PRAGMA journal_mode=WAL")
            await self.connection.execute("PRAGMA synchronous=NORMAL")
            await self.connection.execute("PRAGMA cache_size=10000")
            await self.connection.execute("PRAGMA temp_store=MEMORY")
            # 256MB
            await self.connection.execute("PRAGMA mmap_size=268435456")

            await self._create_tables()

    async def _create_tables(self):
        """Создает таблицу submissions с индексами"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                text_content TEXT,
                file_ids TEXT,
                status TEXT DEFAULT 'new',
                admin_response TEXT,
                processed_at TEXT,
                viewed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Создаем индексы для быстрого поиска
        await self.connection.execute('CREATE INDEX IF NOT EXISTS idx_submissions_user_id ON submissions(user_id)')
        await self.connection.execute('CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status)')
        await self.connection.execute('CREATE INDEX IF NOT EXISTS idx_submissions_created_at ON submissions(created_at)')
        await self.connection.execute('CREATE INDEX IF NOT EXISTS idx_submissions_username ON submissions(username)')

        await self.connection.commit()

    async def add_submission(self, user_id: int, username: str, text: str, file_ids: list[str]):
        """Добавляет заявку в БД"""
        if self.connection is None:
            logger.error("❌ Соединение с БД не инициализировано!")
            raise RuntimeError("Соединение с БД не инициализировано")

        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    '''INSERT INTO submissions 
                    (user_id, username, text_content, file_ids, status) 
                    VALUES (?, ?, ?, ?, 'new')''',
                    (user_id, username, text, json.dumps(file_ids))
                )
                await self.connection.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении записи: {e}")
            raise

    async def get_all_submissions(self, limit: int = 100, offset: int = 0):
        """Получает записи из БД с пагинацией"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    'SELECT * FROM submissions ORDER BY created_at DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                rows = await cursor.fetchall()
                return list(rows)
        except Exception as e:
            logger.error(f"❌ Ошибка при получении записей: {e}")
            raise

    async def get_submissions_by_status(self, status: str, limit: int = 100, offset: int = 0):
        """Получает записи по статусу с пагинацией"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    'SELECT * FROM submissions WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?',
                    (status, limit, offset)
                )
                rows = await cursor.fetchall()
                return list(rows)
        except Exception as e:
            logger.error(f"❌ Ошибка при получении записей по статусу: {e}")
            raise

    async def get_submission_by_id(self, submission_id: int):
        """Получает запись по ID"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    'SELECT * FROM submissions WHERE id = ?',
                    (submission_id,)
                )
                row = await cursor.fetchone()
                return row
        except Exception as e:
            logger.error(f"❌ Ошибка при получении записи по ID: {e}")
            raise

    async def mark_as_viewed(self, submission_id: int):
        """Отмечает запись как просмотренную"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    '''UPDATE submissions 
                    SET status = 'viewed', viewed_at = CURRENT_TIMESTAMP 
                    WHERE id = ? AND status = 'new' ''',
                    (submission_id,)
                )
                await self.connection.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка при отметке как просмотренной: {e}")
            raise

    async def mark_as_solved(self, submission_id: int):
        """Отмечает запись как решенную"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    '''UPDATE submissions 
                    SET status = 'solved', processed_at = CURRENT_TIMESTAMP 
                    WHERE id = ?''',
                    (submission_id,)
                )
                await self.connection.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка при отметке как решенной: {e}")
            raise

    async def delete_submission(self, submission_id: int):
        """Удаляет запись"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        logger.info(f"🗑️ Удаление записи {submission_id}...")
        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    'DELETE FROM submissions WHERE id = ?',
                    (submission_id,)
                )
                await self.connection.commit()
                logger.info(f"✅ Запись {submission_id} удалена")
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении записи: {e}")
            raise

    async def get_statistics(self):
        """Получает статистику по записям"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        logger.info("📊 Получение статистики...")
        try:
            async with self.connection.cursor() as cursor:
                # Общее количество
                await cursor.execute('SELECT COUNT(*) FROM submissions')
                total_row = await cursor.fetchone()
                total = total_row[0] if total_row else 0

                # Новые
                await cursor.execute("SELECT COUNT(*) FROM submissions WHERE status = 'new'")
                new_row = await cursor.fetchone()
                new_count = new_row[0] if new_row else 0

                # Решенные
                await cursor.execute("SELECT COUNT(*) FROM submissions WHERE status = 'solved'")
                solved_row = await cursor.fetchone()
                solved_count = solved_row[0] if solved_row else 0

                # Просмотренные
                await cursor.execute("SELECT COUNT(*) FROM submissions WHERE status = 'viewed'")
                viewed_row = await cursor.fetchone()
                viewed_count = viewed_row[0] if viewed_row else 0

                stats = {
                    'total': total,
                    'new': new_count,
                    'solved': solved_count,
                    'viewed': viewed_count
                }

                logger.info(f"📊 Статистика: {stats}")
                return stats
        except Exception as e:
            logger.error(f"❌ Ошибка при получении статистики: {e}")
            raise

    async def batch_update_status(self, submission_ids: List[int], status: str):
        """Пакетное обновление статуса записей"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        if not submission_ids:
            return

        try:
            async with self.connection.cursor() as cursor:
                placeholders = ','.join(['?' for _ in submission_ids])
                timestamp_field = 'viewed_at' if status == 'viewed' else 'processed_at'

                await cursor.execute(
                    f'''UPDATE submissions 
                    SET status = ?, {timestamp_field} = CURRENT_TIMESTAMP 
                    WHERE id IN ({placeholders})''',
                    [status] + submission_ids
                )
                await self.connection.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка при пакетном обновлении: {e}")
            raise

    async def close(self):
        """Закрывает соединение с БД"""
        if hasattr(self, 'connection') and self.connection:
            await self.connection.close()
            logger.info("🔌 Соединение с БД закрыто")

    async def __aenter__(self):
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
