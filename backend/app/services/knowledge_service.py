"""知识库服务 —— 业务逻辑层"""

import logging
from app.tools.wiki_manager import WikiManager
from app.config import settings

logger = logging.getLogger(__name__)


class KnowledgeService:
    """知识库业务服务"""

    def __init__(self):
        self.wiki = WikiManager()

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """搜索知识库"""
        return self.wiki.search(query, limit)

    def list_pages(self, domain: str = None, category: str = None) -> list[dict]:
        """列出页面"""
        return self.wiki.list_pages(domain=domain, category=category)

    def get_page(self, path: str) -> str | None:
        """获取页面内容"""
        return self.wiki.read_page(path)

    def get_domains(self) -> dict:
        """获取领域列表"""
        return {"domains": settings.DOMAINS, "domain_keys": settings.DOMAIN_KEYS}
