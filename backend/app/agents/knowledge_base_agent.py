"""Knowledge Base Agent —— 知识库 Agent

遵循 LLM Wiki 理念，将新闻素材增量整合到持久化知识库中。
"""

import logging
import asyncio
import re
from typing import Any, Optional
from datetime import datetime
from pathlib import Path
from app.harness.base_agent import BaseAgent
from app.harness.logger import AgentLogger, Timer
from app.tools.zhipu_client import ZhipuClient
from app.tools.wiki_manager import WikiManager
from app.config import settings

logger = logging.getLogger(__name__)


class KnowledgeBaseAgent(BaseAgent):
    name = "knowledge_base_agent"

    def __init__(self, task_id: Optional[str] = None):
        super().__init__(task_id)
        self.zhipu = ZhipuClient()
        self.wiki = WikiManager()
        self.wiki.ensure_structure()

    async def run(self, news_items: list[dict] = None, date_str: str = None, **kwargs) -> dict:
        """摄入新闻到知识库"""
        if not news_items:
            return {"status": "no_news"}

        loop = asyncio.get_event_loop()
        ingested = 0
        pages_updated = 0

        for item in news_items:
            try:
                result = await self._ingest_one(item, date_str)
                ingested += 1
                pages_updated += result.get("pages_touched", 0)
            except Exception as e:
                logger.error(f"Failed to ingest news item '{item.get('title_zh', '')}': {e}")

        # 更新索引
        await loop.run_in_executor(None, self.wiki.update_index)

        # 追加日志
        log_entry = f"## [{date_str}] ingest | {len(news_items)}条新闻 | 涉及{pages_updated}个页面\n"
        await loop.run_in_executor(None, self.wiki.append_log, log_entry)

        result = {
            "ingested": ingested,
            "pages_updated": pages_updated,
            "date": date_str,
        }
        AgentLogger.log(
            self.name, "ingest_batch",
            {"news_count": len(news_items), "date": date_str},
            result, tools_used=["write_page", "update_index", "append_log"],
            task_id=self.task_id
        )
        return result

    async def _ingest_one(self, item: dict, date_str: str) -> dict:
        """摄入单条新闻到知识库"""
        domain = item.get("domain", "unknown")
        domain_key = settings.DOMAIN_KEYS.get(domain, domain.lower().replace(" ", "-"))
        pages_touched = 0

        # 1. 写新闻摘要页
        source_slug = self._slugify(item.get("title_zh", "untitled"))[:60]
        source_path = f"domains/{domain_key}/sources/{date_str}-{source_slug}.md"
        source_content = self._generate_source_page(item, date_str, domain_key)
        await asyncio.get_event_loop().run_in_executor(
            None, self.wiki.write_page, source_path, source_content
        )
        pages_touched += 1

        # 2. 更新实体页（提取关键实体）
        entities = await self._extract_entities(item)
        for entity in entities:
            entity_slug = self._slugify(entity["name"])
            entity_path = f"domains/{domain_key}/entities/{entity_slug}.md"
            existing = self.wiki.read_page(entity_path)
            updated = self._update_entity_page(existing, entity, item, date_str)
            await asyncio.get_event_loop().run_in_executor(
                None, self.wiki.write_page, entity_path, updated
            )
            pages_touched += 1

        # 3. 更新领域概览页
        overview_path = f"domains/{domain_key}/overview.md"
        overview_existing = self.wiki.read_page(overview_path)
        overview_updated = self._update_overview_page(overview_existing, domain, item, date_str)
        await asyncio.get_event_loop().run_in_executor(
            None, self.wiki.write_page, overview_path, overview_updated
        )
        pages_touched += 1

        return {"pages_touched": pages_touched, "source_path": source_path}

    def _generate_source_page(self, item: dict, date_str: str, domain_key: str) -> str:
        """生成新闻摘要页内容"""
        title = item.get("title_zh", "未命名")
        title_en = item.get("title_en", "")
        summary = item.get("summary_zh", "")
        source_url = item.get("source_url", "")
        image_path = item.get("image_path", "")

        image_md = ""
        if image_path:
            # 转为相对路径
            try:
                rel_path = str(Path(image_path).relative_to(settings.DATA_DIR))
                image_md = f"\n![配图](/{rel_path})\n"
            except ValueError:
                pass

        return f"""---
title: "{title}"
domain: {domain_key}
category: source
date: {date_str}
source_url: {source_url}
tags: [{domain_key}, 新闻]
related: []
---

# {title}

{image_md}
## 摘要

{summary}

## 英文标题

{title_en}

## 原始来源

- [{source_url}]({source_url})

> 采集日期: {date_str}
"""

    async def _extract_entities(self, item: dict) -> list[dict]:
        """用 GLM-5.1 从新闻中提取关键实体"""
        prompt = f"""从以下新闻中提取关键实体（公司、产品、人物、技术名称等）。

新闻标题: {item.get('title_zh', '')}
新闻摘要: {item.get('summary_zh', '')}

请以 JSON 数组格式输出，每个元素:
{{"name": "实体名称", "type": "company/product/person/technology/other", "description": "简短描述"}}

最多提取5个实体。

重要：只输出 JSON 数组本身，不要输出任何其他文字、解释或 markdown 代码块标记。直接以 [ 开头，以 ] 结尾。如果新闻中没有可提取的实体，返回 []。"""

        try:
            result = self.zhipu.chat_json(
                prompt,
                system_prompt="你是一个实体识别助手。只输出纯 JSON，不输出任何其他内容。",
                temperature=0.2,
                max_tokens=1024
            )
            if isinstance(result, list):
                return result[:5]
            elif isinstance(result, dict) and "entities" in result:
                return result["entities"][:5]
            return []
        except Exception as e:
            logger.warning(f"Entity extraction failed for '{item.get('title_zh', '')[:30]}': {e}")
            return []

    def _update_entity_page(self, existing: str, entity: dict, news_item: dict, date_str: str) -> str:
        """更新或创建实体页"""
        name = entity["name"]
        entity_type = entity.get("type", "other")
        description = entity.get("description", "")
        domain = news_item.get("domain", "unknown")
        domain_key = settings.DOMAIN_KEYS.get(domain, "")

        if existing:
            # 追加更新记录
            update_section = f"\n### [{date_str}] 更新\n- 来源: [{news_item.get('title_zh', '')}]\n- {description}\n"
            return existing + update_section
        else:
            return f"""---
title: "{name}"
domain: {domain_key}
category: entity
entity_type: {entity_type}
tags: [{domain_key}, {entity_type}]
related: []
---

# {name}

## 简介

{description}

## 相关新闻

### [{date_str}]
- 来源: [{news_item.get('title_zh', '')}]
- {news_item.get('summary_zh', '')[:100]}
"""

    def _update_overview_page(self, existing: str, domain: str, item: dict, date_str: str) -> str:
        """更新领域概览页"""
        if existing:
            # 在最新新闻部分追加
            news_line = f"- **[{date_str}]** {item.get('title_zh', '')}\n"
            if "## 最新新闻" in existing:
                existing = existing.replace("## 最新新闻\n", f"## 最新新闻\n{news_line}", 1)
                # 保持最新新闻不超过20条
                lines = existing.split("\n")
                news_start = None
                news_count = 0
                for i, line in enumerate(lines):
                    if line.startswith("- **["):
                        if news_start is None:
                            news_start = i
                        news_count += 1
                if news_count > 20 and news_start is not None:
                    lines = lines[:news_start + 20] + lines[news_start + news_count:]
                    existing = "\n".join(lines)
                return existing
            else:
                return existing + f"\n## 最新新闻\n{news_line}\n"
        else:
            domain_key = settings.DOMAIN_KEYS.get(domain, "")
            return f"""---
title: "{domain}领域概览"
domain: {domain_key}
category: overview
tags: [{domain_key}, 概览]
---

# {domain}领域概览

本页面由 Agent 自动维护，记录{domain}领域的重要动态。

## 最新新闻

- **[{date_str}]** {item.get('title_zh', '')}

## 关键实体

> 见 entities/ 目录

## 关键概念

> 见 concepts/ 目录
"""

    @staticmethod
    def _slugify(text: str) -> str:
        """将文本转为文件名安全的 slug"""
        # 保留中文、英文、数字
        slug = re.sub(r'[^\w\u4e00-\u9fff\-]', '-', text.strip())
        slug = re.sub(r'-+', '-', slug).strip('-')
        return slug.lower() if slug else "untitled"
