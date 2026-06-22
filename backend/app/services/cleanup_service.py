"""清理服务 —— 定时清理过期播客文件"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)


class CleanupService:
    """过期文件清理服务"""

    @staticmethod
    def cleanup_old_podcasts(days: int = None):
        """清理超过保留期的播客文件"""
        days = days or settings.MAX_PODCAST_DAYS
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        logger.info(f"Cleaning up podcasts older than {cutoff_date} ({days} days)")

        # 清理文件
        podcast_dir = settings.PODCAST_DIR
        if podcast_dir.exists():
            removed = 0
            for d in podcast_dir.iterdir():
                if d.is_dir() and d.name < cutoff_date:
                    # 删除目录
                    import shutil
                    shutil.rmtree(d, ignore_errors=True)
                    removed += 1
                    logger.info(f"Removed podcast directory: {d.name}")
            logger.info(f"Cleaned up {removed} old podcast directories")

        # 更新数据库记录（标记为已清理但保留记录）
        with get_db() as conn:
            conn.execute(
                """UPDATE podcasts SET
                   audio_zh_path=NULL, audio_en_path=NULL,
                   script_zh_path=NULL, script_en_path=NULL
                   WHERE date < ? AND status='ready'""",
                (cutoff_date,)
            )

    @staticmethod
    def cleanup_old_news(days: int = None):
        """清理过期新闻素材"""
        days = days or settings.MAX_PODCAST_DAYS
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        news_dir = settings.NEWS_DIR
        if news_dir.exists():
            removed = 0
            for d in news_dir.iterdir():
                if d.is_dir() and d.name < cutoff_date:
                    import shutil
                    shutil.rmtree(d, ignore_errors=True)
                    removed += 1
            if removed:
                logger.info(f"Cleaned up {removed} old news directories")

    @staticmethod
    def run_cleanup():
        """执行完整清理"""
        try:
            CleanupService.cleanup_old_podcasts()
            CleanupService.cleanup_old_news()
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
