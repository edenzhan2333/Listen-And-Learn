"""知识库 API 路由"""

import re
import yaml
import asyncio
import markdown
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.models.schemas import KBSearchResponse, KBPageListResponse, KBPageDetail
from app.tools.wiki_manager import WikiManager
from app.database import get_db
from app.config import settings

router = APIRouter(prefix="/kb", tags=["knowledge_base"])

wiki = WikiManager()


class KBFeedbackRequest(BaseModel):
    page_path: str = ""
    type: str = "content"
    content: str


class SmartSearchRequest(BaseModel):
    query: str
    page_path: str = ""  # 可选，对特定搜索结果反馈


def _strip_frontmatter(content: str) -> str:
    """移除 YAML frontmatter"""
    match = re.match(r'^---\n.*?\n---\n?', content, re.DOTALL)
    if match:
        return content[match.end():]
    return content


def _parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter"""
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1)) or {}
        except Exception:
            return {}
    return {}


def _markdown_to_readable_text(md_content: str) -> str:
    """将 markdown 转为人类可读的纯文本格式"""
    # 先移除 frontmatter
    body = _strip_frontmatter(md_content)

    # 转为 HTML
    html = markdown.markdown(body, extensions=["extra", "tables"])

    # 将 HTML 标签转为可读格式
    # 标题
    html = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n━━━━━━━━━━━━━━━━\n\1\n━━━━━━━━━━━━━━━━\n', html, flags=re.DOTALL)
    html = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n■ \1\n', html, flags=re.DOTALL)
    html = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n▸ \1\n', html, flags=re.DOTALL)
    html = re.sub(r'<h4[^>]*>(.*?)</h4>', r'\n· \1\n', html, flags=re.DOTALL)

    # 列表
    html = re.sub(r'<li[^>]*>(.*?)</li>', r'  • \1\n', html, flags=re.DOTALL)
    html = re.sub(r'<ul[^>]*>', '', html)
    html = re.sub(r'</ul>', '', html)
    html = re.sub(r'<ol[^>]*>', '', html)
    html = re.sub(r'</ol>', '', html)

    # 段落和换行
    html = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html, flags=re.DOTALL)
    html = re.sub(r'<br\s*/?>', '\n', html)
    html = re.sub(r'<hr\s*/?>', '\n────────────────\n', html)

    # 加粗和斜体
    html = re.sub(r'<strong[^>]*>(.*?)</strong>', r'\1', html, flags=re.DOTALL)
    html = re.sub(r'<b[^>]*>(.*?)</b>', r'\1', html, flags=re.DOTALL)
    html = re.sub(r'<em[^>]*>(.*?)</em>', r'\1', html, flags=re.DOTALL)

    # 链接
    html = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'\2（\1）', html, flags=re.DOTALL)

    # 图片
    html = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*/?>', r'[图片: \1]', html)
    html = re.sub(r'<img[^>]*/?>', '[图片]', html)

    # 表格简化
    html = re.sub(r'<table[^>]*>', '\n', html)
    html = re.sub(r'</table>', '\n', html)
    html = re.sub(r'<tr[^>]*>(.*?)</tr>', r'\1\n', html, flags=re.DOTALL)
    html = re.sub(r'<t[dh][^>]*>(.*?)</t[dh]>', r'\1 | ', html, flags=re.DOTALL)

    # 代码块
    html = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', r'\n```\n\1\n```\n', html, flags=re.DOTALL)
    html = re.sub(r'<code[^>]*>(.*?)</code>', r'\1', html, flags=re.DOTALL)

    # 引用
    html = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', r'│ \1\n', html, flags=re.DOTALL)

    # 移除所有剩余标签
    html = re.sub(r'<[^>]+>', '', html)

    # 清理 HTML 实体
    html = html.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    html = html.replace('&quot;', '"').replace('&apos;', "'").replace('&nbsp;', ' ')

    # 清理多余空行
    html = re.sub(r'\n{3,}', '\n\n', html)
    html = html.strip()

    return html


@router.get("/search", response_model=KBSearchResponse)
async def search_kb(q: str = Query(..., min_length=1), limit: int = Query(20, le=50)):
    """搜索知识库（关键词搜索）"""
    results = wiki.search(q, limit=limit)
    # 清理 snippet 中的 HTML 标签
    for r in results:
        if r.get("snippet"):
            r["snippet"] = re.sub(r'<[^>]+>', '', r["snippet"])
    return KBSearchResponse(query=q, results=results)


@router.post("/smart-search")
async def smart_search(req: SmartSearchRequest):
    """智能搜索 —— 使用 GLM-5.2 理解查询意图，搜索并综合回答"""
    from app.agents.kb_search_agent import KBSearchAgent
    from app.harness.logger import AgentLogger

    agent = KBSearchAgent()
    result = await agent.run(query=req.query)

    return {
        "query": req.query,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "log_id": result.get("log_id"),
    }


@router.get("/domains")
async def get_domains():
    """获取领域列表"""
    return {"domains": settings.DOMAINS, "domain_keys": settings.DOMAIN_KEYS}


@router.get("/pages", response_model=KBPageListResponse)
async def list_pages(
    domain: str = Query(None),
    category: str = Query(None),
):
    """获取页面列表"""
    pages = wiki.list_pages(domain=domain, category=category)
    # 清理 summary 中的标签
    for p in pages:
        if p.get("summary"):
            p["summary"] = re.sub(r'<[^>]+>', '', p["summary"])[:150]
    return KBPageListResponse(domain=domain, pages=pages)


@router.get("/pages/{path:path}", response_model=KBPageDetail)
async def get_page(path: str):
    """获取页面内容（纯文本格式，适合人类阅读）"""
    content = wiki.read_page(path)
    if content is None:
        raise HTTPException(status_code=404, detail="Page not found")

    # 解析元数据
    meta = _parse_frontmatter(content)

    # 转为人类可读纯文本
    readable_content = _markdown_to_readable_text(content)

    return KBPageDetail(
        path=path,
        title=meta.get("title", path),
        content=readable_content,
        domain=meta.get("domain"),
        category=meta.get("category"),
    )


@router.get("/images/{filename:path}")
async def get_image(filename: str):
    """获取图片"""
    from fastapi.responses import FileResponse

    for base in [settings.KB_DIR / "assets", settings.NEWS_DIR]:
        img_path = base / filename
        if img_path.exists():
            return FileResponse(str(img_path))

    raise HTTPException(status_code=404, detail="Image not found")


@router.post("/update")
async def update_kb():
    """触发知识库更新任务"""
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO generation_jobs (type, status, progress, detail) "
            "VALUES ('kb_update', 'running', 0, '正在更新知识库...')"
        )
        job_id = cur.lastrowid

    async def _update():
        from app.harness.logger import AgentLogger
        wm = WikiManager()
        wm.ensure_structure()
        wm.update_index()
        AgentLogger.log(
            "knowledge_base_agent", "manual_update",
            {"job_id": job_id}, {"status": "success"},
            task_id=str(job_id)
        )
        with get_db() as conn:
            conn.execute(
                "UPDATE generation_jobs SET progress=100, status='success', "
                "detail='知识库更新完成', updated_at=datetime('now') WHERE id=?",
                (job_id,)
            )

    asyncio.create_task(_update())
    return {"job_id": job_id, "status": "running", "message": "知识库更新已启动"}


@router.post("/feedback")
async def submit_kb_feedback(req: KBFeedbackRequest):
    """提交知识库反馈 —— 触发 Feedback Optimizer Agent 优化"""
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO feedback (podcast_id, type, content) VALUES (NULL, ?, ?)",
            (f"kb_{req.type}", f"[{req.page_path}] {req.content}")
        )
        feedback_id = cur.lastrowid

    from app.agents.feedback_optimizer_agent import FeedbackOptimizerAgent
    agent = FeedbackOptimizerAgent()
    asyncio.create_task(agent.run(feedback_id=feedback_id))

    return {"id": feedback_id, "status": "pending", "message": "知识库反馈已提交，正在处理"}


@router.get("/feedback/list")
async def list_kb_feedback(limit: int = Query(20, le=100)):
    """获取知识库反馈列表"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback WHERE type LIKE 'kb_%' ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return {"feedbacks": [dict(r) for r in rows]}
