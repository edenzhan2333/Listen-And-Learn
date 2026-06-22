"""播客服务 —— 业务逻辑层"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)


class PodcastService:
    """播客业务服务"""

    @staticmethod
    def get_podcast_list(limit: int = 30) -> list[dict]:
        """获取播客列表"""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM podcasts ORDER BY date DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_podcast(podcast_id: int) -> dict | None:
        """获取播客详情"""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM podcasts WHERE id=?", (podcast_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            # 获取新闻
            news_rows = conn.execute(
                "SELECT * FROM news_items WHERE podcast_date=? ORDER BY domain",
                (d["date"],)
            ).fetchall()
            d["news_items"] = [dict(r) for r in news_rows]
            return d

    @staticmethod
    def save_news_items(news_items: list[dict], date_str: str):
        """保存新闻素材到数据库"""
        with get_db() as conn:
            for item in news_items:
                conn.execute(
                    """INSERT INTO news_items
                       (podcast_date, domain, title_zh, title_en, summary_zh, source_url, image_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        date_str,
                        item.get("domain", ""),
                        item.get("title_zh", ""),
                        item.get("title_en", ""),
                        item.get("summary_zh", ""),
                        item.get("source_url", ""),
                        item.get("image_path"),
                    )
                )

    @staticmethod
    def get_running_jobs() -> list[dict]:
        """获取正在运行的任务"""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM generation_jobs WHERE status='running' ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
