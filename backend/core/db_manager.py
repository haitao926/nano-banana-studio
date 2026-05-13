import sqlite3
import time
import os
import json
from typing import Optional, List, Dict, Tuple


DB_INIT_RETRY_ATTEMPTS = 8
DB_INIT_RETRY_DELAY_SECONDS = 0.25

class DBManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "data", "app.db")
        else:
            self.db_path = db_path
        
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _is_retryable_lock_error(exc: sqlite3.OperationalError) -> bool:
        message = str(exc or "").strip().lower()
        return "database is locked" in message or "database table is locked" in message or "database schema is locked" in message

    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        for attempt in range(1, DB_INIT_RETRY_ATTEMPTS + 1):
            try:
                with self._get_conn() as conn:
                    conn.execute("PRAGMA journal_mode = WAL")
                    conn.execute("PRAGMA synchronous = NORMAL")
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

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS refresh_tokens (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            jti TEXT UNIQUE NOT NULL,
                            token_hash TEXT NOT NULL,
                            expires_at REAL NOT NULL,
                            created_at REAL,
                            revoked_at REAL,
                            replaced_by_jti TEXT,
                            user_agent TEXT,
                            ip TEXT,
                            FOREIGN KEY(user_id) REFERENCES users(id)
                        )
                    """)
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_active "
                        "ON refresh_tokens(user_id, revoked_at, expires_at)"
                    )

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS cli_device_tokens (
                            device_code TEXT PRIMARY KEY,
                            user_code TEXT UNIQUE NOT NULL,
                            user_id INTEGER,
                            status TEXT NOT NULL DEFAULT 'pending',
                            created_at REAL,
                            expires_at REAL NOT NULL,
                            approved_at REAL,
                            consumed_at REAL,
                            access_token TEXT,
                            refresh_token TEXT,
                            token_type TEXT,
                            base_url TEXT,
                            username TEXT,
                            user_agent TEXT,
                            ip TEXT,
                            FOREIGN KEY(user_id) REFERENCES users(id)
                        )
                    """)
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_cli_device_tokens_user_code "
                        "ON cli_device_tokens(user_code)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_cli_device_tokens_expires "
                        "ON cli_device_tokens(expires_at, status)"
                    )

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS key_rotation_state (
                            rotation_key TEXT PRIMARY KEY,
                            next_index INTEGER NOT NULL DEFAULT 0,
                            updated_at REAL
                        )
                    """)

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS model_candidate_health (
                            health_key TEXT PRIMARY KEY,
                            failures INTEGER NOT NULL DEFAULT 0,
                            cooldown_until REAL NOT NULL DEFAULT 0,
                            last_success_at REAL,
                            last_failure_at REAL,
                            last_error TEXT,
                            updated_at REAL
                        )
                    """)

                    conn.commit()
                    return
            except sqlite3.OperationalError as exc:
                if not self._is_retryable_lock_error(exc) or attempt >= DB_INIT_RETRY_ATTEMPTS:
                    raise
                time.sleep(DB_INIT_RETRY_DELAY_SECONDS * attempt)

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
            conn.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM assistant_messages WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM assistant_conversations WHERE user_id = ?", (user_id,))
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    def create_refresh_token(self, user_id: int, jti: str, token_hash: str, expires_at: float, user_agent: Optional[str] = None, ip: Optional[str] = None):
        created_at = time.time()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO refresh_tokens
                (user_id, jti, token_hash, expires_at, created_at, revoked_at, replaced_by_jti, user_agent, ip)
                VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (user_id, jti, token_hash, expires_at, created_at, user_agent, ip),
            )
            conn.commit()

    def get_refresh_token(self, jti: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM refresh_tokens WHERE jti = ? LIMIT 1", (jti,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def revoke_refresh_token(self, jti: str, replaced_by_jti: Optional[str] = None) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = ?, replaced_by_jti = COALESCE(?, replaced_by_jti)
                WHERE jti = ? AND revoked_at IS NULL
                """,
                (time.time(), replaced_by_jti, jti),
            )
            conn.commit()
            return cursor.rowcount > 0

    def create_cli_device_token(
        self,
        device_code: str,
        user_code: str,
        expires_at: float,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cli_device_tokens (
                    device_code, user_code, user_id, status, created_at, expires_at,
                    approved_at, consumed_at, access_token, refresh_token, token_type,
                    base_url, username, user_agent, ip
                )
                VALUES (?, ?, NULL, 'pending', ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
                """,
                (device_code, user_code, time.time(), expires_at, user_agent, ip),
            )
            conn.commit()

    def get_cli_device_token(self, device_code: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cli_device_tokens WHERE device_code = ? LIMIT 1", (device_code,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_cli_device_token_by_user_code(self, user_code: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cli_device_tokens WHERE user_code = ? LIMIT 1", (user_code,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def approve_cli_device_token(
        self,
        device_code: str,
        user_id: int,
        access_token: str,
        refresh_token: str,
        token_type: str,
        base_url: str,
        username: str,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                UPDATE cli_device_tokens
                SET user_id = ?, status = 'approved', approved_at = ?, access_token = ?, refresh_token = ?,
                    token_type = ?, base_url = ?, username = ?, user_agent = COALESCE(?, user_agent),
                    ip = COALESCE(?, ip)
                WHERE device_code = ? AND status = 'pending' AND expires_at > ?
                """,
                (
                    user_id,
                    time.time(),
                    access_token,
                    refresh_token,
                    token_type,
                    base_url,
                    username,
                    user_agent,
                    ip,
                    device_code,
                    time.time(),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def consume_cli_device_token(self, device_code: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cli_device_tokens WHERE device_code = ? LIMIT 1", (device_code,))
            row = cursor.fetchone()
            if not row:
                return None
            record = dict(row)
            if record.get("status") != "approved" or float(record.get("expires_at") or 0) <= time.time():
                return record
            conn.execute(
                "UPDATE cli_device_tokens SET status = 'consumed', consumed_at = ? WHERE device_code = ?",
                (time.time(), device_code),
            )
            conn.commit()
            record["status"] = "consumed"
            record["consumed_at"] = time.time()
            return record

    def purge_expired_cli_device_tokens(self) -> int:
        now = time.time()
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM cli_device_tokens WHERE expires_at <= ?", (now,))
            conn.commit()
            return cursor.rowcount

    def revoke_all_refresh_tokens_for_user(self, user_id: int) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (time.time(), user_id),
            )
            conn.commit()
            return cursor.rowcount

    def purge_expired_refresh_tokens(self) -> int:
        now = time.time()
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM refresh_tokens WHERE expires_at <= ?", (now,))
            conn.commit()
            return cursor.rowcount

    def get_and_advance_rotation_index(self, rotation_key: str, candidate_count: int) -> int:
        normalized_key = str(rotation_key or "").strip()
        size = max(1, int(candidate_count or 1))
        if size <= 1 or not normalized_key:
            return 0

        with self._get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT next_index FROM key_rotation_state WHERE rotation_key = ?",
                (normalized_key,),
            )
            row = cursor.fetchone()
            current = int(row[0]) if row else 0
            start = current % size
            next_index = (start + 1) % size
            now = time.time()
            if row:
                conn.execute(
                    "UPDATE key_rotation_state SET next_index = ?, updated_at = ? WHERE rotation_key = ?",
                    (next_index, now, normalized_key),
                )
            else:
                conn.execute(
                    "INSERT INTO key_rotation_state (rotation_key, next_index, updated_at) VALUES (?, ?, ?)",
                    (normalized_key, next_index, now),
                )
            conn.commit()
            return start

    def get_model_candidate_health(self, health_key: str) -> Dict:
        normalized_key = str(health_key or "").strip()
        if not normalized_key:
            return {}
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT failures, cooldown_until, last_success_at, last_failure_at, last_error "
                "FROM model_candidate_health WHERE health_key = ?",
                (normalized_key,),
            )
            row = cursor.fetchone()
        if not row:
            return {}
        return {
            "failures": int(row[0] or 0),
            "cooldown_until": float(row[1] or 0),
            "last_success_at": float(row[2] or 0),
            "last_failure_at": float(row[3] or 0),
            "last_error": row[4] or "",
        }

    def upsert_model_candidate_health(self, health_key: str, health: Dict) -> None:
        normalized_key = str(health_key or "").strip()
        if not normalized_key:
            return
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO model_candidate_health (
                    health_key, failures, cooldown_until, last_success_at,
                    last_failure_at, last_error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(health_key) DO UPDATE SET
                    failures = excluded.failures,
                    cooldown_until = excluded.cooldown_until,
                    last_success_at = excluded.last_success_at,
                    last_failure_at = excluded.last_failure_at,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_key,
                    int(health.get("failures") or 0),
                    float(health.get("cooldown_until") or 0),
                    float(health.get("last_success_at") or 0),
                    float(health.get("last_failure_at") or 0),
                    str(health.get("last_error") or ""),
                    now,
                ),
            )
            conn.commit()

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
