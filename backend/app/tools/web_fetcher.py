"""网页抓取工具 —— 获取新闻正文和图片URL"""

import logging
import re
from urllib.parse import urljoin, urlparse
from typing import Optional, Tuple
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 常见新闻站点的 User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_article(url: str, timeout: int = 30) -> dict:
    """
    抓取新闻网页，提取正文和图片

    Returns:
        {"url": str, "title": str, "content": str, "images": list[str]}
    """
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, "lxml")

        # 提取标题
        title = ""
        if soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.find("title"):
            title = soup.find("title").get_text(strip=True)

        # 提取正文 —— 移除脚本、样式等
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # 尝试找到主要内容区域
        content_area = (
            soup.find("article")
            or soup.find("main")
            or soup.find(class_=re.compile(r"article|content|post|entry", re.I))
            or soup.find("body")
        )

        content = content_area.get_text(separator="\n", strip=True) if content_area else ""
        # 清理多余空行
        content = re.sub(r'\n{3,}', '\n\n', content)

        # 提取图片 URL
        images = []
        if content_area:
            for img in content_area.find_all("img"):
                src = img.get("src") or img.get("data-src")
                if src:
                    img_url = urljoin(url, src)
                    # 过滤掉小图标/表情等
                    width = img.get("width", "")
                    if width and int(width) < 100:
                        continue
                    images.append(img_url)

        # 限制正文长度
        if len(content) > 8000:
            content = content[:8000] + "..."

        logger.info(f"Fetched article: {url}, title={title[:50]}, "
                     f"content_len={len(content)}, images={len(images)}")

        return {
            "url": url,
            "title": title,
            "content": content,
            "images": images[:5],  # 最多5张图
        }

    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return {
            "url": url,
            "title": "",
            "content": "",
            "images": [],
            "error": str(e),
        }


def fetch_image_urls(query: str, count: int = 1) -> list[str]:
    """通过搜索获取图片 URL（简化实现，实际从新闻页面提取）"""
    # 在实际流程中，图片从新闻页面提取，此处保留接口
    return []
