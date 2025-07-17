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
        """Создает таблицы для обратной связи и истории переписки"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        # Таблица submissions (обновленная структура)
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                text_content TEXT,
                file_ids TEXT,
                status TEXT DEFAULT 'new',
                conversation_id INTEGER,
                processed_at TEXT,
                viewed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Новая таблица для переписок (логическая цепочка сообщений)
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_message_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'open' -- open/closed/archived
            )
        ''')
        await self.connection.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)')
        await self.connection.execute('CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status)')

        # Новая таблица для сообщений в переписке
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                sender_role TEXT NOT NULL, -- 'user' или 'admin'
                text_content TEXT,
                file_ids TEXT, -- json array
                status TEXT DEFAULT 'new', -- new/read
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            )
        ''')
        await self.connection.execute('CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)')
        await self.connection.execute('CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status)')
        await self.connection.execute('CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id)')
        await self.connection.execute('CREATE INDEX IF NOT EXISTS idx_messages_receiver_id ON messages(receiver_id)')

        await self.connection.commit()

    async def add_submission(self, user_id: int, username: str, text: str, file_ids: Optional[List[str]] = None):
        """Добавляет заявку в БД и создает переписку"""
        if self.connection is None:
            logger.error("❌ Соединение с БД не инициализировано!")
            raise RuntimeError("Соединение с БД не инициализировано")
        if file_ids is None:
            file_ids = []
        try:
            async with self.connection.cursor() as cursor:
                # Создаем новую переписку
                await cursor.execute(
                    'INSERT INTO conversations (user_id) VALUES (?)',
                    (user_id,)
                )
                conversation_id = cursor.lastrowid

                # Добавляем запись в submissions
                await cursor.execute(
                    '''INSERT INTO submissions 
                    (user_id, username, text_content, file_ids, status, conversation_id) 
                    VALUES (?, ?, ?, ?, 'new', ?)''',
                    (user_id, username, text, json.dumps(file_ids), conversation_id)
                )
                submission_id = cursor.lastrowid

                # Добавляем первое сообщение пользователя в переписку
                await cursor.execute(
                    '''INSERT INTO messages (conversation_id, sender_id, receiver_id, sender_role, text_content, file_ids, status) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (conversation_id, user_id, 0, 'user',
                     text, json.dumps(file_ids), 'new')
                )

                await self.connection.commit()
                return submission_id
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

    async def save_admin_response(self, submission_id: int, admin_response: str, admin_id: int, file_ids: Optional[List[str]] = None):
        """Сохраняет ответ администратора в переписку (текст и файлы)"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")
        if file_ids is None:
            file_ids = []
        try:
            async with self.connection.cursor() as cursor:
                # Получаем conversation_id из submissions
                await cursor.execute(
                    'SELECT conversation_id, user_id FROM submissions WHERE id = ?',
                    (submission_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    raise RuntimeError(f"Обращение {submission_id} не найдено")

                conversation_id, user_id = row

                # Добавляем ответ администратора в переписку
                await cursor.execute(
                    '''INSERT INTO messages (conversation_id, sender_id, receiver_id, sender_role, text_content, file_ids, status) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (conversation_id, admin_id, user_id,
                     'admin', admin_response, json.dumps(file_ids), 'new')
                )

                # Обновляем время последнего сообщения в переписке
                await cursor.execute(
                    'UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (conversation_id,)
                )

                await self.connection.commit()
                logger.info(
                    f"✅ Ответ администратора сохранен в переписку {conversation_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении ответа администратора: {e}")
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

    async def get_last_submission_time(self, user_id: int) -> Optional[str]:
        """
        Возвращает дату и время последней отправки обращения пользователем (по created_at).
        """
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")
        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    'SELECT created_at FROM submissions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1',
                    (user_id,)
                )
                row = await cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(
                f"❌ Ошибка при получении времени последней отправки: {e}")
            return None

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

    # Методы для работы с новой структурой
    async def create_conversation(self, user_id: int) -> int:
        """Создать новую переписку и вернуть её id"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")
        async with self.connection.cursor() as cursor:
            await cursor.execute(
                'INSERT INTO conversations (user_id) VALUES (?)',
                (user_id,)
            )
            await self.connection.commit()
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("Не удалось получить id новой переписки")
            return lastrowid

    async def add_message(self, conversation_id: int, sender_id: int, receiver_id: int, sender_role: str, text: str = "", file_ids: Optional[List[str]] = None, status: str = 'new'):
        """Добавить сообщение в переписку"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")
        if file_ids is None:
            file_ids = []
        file_ids_json = json.dumps(file_ids)
        async with self.connection.cursor() as cursor:
            await cursor.execute(
                '''INSERT INTO messages (conversation_id, sender_id, receiver_id, sender_role, text_content, file_ids, status) \
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (conversation_id, sender_id, receiver_id,
                 sender_role, text, file_ids_json, status)
            )
            await self.connection.commit()
            # Обновляем last_message_at в conversations
            await cursor.execute(
                'UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?',
                (conversation_id,)
            )
            await self.connection.commit()
            return cursor.lastrowid

    async def get_conversation_by_id(self, conversation_id: int):
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")
        async with self.connection.cursor() as cursor:
            await cursor.execute('SELECT * FROM conversations WHERE id = ?', (conversation_id,))
            return await cursor.fetchone()

    async def get_user_conversations(self, user_id: int, limit: int = 20, offset: int = 0):
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")
        async with self.connection.cursor() as cursor:
            await cursor.execute('SELECT * FROM conversations WHERE user_id = ? ORDER BY last_message_at DESC LIMIT ? OFFSET ?', (user_id, limit, offset))
            return await cursor.fetchall()

    async def get_messages_in_conversation(self, conversation_id: int, limit: int = 50, offset: int = 0):
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")
        async with self.connection.cursor() as cursor:
            await cursor.execute('SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?', (conversation_id, limit, offset))
            return await cursor.fetchall()

    async def mark_message_as_read(self, message_id: int):
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")
        async with self.connection.cursor() as cursor:
            await cursor.execute('UPDATE messages SET status = "read" WHERE id = ?', (message_id,))
            await self.connection.commit()

    async def get_conversation_history(self, submission_id: int):
        """Получает историю переписки для обращения"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        try:
            async with self.connection.cursor() as cursor:
                # Получаем conversation_id из submissions
                await cursor.execute(
                    'SELECT conversation_id FROM submissions WHERE id = ?',
                    (submission_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    return []

                conversation_id = row[0]

                # Получаем все сообщения из переписки
                await cursor.execute(
                    '''SELECT sender_role, text_content, file_ids, created_at 
                    FROM messages 
                    WHERE conversation_id = ? 
                    ORDER BY created_at ASC''',
                    (conversation_id,)
                )
                messages = await cursor.fetchall()
                return list(messages)
        except Exception as e:
            logger.error(f"❌ Ошибка при получении истории переписки: {e}")
            return []

    async def backup_and_clear_database(self):
        """Создает резервную копию БД и очищает все сообщения"""
        if self.connection is None:
            raise RuntimeError("Соединение с БД не инициализировано")

        try:
            import shutil
            from datetime import datetime

            # Закрываем текущее соединение
            await self.connection.close()
            self.connection = None

            # Создаем имя файла резервной копии с текущей датой
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.db_path.parent / \
                f"submissions_backup_{timestamp}.db"

            # Копируем файл БД
            shutil.copy2(str(self.db_path), str(backup_path))
            logger.info(f"✅ Резервная копия создана: {backup_path}")

            # Пересоздаем соединение
            await self.init()
            if self.connection is None:
                self.connection = await aiosqlite.connect(
                    str(self.db_path),
                    timeout=30.0,
                    check_same_thread=False
                )
                await self._create_tables()

            # Очищаем все сообщения и переписки
            async with self.connection.cursor() as cursor:
                await cursor.execute('DELETE FROM messages')
                await cursor.execute('DELETE FROM conversations')
                await cursor.execute('DELETE FROM submissions')
                await self.connection.commit()

            logger.info("✅ Все сообщения и переписки очищены")
            return str(backup_path)

        except Exception as e:
            logger.error(f"❌ Ошибка при резервном копировании и очистке: {e}")
            raise
