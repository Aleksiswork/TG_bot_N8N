import os
import aiosqlite
from datetime import datetime
from config import DB_NAME


class Database:
    def __init__(self):
        if not DB_NAME:
            raise ValueError('❌ Отсутствует DB_USERS_PATH в .env')
        self.db_name = DB_NAME
        db_dir = os.path.dirname(self.db_name)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TEXT,
                    last_active TEXT
                )
            ''')
            await db.commit()

    @staticmethod
    async def init_all():
        """Асинхронно инициализирует все необходимые БД и таблицы проекта."""
        db = Database()
        await db.init_db()
        from database.submissions import SubmissionDB
        submission_db = SubmissionDB()
        await submission_db.init()

    async def save_user(self, user):
        """Сохранение/обновление пользователя"""
        now = datetime.now().isoformat()
        # Гарантируем, что таблица users существует перед операцией
        await self.init_db()
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                "SELECT 1 FROM users WHERE user_id = ?",
                (user.id,)
            )
            exists = await cursor.fetchone()

            if exists:
                await db.execute(
                    "UPDATE users SET username=?, first_name=?, last_name=?, last_active=? WHERE user_id=?",
                    (user.username, user.first_name, user.last_name, now, user.id)
                )
            else:
                await db.execute(
                    "INSERT INTO users (user_id, username, first_name, last_name, created_at, last_active) VALUES (?, ?, ?, ?, ?, ?)",
                    (user.id, user.username, user.first_name,
                     user.last_name, now, now)
                )
            await db.commit()

    async def get_users_stats(self):
        """Получение статистики пользователей"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            result = await cursor.fetchone()
            total_users = result[0] if result is not None else 0

            cursor = await db.execute("""
                SELECT first_name, username, last_active 
                FROM users 
                ORDER BY last_active DESC 
                LIMIT 5
            """)
            recent_users = await cursor.fetchall()

        return total_users, recent_users

    async def get_all_users(self):
        """Получение всех пользователей"""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT * FROM users")
            return await cursor.fetchall()
