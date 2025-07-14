import os
import aiosqlite
from datetime import datetime
from config import DB_NAME
import asyncio
from typing import Optional


class Database:
    def __init__(self):
        if not DB_NAME:
            raise ValueError('❌ Отсутствует DB_USERS_PATH в .env')
        self.db_name = DB_NAME
        db_dir = os.path.dirname(self.db_name)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        # Пул соединений для высокой нагрузки
        self._connection_pool = []
        self._max_connections = 10
        self._lock = asyncio.Lock()

    async def _get_connection(self):
        """Получает соединение из пула или создает новое"""
        async with self._lock:
            if self._connection_pool:
                return self._connection_pool.pop()

            # Создаем новое соединение с оптимизациями
            conn = await aiosqlite.connect(
                self.db_name,
                timeout=30.0,  # Увеличиваем timeout
                check_same_thread=False
            )

            # Включаем WAL режим для лучшей производительности
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA cache_size=10000")
            await conn.execute("PRAGMA temp_store=MEMORY")
            await conn.execute("PRAGMA mmap_size=268435456")  # 256MB
            await conn.execute("PRAGMA optimize")

            return conn

    async def _return_connection(self, conn):
        """Возвращает соединение в пул"""
        async with self._lock:
            if len(self._connection_pool) < self._max_connections:
                self._connection_pool.append(conn)
            else:
                await conn.close()

    async def init_db(self):
        """Инициализация базы данных"""
        conn = await self._get_connection()
        try:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TEXT,
                    last_active TEXT
                )
            ''')

            # Создаем индексы для быстрого поиска
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active)')

            await conn.commit()
        finally:
            await self._return_connection(conn)

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
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT 1 FROM users WHERE user_id = ?",
                (user.id,)
            )
            exists = await cursor.fetchone()

            if exists:
                await conn.execute(
                    "UPDATE users SET username=?, first_name=?, last_name=?, last_active=? WHERE user_id=?",
                    (user.username, user.first_name, user.last_name, now, user.id)
                )
            else:
                await conn.execute(
                    "INSERT INTO users (user_id, username, first_name, last_name, created_at, last_active) VALUES (?, ?, ?, ?, ?, ?)",
                    (user.id, user.username, user.first_name,
                     user.last_name, now, now)
                )
            await conn.commit()
        finally:
            await self._return_connection(conn)

    async def get_users_stats(self):
        """Получение статистики пользователей"""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute("SELECT COUNT(*) FROM users")
            result = await cursor.fetchone()
            total_users = result[0] if result is not None else 0

            cursor = await conn.execute("""
                SELECT first_name, username, last_active 
                FROM users 
                ORDER BY last_active DESC 
                LIMIT 5
            """)
            recent_users = await cursor.fetchall()

            return total_users, recent_users
        finally:
            await self._return_connection(conn)

    async def get_all_users(self):
        """Получение всех пользователей"""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute("SELECT * FROM users")
            return await cursor.fetchall()
        finally:
            await self._return_connection(conn)

    async def close_all_connections(self):
        """Закрывает все соединения в пуле"""
        async with self._lock:
            for conn in self._connection_pool:
                await conn.close()
            self._connection_pool.clear()
