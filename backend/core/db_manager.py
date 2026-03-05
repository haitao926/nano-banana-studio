import sqlite3
import time
import os
import json
from typing import Optional, List, Dict, Tuple

class DBManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "data", "app.db")
        else:
            self.db_path = db_path
        
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_conn() as conn:
            # Users Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_pro BOOLEAN DEFAULT 0,
                    quota_limit INTEGER DEFAULT 10,
                    quota_used INTEGER DEFAULT 0,
                    created_at REAL,
                    last_quota_reset REAL
                )
            """)
            
            # Images Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    filename TEXT UNIQUE NOT NULL,
                    prompt TEXT,
                    subject TEXT,
                    grade TEXT,
                    featured BOOLEAN DEFAULT 0,
                    timestamp REAL,
                    metadata TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)

            # Audio History Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    filename TEXT,
                    url TEXT,
                    prompt TEXT,
                    voice TEXT,
                    model TEXT,
                    duration REAL,
                    mode TEXT,
                    created_at REAL,
                    metadata TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)

            # Video History Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    task_id TEXT UNIQUE,
                    image_url TEXT,
                    audio_url TEXT,
                    video_url TEXT,
                    prompt TEXT,
                    resolution INTEGER,
                    style TEXT,
                    duration REAL,
                    status TEXT,
                    created_at REAL,
                    metadata TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)

            # Assistant conversations/messages
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assistant_conversations (
                    conversation_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT,
                    model TEXT,
                    created_at REAL,
                    updated_at REAL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assistant_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at REAL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_assistant_conversations_user_updated "
                "ON assistant_conversations(user_id, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_assistant_messages_conversation_created "
                "ON assistant_messages(conversation_id, created_at ASC)"
            )

            # Rate Limit Log (Legacy support / IP tracking if needed, or purely for audit)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ip TEXT,
                    timestamp REAL
                )
            """)
            
            conn.commit()

    # --- User Management ---
    def create_user(self, username, password_hash, is_pro=False, quota_limit: Optional[int] = None):
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                limit = 20 # Default 20 points (Gemini=2pts, Others=1pt)
                if quota_limit is not None:
                    try:
                        limit = int(quota_limit)
                    except Exception:
                        limit = 20
                cursor.execute(
                    "INSERT INTO users (username, password_hash, is_pro, quota_limit, created_at, last_quota_reset) VALUES (?, ?, ?, ?, ?, ?)",
                    (username, password_hash, is_pro, limit, time.time(), time.time())
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def get_user_by_username(self, username) -> Optional[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_user_by_id(self, user_id) -> Optional[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_user_quota(self, user_id, increment=1):
        with self._get_conn() as conn:
            conn.execute("UPDATE users SET quota_used = quota_used + ? WHERE id = ?", (increment, user_id))
            conn.commit()

    def check_and_reset_quota(self, user_id):
        """Check if weekly reset is needed"""
        user = self.get_user_by_id(user_id)
        if not user: return
        
        last_reset = user['last_quota_reset'] or 0
        now = time.time()
        # 7 days = 604800 seconds
        if now - last_reset > 604800:
            with self._get_conn() as conn:
                conn.execute("UPDATE users SET quota_used = 0, last_quota_reset = ? WHERE id = ?", (now, user_id))
                conn.commit()

    def get_all_users(self):
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, is_pro, quota_limit, quota_used, created_at FROM users ORDER BY id DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_user_status(self, user_id, is_pro: bool, quota_limit: int):
        with self._get_conn() as conn:
            conn.execute("UPDATE users SET is_pro = ?, quota_limit = ? WHERE id = ?", (is_pro, quota_limit, user_id))
            conn.commit()

    def delete_user(self, user_id: int) -> bool:
        with self._get_conn() as conn:
            conn.execute("UPDATE images SET user_id = NULL WHERE user_id = ?", (user_id,))
            conn.execute("UPDATE audios SET user_id = NULL WHERE user_id = ?", (user_id,))
            conn.execute("UPDATE videos SET user_id = NULL WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM assistant_messages WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM assistant_conversations WHERE user_id = ?", (user_id,))
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    # --- Image Management ---
    def log_image(self, user_id, filename, prompt, subject, grade, metadata=None):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO images (user_id, filename, prompt, subject, grade, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, filename, prompt, subject, grade, time.time(), json.dumps(metadata or {}))
            )
            conn.commit()

    def log_audio(self, user_id, filename, url, prompt, voice, model, duration, mode="speech", metadata=None):
        created_at = time.time()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO audios (user_id, filename, url, prompt, voice, model, duration, mode, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, filename, url, prompt, voice, model, duration, mode, created_at, json.dumps(metadata or {}))
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "user_id": user_id,
                "filename": filename,
                "url": url,
                "prompt": prompt,
                "voice": voice,
                "model": model,
                "duration": duration,
                "mode": mode,
                "created_at": created_at
            }

    def get_audio_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM audios WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def create_video_task(self, user_id, task_id, image_url, audio_url, prompt, resolution, style, duration, status="pending", metadata=None):
        created_at = time.time()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO videos (user_id, task_id, image_url, audio_url, prompt, resolution, style, duration, status, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, task_id, image_url, audio_url, prompt, resolution, style, duration, status, created_at, json.dumps(metadata or {}))
            )
            conn.commit()
            return cursor.lastrowid

    def update_video_task(self, task_id: str, video_url: Optional[str] = None, status: Optional[str] = None):
        if not task_id:
            return
        updates = []
        params = []
        if video_url is not None:
            updates.append("video_url = ?")
            params.append(video_url)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if not updates:
            return
        params.append(task_id)
        with self._get_conn() as conn:
            conn.execute(f"UPDATE videos SET {', '.join(updates)} WHERE task_id = ?", params)
            conn.commit()

    def get_video_task(self, task_id: str) -> Optional[Dict]:
        if not task_id:
            return None
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE task_id = ? LIMIT 1", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_video_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM videos WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_gallery_images(self, user_id: Optional[int] = None, show_featured_only=False, show_all=False):
        """
        user_id: If provided, show this user's images.
        show_featured_only: If True, show only featured images.
        show_all: If True (Admin?), show everything.
        
        Logic for "User sees own history + Featured":
        Query: WHERE (user_id = ?) OR (featured = 1)
        """
        query = "SELECT * FROM images WHERE 1=1"
        params = []

        if show_all:
            pass # No filter
        else:
            filters = []
            if user_id is not None:
                filters.append("user_id = ?")
                params.append(user_id)
            
            # Always include featured images in the result if not specifically filtering for just "my" images strictly
            # But the requirement is "User sees own history + Featured".
            # So: (user_id = X) OR (featured = 1)
            
            if user_id is not None:
                query = "SELECT * FROM images WHERE user_id = ? OR featured = 1"
                # params is just [user_id]
                pass
            else:
                # If no user_id (not logged in? shouldn't happen per new requirement), show only featured
                query = "SELECT * FROM images WHERE featured = 1"
                params = []

        query += " ORDER BY timestamp DESC"
        
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def toggle_feature(self, filename, featured: bool):
        with self._get_conn() as conn:
            conn.execute("UPDATE images SET featured = ? WHERE filename = ?", (featured, filename))
            conn.commit()

    def get_image_metadata(self, filename):
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM images WHERE filename = ?", (filename,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    # --- Assistant Conversation Management ---
    def create_or_touch_assistant_conversation(
        self,
        user_id: int,
        conversation_id: str,
        model: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        now = time.time()
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT conversation_id, title, model FROM assistant_conversations "
                "WHERE conversation_id = ? AND user_id = ? LIMIT 1",
                (conversation_id, user_id),
            )
            row = cursor.fetchone()
            if row:
                updates = ["updated_at = ?"]
                params: List = [now]
                if model:
                    updates.append("model = ?")
                    params.append(model)
                if title and not row["title"]:
                    updates.append("title = ?")
                    params.append(title)
                params.extend([conversation_id, user_id])
                conn.execute(
                    f"UPDATE assistant_conversations SET {', '.join(updates)} "
                    "WHERE conversation_id = ? AND user_id = ?",
                    params,
                )
            else:
                conn.execute(
                    "INSERT INTO assistant_conversations "
                    "(conversation_id, user_id, title, model, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (conversation_id, user_id, title or "", model or "", now, now),
                )
            conn.commit()

    def list_assistant_conversations(self, user_id: int, limit: int = 50) -> List[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT conversation_id, user_id, title, model, created_at, updated_at "
                "FROM assistant_conversations "
                "WHERE user_id = ? "
                "ORDER BY updated_at DESC "
                "LIMIT ?",
                (user_id, limit),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_assistant_conversation(self, user_id: int, conversation_id: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT conversation_id, user_id, title, model, created_at, updated_at "
                "FROM assistant_conversations "
                "WHERE user_id = ? AND conversation_id = ? "
                "LIMIT 1",
                (user_id, conversation_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_assistant_message(
        self,
        user_id: int,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> int:
        created_at = time.time()
        metadata_text = json.dumps(metadata or {}, ensure_ascii=False)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO assistant_messages "
                "(conversation_id, user_id, role, content, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, user_id, role, content, metadata_text, created_at),
            )
            conn.execute(
                "UPDATE assistant_conversations SET updated_at = ? "
                "WHERE conversation_id = ? AND user_id = ?",
                (created_at, conversation_id, user_id),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def get_assistant_messages(self, user_id: int, conversation_id: str, limit: int = 50) -> List[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, conversation_id, user_id, role, content, metadata, created_at "
                "FROM assistant_messages "
                "WHERE user_id = ? AND conversation_id = ? "
                "ORDER BY created_at DESC "
                "LIMIT ?",
                (user_id, conversation_id, limit),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            rows.reverse()
            return rows

    def delete_assistant_conversation(self, user_id: int, conversation_id: str) -> bool:
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM assistant_messages WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            )
            cursor = conn.execute(
                "DELETE FROM assistant_conversations WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            )
            conn.commit()
            return cursor.rowcount > 0
