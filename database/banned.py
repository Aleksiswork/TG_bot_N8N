"""
БД для управления заблокированными пользователями
Система прогрессивных блокировок: 24ч -> 7 дней -> навсегда
"""
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class BannedDB:
    """База данных заблокированных пользователей"""

    def __init__(self, db_path: str = "data/banned.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Инициализация БД"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    banned_by INTEGER,
                    reason TEXT,
                    expires_at TIMESTAMP NULL,
                    is_permanent BOOLEAN DEFAULT FALSE,
                    ban_count INTEGER DEFAULT 1,
                    last_ban_reason TEXT
                )
            """)
            conn.commit()

    async def is_banned(self, user_id: int) -> bool:
        """Проверка, заблокирован ли пользователь"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT expires_at, is_permanent FROM banned_users WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()

                if not result:
                    return False

                expires_at, is_permanent = result

                # Если постоянная блокировка
                if is_permanent:
                    return True

                # Если временная блокировка истекла
                if expires_at:
                    expires = datetime.fromisoformat(expires_at)
                    if datetime.now() > expires:
                        # Удаляем истекшую блокировку
                        conn.execute(
                            "DELETE FROM banned_users WHERE user_id = ?", (user_id,))
                        conn.commit()
                        return False

                return True
        except Exception as e:
            logger.error(f"Ошибка проверки блокировки: {e}")
            return False

    async def get_ban_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации о блокировке"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT username, banned_at, banned_by, reason, expires_at, 
                           is_permanent, ban_count, last_ban_reason
                    FROM banned_users WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()

                if not result:
                    return None

                return {
                    'username': result[0],
                    'banned_at': result[1],
                    'banned_by': result[2],
                    'reason': result[3],
                    'expires_at': result[4],
                    'is_permanent': result[5],
                    'ban_count': result[6],
                    'last_ban_reason': result[7]
                }
        except Exception as e:
            logger.error(f"Ошибка получения информации о блокировке: {e}")
            return None

    async def ban_user(self, user_id: int, username: str, reason: str,
                       banned_by: int, duration_hours: int = 24) -> Dict[str, Any]:
        """Блокировка пользователя с прогрессивной системой"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Проверяем существующую блокировку
                cursor = conn.execute(
                    "SELECT ban_count FROM banned_users WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()

                ban_count = 1
                is_permanent = False
                expires_at = None

                if result:
                    ban_count = result[0] + 1

                    # Прогрессивная система блокировок
                    if ban_count == 2:  # Вторая блокировка - 7 дней
                        duration_hours = 24 * 7
                    elif ban_count >= 3:  # Третья и далее - навсегда
                        is_permanent = True

                # Вычисляем время истечения
                if not is_permanent:
                    expires_at = (datetime.now() +
                                  timedelta(hours=duration_hours)).isoformat()

                # Обновляем или вставляем запись
                conn.execute("""
                    INSERT OR REPLACE INTO banned_users 
                    (user_id, username, banned_at, banned_by, reason, expires_at, 
                     is_permanent, ban_count, last_ban_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, username, datetime.now().isoformat(), banned_by,
                      reason, expires_at, is_permanent, ban_count, reason))

                conn.commit()

                return {
                    'ban_count': ban_count,
                    'is_permanent': is_permanent,
                    'expires_at': expires_at,
                    'duration_hours': duration_hours
                }

        except Exception as e:
            logger.error(f"Ошибка блокировки пользователя: {e}")
            raise

    async def unban_user(self, user_id: int) -> bool:
        """Разблокировка пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM banned_users WHERE user_id = ?", (user_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка разблокировки пользователя: {e}")
            return False

    async def get_banned_list(self) -> List[Dict[str, Any]]:
        """Получение списка всех заблокированных пользователей"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT user_id, username, banned_at, reason, expires_at, 
                           is_permanent, ban_count
                    FROM banned_users 
                    ORDER BY banned_at DESC
                """)

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'user_id': row[0],
                        'username': row[1],
                        'banned_at': row[2],
                        'reason': row[3],
                        'expires_at': row[4],
                        'is_permanent': row[5],
                        'ban_count': row[6]
                    })

                return results
        except Exception as e:
            logger.error(f"Ошибка получения списка заблокированных: {e}")
            return []

    async def cleanup_expired_bans(self) -> int:
        """Очистка истекших блокировок"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM banned_users 
                    WHERE expires_at IS NOT NULL 
                    AND expires_at < ? 
                    AND is_permanent = FALSE
                """, (datetime.now().isoformat(),))

                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
        except Exception as e:
            logger.error(f"Ошибка очистки истекших блокировок: {e}")
            return 0

    async def get_ban_stats(self) -> Dict[str, Any]:
        """Статистика блокировок"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Общее количество заблокированных
                total = conn.execute(
                    "SELECT COUNT(*) FROM banned_users").fetchone()[0]

                # Постоянные блокировки
                permanent = conn.execute(
                    "SELECT COUNT(*) FROM banned_users WHERE is_permanent = TRUE"
                ).fetchone()[0]

                # Временные блокировки
                temporary = conn.execute(
                    "SELECT COUNT(*) FROM banned_users WHERE is_permanent = FALSE"
                ).fetchone()[0]

                # Заблокированные сегодня
                today = datetime.now().date().isoformat()
                today_bans = conn.execute(
                    "SELECT COUNT(*) FROM banned_users WHERE DATE(banned_at) = ?",
                    (today,)
                ).fetchone()[0]

                return {
                    'total': total,
                    'permanent': permanent,
                    'temporary': temporary,
                    'today': today_bans
                }
        except Exception as e:
            logger.error(f"Ошибка получения статистики блокировок: {e}")
            return {'total': 0, 'permanent': 0, 'temporary': 0, 'today': 0}

    async def close(self):
        """Закрытие соединения с БД"""
        pass  # SQLite автоматически закрывает соединения
