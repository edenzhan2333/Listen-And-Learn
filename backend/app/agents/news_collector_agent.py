"""News Collector Agent —— 新闻采集 Agent

访问 https://news.aibase.com/zh/news 定向采集 AI 领域新闻。
读取最新一天的所有新闻（按"X天前"标签判断日期），总结最重要的20条。
"""

import logging
import asyncio
import re
from typing import Optional
from datetime import datetime, timedelta
from app.harness.base_agent import BaseAgent
from app.harness.logger import AgentLogger
from app.tools.zhipu_client import ZhipuClient
from app.tools.image_downloader import download_image
from app.config import settings

logger = logging.getLogger(__name__)


class NewsCollectorAgent(BaseAgent):
    name = "news_collector_agent"

    def __init__(self, task_id: Optional[str] = None):
        super().__init__(task_id)
        self.zhipu = ZhipuClient()

    async def run(self, date_str: str = None, **kwargs) -> list[dict]:
        """采集 AI 领域新闻 —— 从 aibase.com 定向获取"""
        loop = asyncio.get_event_loop()

        logger.info(f"Starting news collection from {settings.NEWS_SOURCE_URL}")

        # Step 1: 抓取新闻列表页，获取最新一天的所有新闻链接
        news_links = await loop.run_in_executor(None, self._fetch_news_links)

        if not news_links:
            logger.error("No news links found from aibase.com")
            AgentLogger.log(
                self.name, "collect", {"source": settings.NEWS_SOURCE_URL},
                None, status="failed", error="no news links found",
                task_id=self.task_id
            )
            return []

        logger.info(f"Found {len(news_links)} news links for the latest day")

        # Step 2: 逐个抓取新闻正文
        all_news_raw = []
        batch_size = 5  # 每批5个并发抓取
        for i in range(0, len(news_links), batch_size):
            batch = news_links[i:i + batch_size]
            tasks = [loop.run_in_executor(None, self._fetch_article_detail, link) for link in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for link, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.warning(f"Failed to fetch {link['url']}: {result}")
                elif result:
                    all_news_raw.append(result)
            logger.info(f"Fetched {len(all_news_raw)}/{len(news_links)} articles")

        if not all_news_raw:
            logger.error("No article content fetched")
            return []

        # Step 3: 用 GLM 总结并选出最重要的20条
        top_news = await self._summarize_and_select(all_news_raw)

        # Step 4: 下载图片
        for item in top_news:
            if item.get("image_url"):
                img_dir = settings.NEWS_DIR / (date_str or datetime.now().strftime("%Y-%m-%d")) / "images"
                local_path = await loop.run_in_executor(
                    None, download_image, item["image_url"], img_dir
                )
                if local_path:
                    item["image_path"] = str(local_path)
            item["domain"] = "AI"

        logger.info(f"Total news collected: {len(top_news)}")
        AgentLogger.log(
            self.name, "collect",
            {"source": settings.NEWS_SOURCE_URL, "links_found": len(news_links)},
            {"collected": len(top_news)},
            tools_used=["fetch_page", "fetch_article", "summarize"],
            task_id=self.task_id
        )

        return top_news

    def _fetch_news_links(self) -> list[dict]:
        """抓取 aibase.com 新闻列表页，获取最新一天的所有新闻链接"""
        import httpx
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

        all_links = []
        latest_day_label = None  # 如 "4天前"

        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                # 抓取第1页
                resp = client.get(settings.NEWS_SOURCE_URL, headers=headers)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                # 查找所有新闻条目，识别"X天前"标签
                # aibase 的新闻列表通常有日期标签在标题左下角
                news_items = soup.find_all("a", href=re.compile(r"/zh/news/"))

                for item in news_items:
                    # 获取新闻标题和链接
                    title = item.get_text(strip=True)
                    href = item.get("href", "")
                    if not title or not href:
                        continue
                    url = urljoin("https://news.aibase.com", href)

                    # 查找日期标签（"X天前"、"X小时前"、"昨天"、"今天"等）
                    # 在新闻条目附近查找
                    parent = item.find_parent()
                    day_label = None
                    if parent:
                        # 查找包含"天前"、"小时前"等文本的元素
                        for sibling in parent.find_all(string=re.compile(r"\d+\s*(天|小时)前|昨天|今天|前天")):
                            day_label = sibling.strip()
                            break
                        if not day_label:
                            # 在父元素的文本中查找
                            parent_text = parent.get_text()
                            match = re.search(r'(\d+\s*天前|\d+\s*小时前|昨天|今天|前天)', parent_text)
                            if match:
                                day_label = match.group(1)

                    if day_label:
                        # 确定最新一天的标签
                        if latest_day_label is None:
                            latest_day_label = day_label
                            logger.info(f"Latest day label detected: {latest_day_label}")

                        # 如果遇到更早一天的新闻，停止收集
                        if self._is_earlier_day(day_label, latest_day_label):
                            logger.info(f"Reached earlier day ({day_label} < {latest_day_label}), stopping")
                            break

                        all_links.append({
                            "url": url,
                            "title": title,
                            "day_label": day_label,
                        })

                # 如果第1页没找够，翻页获取更多
                page = 2
                while len(all_links) < 50 and page <= 5:
                    try:
                        next_url = f"{settings.NEWS_SOURCE_URL}?page={page}"
                        resp2 = client.get(next_url, headers=headers)
                        if resp2.status_code != 200:
                            break
                        soup2 = BeautifulSoup(resp2.text, "lxml")
                        items2 = soup2.find_all("a", href=re.compile(r"/zh/news/"))

                        found_earlier = False
                        for item in items2:
                            title = item.get_text(strip=True)
                            href = item.get("href", "")
                            if not title or not href:
                                continue
                            url = urljoin("https://news.aibase.com", href)

                            parent = item.find_parent()
                            day_label = None
                            if parent:
                                for sibling in parent.find_all(string=re.compile(r"\d+\s*(天|小时)前|昨天|今天|前天")):
                                    day_label = sibling.strip()
                                    break
                                if not day_label:
                                    parent_text = parent.get_text()
                                    match = re.search(r'(\d+\s*天前|\d+\s*小时前|昨天|今天|前天)', parent_text)
                                    if match:
                                        day_label = match.group(1)

                            if day_label and self._is_earlier_day(day_label, latest_day_label):
                                found_earlier = True
                                break

                            if day_label and day_label == latest_day_label:
                                all_links.append({
                                    "url": url,
                                    "title": title,
                                    "day_label": day_label,
                                })

                        if found_earlier:
                            break
                        page += 1
                    except Exception as e:
                        logger.warning(f"Failed to fetch page {page}: {e}")
                        break

            logger.info(f"Found {len(all_links)} news links (latest day: {latest_day_label})")
            return all_links

        except Exception as e:
            logger.error(f"Failed to fetch news links: {e}")
            return []

    def _is_earlier_day(self, label: str, reference: str) -> bool:
        """判断 label 是否比 reference 更早"""
        def to_hours(l: str) -> int:
            l = l.strip()
            if "小时" in l:
                m = re.search(r'(\d+)', l)
                return int(m.group(1)) if m else 0
            elif "天前" in l:
                m = re.search(r'(\d+)', l)
                return int(m.group(1)) * 24 if m else 999
            elif l == "今天":
                return 0
            elif l == "昨天":
                return 24
            elif l == "前天":
                return 48
            return 999

        return to_hours(label) > to_hours(reference)

    def _fetch_article_detail(self, link: dict) -> dict:
        """抓取单篇新闻正文"""
        import httpx
        from bs4 import BeautifulSoup

        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.get(link["url"], headers=headers)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                # 提取标题
                title = link.get("title", "")
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)

                # 提取正文
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()

                content_area = (
                    soup.find("article")
                    or soup.find("main")
                    or soup.find(class_=re.compile(r"article|content|post|entry", re.I))
                    or soup.find("body")
                )
                content = content_area.get_text(separator="\n", strip=True) if content_area else ""
                if len(content) > 6000:
                    content = content[:6000]

                # 提取图片
                image_url = ""
                if content_area:
                    for img in content_area.find_all("img"):
                        src = img.get("src") or img.get("data-src")
                        if src:
                            image_url = src if src.startswith("http") else f"https://news.aibase.com{src}"
                            break

                return {
                    "url": link["url"],
                    "title": title,
                    "content": content,
                    "image_url": image_url,
                    "day_label": link.get("day_label", ""),
                }

        except Exception as e:
            logger.error(f"Failed to fetch article {link['url']}: {e}")
            return None

    async def _summarize_and_select(self, articles: list[dict]) -> list[dict]:
        """用 GLM 总结所有新闻正文，选出最重要的20条"""
        # 构建文章摘要文本
        articles_text = []
        for i, art in enumerate(articles, 1):
            articles_text.append(
                f"【新闻{i}】\n标题: {art['title']}\n正文: {art['content'][:800]}\n来源: {art['url']}\n"
            )

        # 分批处理（每批10篇，避免 prompt 过长）
        all_summaries = []
        batch_size = 10
        for i in range(0, len(articles_text), batch_size):
            batch = articles_text[i:i + batch_size]
            batch_text = "\n".join(batch)

            prompt = f"""请阅读以下{len(batch)}篇AI领域新闻，为每篇生成结构化摘要。

新闻内容:
{batch_text}

请为每篇新闻输出JSON数组，每个元素包含:
- title_zh: 中文标题
- title_en: 英文标题（如有英文原标题则保留，否则翻译）
- summary_zh: 中文摘要（200字以内，包含关键事实）
- source_url: 原文链接
- image_url: 图片URL（如有）
- importance: 重要性评分（1-10分，10分最重要）

只输出JSON数组，以 [ 开头，以 ] 结尾。"""

            try:
                response = self.zhipu.chat(
                    prompt,
                    system_prompt="你是AI领域新闻编辑，擅长提炼新闻要点。只输出JSON。",
                    temperature=0.3,
                    max_tokens=4096
                )
                items = self._parse_summaries(response)
                all_summaries.extend(items)
                logger.info(f"Batch {i//batch_size + 1}: summarized {len(items)} articles")
            except Exception as e:
                logger.error(f"Batch summarize failed: {e}")

        # 按重要性排序，选前20条
        all_summaries.sort(key=lambda x: x.get("importance", 5), reverse=True)
        top_news = all_summaries[:settings.NEWS_PER_DOMAIN]

        # 补全字段
        today_str = datetime.now().strftime("%Y-%m-%d")
        for item in top_news:
            item["domain"] = "AI"
            item["news_date"] = today_str
            item["date"] = today_str

        return top_news

    def _parse_summaries(self, response: str) -> list[dict]:
        """解析 GLM 返回的新闻摘要"""
        try:
            data = self.zhipu._extract_json(response)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "news" in data:
                return data["news"]
            return [data] if isinstance(data, dict) else []
        except Exception as e:
            logger.error(f"Failed to parse summaries: {e}")
            return []
