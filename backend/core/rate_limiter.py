
import sqlite3
import time
import os
from typing import Tuple, Optional

class RateLimiter:
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "data", "rate_limit.db")
        else:
            self.db_path = db_path
        
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            # 创建索引加速查询
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ip_time ON usage_logs (ip, timestamp)")
            conn.commit()

    def check_limit(self, ip: str) -> Tuple[bool, str]:
        """
        检查是否允许生成
        Returns: (是否允许, 拒绝原因消息)
        """
        now = time.time()
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 1. 检查每分钟限制 (1张/分钟)
            # 查找该IP最近一次生成记录
            cursor.execute(
                "SELECT MAX(timestamp) FROM usage_logs WHERE ip = ?", 
                (ip,)
            )
            last_time = cursor.fetchone()[0]
            
            if last_time and (now - last_time < 60):
                remaining = int(60 - (now - last_time))
                return False, f"太频繁啦！灵感需要沉淀，请休息 {remaining} 秒后再试。\n趁这段时间好好构思一下更完美的提示词吧！"

            # 2. 检查每周限制 (20张/周)
            one_week_ago = now - (7 * 24 * 60 * 60)
            cursor.execute(
                "SELECT COUNT(*) FROM usage_logs WHERE ip = ? AND timestamp > ?", 
                (ip, one_week_ago)
            )
            count = cursor.fetchone()[0]
            
            if count >= 20:
                return False, f"本周额度已耗尽 ({count}/20)。\n好图不在多而在精，请下周再来创作，或者精简您的提示词策略！"

        return True, "Allowed"

    def record_usage(self, ip: str):
        """记录一次使用"""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO usage_logs (ip, timestamp) VALUES (?, ?)", 
                (ip, time.time())
            )
            conn.commit()

    def get_remaining_quota(self, ip: str) -> int:
        """查询本周剩余额度"""
        now = time.time()
        one_week_ago = now - (7 * 24 * 60 * 60)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM usage_logs WHERE ip = ? AND timestamp > ?", 
                (ip, one_week_ago)
            )
            count = cursor.fetchone()[0]
            return max(0, 20 - count)

    def get_all_stats(self) -> list:
        """获取所有IP的使用统计"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # 统计每个IP的总生成次数
            cursor.execute("""
                SELECT ip, COUNT(*) as total_count, MAX(timestamp) as last_active
                FROM usage_logs 
                GROUP BY ip 
                ORDER BY total_count DESC
            """)
            return [
                {"ip": row[0], "count": row[1], "last_active": row[2]} 
                for row in cursor.fetchall()
            ]
