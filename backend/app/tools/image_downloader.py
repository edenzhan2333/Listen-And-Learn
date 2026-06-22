"""图片下载工具 —— 下载新闻配图到本地"""

import logging
from pathlib import Path
from urllib.parse import urlparse
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def download_image(
    url: str,
    save_dir: Path,
    filename: str = None,
    timeout: int = 30,
) -> Path | None:
    """
    下载图片到本地

    Args:
        url: 图片 URL
        save_dir: 保存目录
        filename: 文件名（不含扩展名），None 则从 URL 推断

    Returns:
        保存的文件路径，失败返回 None
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            img_data = resp.content

        # 推断扩展名
        content_type = resp.headers.get("content-type", "")
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        elif "gif" in content_type:
            ext = ".gif"
        else:
            # 从 URL 推断
            parsed = urlparse(url)
            path = parsed.path
            if "." in path:
                ext = "." + path.rsplit(".", 1)[-1].lower()
                if len(ext) > 5:
                    ext = ".jpg"
            else:
                ext = ".jpg"

        if not filename:
            import hashlib
            filename = hashlib.md5(url.encode()).hexdigest()[:12]

        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{filename}{ext}"

        with open(save_path, "wb") as f:
            f.write(img_data)

        logger.info(f"Downloaded image: {url} -> {save_path} ({len(img_data)} bytes)")
        return save_path

    except Exception as e:
        logger.error(f"Failed to download image {url}: {e}")
        return None
