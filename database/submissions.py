import aiosqlite
import json
from pathlib import Path
from config import DB_SUBMISSIONS_PATH


class SubmissionDB:
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.db_path = Path("submissions.db")  # Или явный путь
            cls._instance.ensure_db_directory()
        return cls._instance

    def ensure_db_directory(self):
        """Создает папку для БД, если её нет"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self):
        """Инициализация соединения с БД"""
        self.connection = await aiosqlite.connect(str(self.db_path))  # Преобразуем Path в строку
        await self._create_tables()

    async def _create_tables(self):
        """Создает таблицу submissions"""
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                text_content TEXT,
                file_ids TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await self.connection.commit()

    async def add_submission(self, user_id: int, username: str, text: str, file_ids: list[str]):
        """Добавляет заявку в БД"""
        async with self.connection.cursor() as cursor:
            await cursor.execute(
                '''INSERT INTO submissions 
                (user_id, username, text_content, file_ids) 
                VALUES (?, ?, ?, ?)''',
                (user_id, username, text, json.dumps(file_ids))
            )
            await self.connection.commit()

    async def close(self):
        """Закрывает соединение с БД"""
        if hasattr(self, 'connection'):
            await self.connection.close()

    async def __aenter__(self):
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


# import aiosqlite
# from datetime import datetime
# # Добавьте в config.py: DB_SUBMISSIONS_PATH = "submissions.db"
# from config import DB_SUBMISSIONS_PATH


# class SubmissionDB:
#     async def init(self):
#         async with aiosqlite.connect(DB_SUBMISSIONS_PATH) as db:
#             await db.execute('''
#                 CREATE TABLE IF NOT EXISTS submissions (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     user_id INTEGER NOT NULL,
#                     username TEXT,
#                     text_content TEXT,
#                     file_ids TEXT,  # JSON-список file_id
#                     created_at TEXT DEFAULT (datetime('now'))
#                 )
#             ''')
#             await db.commit()

#     async def add_submission(self, user_id: int, username: str, text: str, file_ids: list[str]):
#         async with aiosqlite.connect(DB_SUBMISSIONS_PATH) as db:
#             await db.execute(
#                 '''INSERT INTO submissions
#                 (user_id, username, text_content, file_ids)
#                 VALUES (?, ?, ?, json(?))''',
#                 (user_id, username, text, file_ids)
#             )
#             await db.commit()
# import aiosqlite
# import json
# from pathlib import Path
# from config import DB_SUBMISSIONS_PATH


# class SubmissionDB:
#     _instance = None  # Singleton pattern

#     def __new__(cls):
#         if cls._instance is None:
#             cls._instance = super().__new__(cls)
#             cls._instance.db_path = Path(DB_SUBMISSIONS_PATH)
#             cls._instance.ensure_db_directory()
#         return cls._instance

#     def ensure_db_directory(self):
#         """Создает директорию для БД"""
#         self.db_path.parent.mkdir(parents=True, exist_ok=True)

#     async def init(self):
#         """Инициализация БД (вызывается 1 раз при старте)"""
#         self.connection = await aiosqlite.connect(self.db_path)
#         await self._create_tables()

#     async def _create_tables(self):
#         """Создание таблиц"""
#         await self.connection.execute('''
#             CREATE TABLE IF NOT EXISTS submissions (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 user_id INTEGER NOT NULL,
#                 username TEXT,
#                 text_content TEXT,
#                 file_ids TEXT,
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         ''')
#         await self.connection.commit()
# class SubmissionDB:
#     _instance = None

#     def __new__(cls):
#         if cls._instance is None:
#             cls._instance = super().__new__(cls)
#             cls._instance.db_path = Path(
#                 DB_SUBMISSIONS_PATH)  # <- Проблема здесь!
#             cls._instance.ensure_db_directory()
#         return cls._instance

#     async def init(self):
#         """Явная инициализация соединения с БД"""
#         self.connection = await aiosqlite.connect(self.db_path)
#         await self._create_tables()  # Создает таблицу, если ее нет

#     async def _create_tables(self):
#         """Создание таблицы (если не существует)"""
#         await self.connection.execute('''
#             CREATE TABLE IF NOT EXISTS submissions (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 user_id INTEGER NOT NULL,
#                 username TEXT,
#                 text_content TEXT,
#                 file_ids TEXT,
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         ''')
#         await self.connection.commit()

#     async def add_submission(self, user_id: int, username: str, text: str, file_ids: list[str]):
#         """Добавление заявки"""
#         async with self.connection.cursor() as cursor:
#             await cursor.execute(
#                 '''INSERT INTO submissions
#                 (user_id, username, text_content, file_ids)
#                 VALUES (?, ?, ?, ?)''',
#                 (user_id, username, text, json.dumps(file_ids))
#             )
#             await self.connection.commit()

#     async def close(self):
#         """Закрытие соединения"""
#         if hasattr(self, 'connection'):
#             await self.connection.close()

#     async def __aenter__(self):
#         await self.init()
#         return self

#     async def __aexit__(self, exc_type, exc, tb):
#         await self.close()
