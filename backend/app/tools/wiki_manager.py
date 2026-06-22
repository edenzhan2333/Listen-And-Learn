"""Wiki 文件管理器 —— 维护 LLM Wiki 的文件结构和索引"""

import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
import yaml
from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)


class WikiManager:
    """LLM Wiki 文件管理器"""

    def __init__(self):
        self.base_dir = settings.KB_DIR
        self.domains = settings.DOMAIN_KEYS

    def ensure_structure(self):
        """确保 Wiki 目录结构存在"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for domain_key in self.domains.values():
            for sub in ["entities", "concepts", "sources"]:
                (self.base_dir / "domains" / domain_key / sub).mkdir(parents=True, exist_ok=True)
        (self.base_dir / "cross-domain").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "assets").mkdir(parents=True, exist_ok=True)

        schema_path = self.base_dir / "SCHEMA.md"
        if not schema_path.exists():
            schema_path.write_text(_SCHEMA_TEMPLATE, encoding="utf-8")

        index_path = self.base_dir / "index.md"
        if not index_path.exists():
            index_path.write_text("# 知识库索引\n\n> 由 Agent 自动维护\n", encoding="utf-8")

        log_path = self.base_dir / "log.md"
        if not log_path.exists():
            log_path.write_text("# 操作日志\n\n", encoding="utf-8")

    def read_page(self, relative_path: str) -> Optional[str]:
        full_path = self.base_dir / relative_path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        return None

    def write_page(self, relative_path: str, content: str):
        full_path = self.base_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        logger.info(f"Wiki page written: {relative_path}")
        self._update_db_index(relative_path, content)

    def _update_db_index(self, relative_path: str, content: str):
        meta = self._parse_frontmatter(content)
        body = self._strip_frontmatter(content)
        with get_db() as conn:
            conn.execute(
                """INSERT INTO knowledge_pages (path, title, domain, category, summary, tags, content, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(path) DO UPDATE SET
                       title=excluded.title, domain=excluded.domain,
                       category=excluded.category, summary=excluded.summary,
                       tags=excluded.tags, content=excluded.content,
                       updated_at=datetime('now')""",
                (
                    relative_path,
                    meta.get("title", ""),
                    meta.get("domain", ""),
                    meta.get("category", ""),
                    meta.get("summary", body[:200] if body else ""),
                    str(meta.get("tags", [])),
                    body,
                )
            )

    def append_log(self, entry: str):
        log_path = self.base_dir / "log.md"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")

    def update_index(self):
        lines = ["# 知识库索引\n\n> 由 Agent 自动维护\n"]
        for domain_name, domain_key in self.domains.items():
            lines.append(f"\n## {domain_name}\n")
            domain_dir = self.base_dir / "domains" / domain_key
            overview = domain_dir / "overview.md"
            if overview.exists():
                lines.append(f"- [[{domain_key}/overview|概览]] - {domain_name}领域总览\n")
            for sub in ["entities", "concepts", "sources"]:
                sub_dir = domain_dir / sub
                if sub_dir.exists():
                    for p in sorted(sub_dir.glob("*.md"), reverse=(sub == "sources")):
                        title = self._get_title(p.read_text(encoding="utf-8"))
                        lines.append(f"- [[{domain_key}/{sub}/{p.stem}|{title}]]\n")
        cross_dir = self.base_dir / "cross-domain"
        if cross_dir.exists():
            lines.append("\n## 跨领域\n")
            for p in sorted(cross_dir.glob("*.md")):
                title = self._get_title(p.read_text(encoding="utf-8"))
                lines.append(f"- [[cross-domain/{p.stem}|{title}]]\n")
        (self.base_dir / "index.md").write_text("".join(lines), encoding="utf-8")
        logger.info("Wiki index.md rebuilt")

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """将用户输入转为安全的 FTS5 查询字符串。

        FTS5 MATCH 对双引号、*、AND/OR/NOT/NEAR、:、() 等特殊字符敏感，
        直接传用户输入会触发 SQL 语法错误。这里按空格分词后用双引号包裹
        每个词作为短语，转义内部双引号，保证字面量匹配。
        """
        if not query or not query.strip():
            return ""
        # 转义双引号（FTS5 短语内双引号用 "" 转义）
        query = query.replace('"', '""')
        # 按空白分词，每个词用双引号包裹（短语搜索），空格连接（FTS5 默认 AND）
        tokens = [t for t in query.split() if t]
        if not tokens:
            return ""
        return " ".join(f'"{t}"' for t in tokens)

    def search(self, query: str, limit: int = 20) -> list[dict]:
        fts_query = self._sanitize_fts_query(query)
        if not fts_query:
            return []
        with get_db() as conn:
            rows = conn.execute(
                """SELECT knowledge_pages.path AS path,
                          knowledge_pages.title AS title,
                          knowledge_pages.domain AS domain,
                          knowledge_pages.category AS category,
                          knowledge_pages.summary AS summary,
                          snippet(knowledge_pages_fts, 2, '<b>', '</b>', '...', 30) AS snippet
                   FROM knowledge_pages_fts
                   JOIN knowledge_pages ON knowledge_pages_fts.rowid = knowledge_pages.id
                   WHERE knowledge_pages_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (fts_query, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def list_pages(self, domain: Optional[str] = None, category: Optional[str] = None) -> list[dict]:
        query = "SELECT path, title, domain, category, summary, updated_at FROM knowledge_pages WHERE 1=1"
        params = []
        if domain:
            query += " AND domain=?"
            params.append(domain)
        if category:
            query += " AND category=?"
            params.append(category)
        query += " ORDER BY updated_at DESC"
        with get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def _parse_frontmatter(content: str) -> dict:
        match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if match:
            try:
                return yaml.safe_load(match.group(1)) or {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        match = re.match(r'^---\n.*?\n---\n?', content, re.DOTALL)
        if match:
            return content[match.end():]
        return content

    @staticmethod
    def _get_title(content: str) -> str:
        meta = WikiManager._parse_frontmatter(content)
        if meta.get("title"):
            return meta["title"]
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        return match.group(1) if match else "未命名"


_SCHEMA_TEMPLATE = """# Listen and Learn 知识库规范

## 结构
- `domains/{领域}/overview.md` — 领域概览
- `domains/{领域}/entities/` — 实体页（公司、产品、人物、技术）
- `domains/{领域}/concepts/` — 概念页
- `domains/{领域}/sources/` — 新闻摘要页
- `cross-domain/` — 跨领域综合页
- `assets/` — 图片资源
- `index.md` — 内容目录
- `log.md` — 操作日志

## 页面格式
每个页面包含 YAML frontmatter + markdown 正文。

## 操作
- Ingest: 摄入新新闻，更新相关页面
- Query: 搜索和查询知识库
- Lint: 定期健康检查

## 维护原则
- 所有内容使用中文
- 维护交叉引用 [[页面名]]
- 矛盾信息标注，不直接删除旧信息
- Agent 负责所有维护工作
"""
