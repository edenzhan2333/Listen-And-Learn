"""KB Search Agent —— 知识库智能搜索 Agent

使用 GLM-5.2 理解用户查询意图，搜索知识库，综合回答并引用来源。
支持反馈优化和质量评测。
"""

import re
import logging
from typing import Optional
from app.harness.base_agent import BaseAgent
from app.harness.logger import AgentLogger, Timer
from app.tools.zhipu_client import ZhipuClient
from app.tools.wiki_manager import WikiManager

logger = logging.getLogger(__name__)


class KBSearchAgent(BaseAgent):
    name = "kb_search_agent"

    def __init__(self, task_id: Optional[str] = None):
        super().__init__(task_id)
        self.zhipu = ZhipuClient()
        self.wiki = WikiManager()

    async def run(self, query: str = "", **kwargs) -> dict:
        """智能搜索知识库"""
        timer = Timer()
        timer.__enter__()

        try:
            search_keywords = self._generate_search_keywords(query)
            logger.info(f"[KBSearch] query='{query}', keywords={search_keywords}")

            all_results = []
            for kw in search_keywords:
                results = self.wiki.search(kw, limit=10)
                all_results.extend(results)

            seen_paths = set()
            unique_results = []
            for r in all_results:
                path = r.get("path", "")
                if path not in seen_paths:
                    seen_paths.add(path)
                    unique_results.append(r)

            logger.info(f"[KBSearch] found {len(unique_results)} unique results")

            if not unique_results:
                timer.__exit__()
                answer = "未在知识库中找到相关内容。请尝试其他关键词，或先生成播客以丰富知识库。"
                result = {"answer": answer, "sources": [], "log_id": None}
                log_id = AgentLogger.log(
                    self.name, "smart_search",
                    {"query": query}, result,
                    tools_used=["wiki_search", "zhipu_chat"],
                    duration_ms=timer.elapsed_ms,
                    task_id=self.task_id
                )
                result["log_id"] = log_id
                return result

            page_contents = []
            for r in unique_results[:5]:
                path = r.get("path", "")
                if path:
                    content = self.wiki.read_page(path)
                    if content:
                        body = re.sub(r'^---\n.*?\n---\n?', '', content, flags=re.DOTALL)
                        page_contents.append({
                            "path": path,
                            "title": r.get("title", path),
                            "content": body[:1500]
                        })

            answer = self._generate_answer(query, page_contents)
            timer.__exit__()

            sources = [{"path": p["path"], "title": p["title"]} for p in page_contents]
            result = {"answer": answer, "sources": sources}

            log_id = AgentLogger.log(
                self.name, "smart_search",
                {"query": query, "results_count": len(unique_results)},
                result,
                tools_used=["wiki_search", "zhipu_chat"],
                duration_ms=timer.elapsed_ms,
                task_id=self.task_id
            )
            result["log_id"] = log_id
            return result

        except Exception as e:
            timer.__exit__()
            logger.error(f"[KBSearch] failed: {e}")
            AgentLogger.log(
                self.name, "smart_search",
                {"query": query}, None,
                status="failed", error=str(e),
                duration_ms=timer.elapsed_ms,
                task_id=self.task_id
            )
            return {"answer": f"搜索失败: {e}", "sources": [], "log_id": None}

    def _generate_search_keywords(self, query: str) -> list[str]:
        """用 GLM 生成搜索关键词
        
        think 模式开启后思考过程会占用 token，max_tokens 必须足够大。
        同时对空响应做兜底：拆分查询中的实体词。
        """
        prompt = f"""用户想搜索AI领域知识库，查询内容是："{query}"

请生成3个简短的全文搜索关键词（中英文均可），用于在知识库中匹配相关页面。
要求：
- 每个关键词2-6个字，是具体的实体名或术语（如"智谱"、"GLM"、"OpenAI"）
- 不要输出整句话作为关键词
- 第一个关键词必须是查询中的核心实体

直接输出3个关键词，每行一个，不要编号，不要解释，不要思考过程。"""

        try:
            response = self.zhipu.chat(prompt, temperature=0.3, max_tokens=2048)
            keywords = [k.strip() for k in response.strip().split('\n') if k.strip()][:3]
            
            # 过滤掉过长的"关键词"（超过15字的不是关键词，是句子）
            keywords = [k for k in keywords if len(k) <= 15]
            
            if not keywords:
                # GLM 返回空（think 模式思考过长未输出）→ 本地拆分兜底
                logger.warning(f"GLM returned empty keywords, using local fallback for: {query}")
                keywords = self._extract_keywords_locally(query)
            
            # 始终包含原始查询的核心词
            if query not in keywords:
                keywords.insert(0, query)
            return keywords[:4]
        except Exception as e:
            logger.warning(f"Keyword generation failed: {e}")
            return [query]

    @staticmethod
    def _extract_keywords_locally(query: str) -> list[str]:
        """本地关键词提取兜底：从查询中提取2-4字的中文词或英文单词"""
        # 提取英文单词（2字符以上）
        en_words = re.findall(r'[A-Za-z]{2,}', query)
        # 提取中文词组（2-6字连续中文）
        zh_words = re.findall(r'[\u4e00-\u9fff]{2,6}', query)
        keywords = []
        # 优先中文词（取前2个），再英文词（取前2个）
        keywords.extend(zh_words[:2])
        keywords.extend(en_words[:2])
        # 去重
        seen = set()
        result = []
        for k in keywords:
            if k not in seen and k.lower() not in seen:
                seen.add(k)
                seen.add(k.lower())
                result.append(k)
        return result[:3] if result else [query]

    def _generate_answer(self, query: str, pages: list[dict]) -> str:
        """用 GLM 综合页面内容生成回答"""
        context = ""
        for i, p in enumerate(pages, 1):
            context += f"\n【来源{i}: {p['title']}】\n{p['content']}\n"

        prompt = f"""用户问题: {query}

以下是从知识库中检索到的相关内容:

{context}

请基于以上知识库内容，回答用户的问题。要求:
1. 回答要准确、清晰、有条理
2. 综合多个来源的信息
3. 如果信息不足以完整回答，请说明
4. 在回答末尾标注信息来源（如"来源: 来源1、来源2"）
5. 用中文回答，适合人类阅读

直接输出回答内容，不要其他说明。"""

        try:
            response = self.zhipu.chat(
                prompt,
                system_prompt="你是AI领域知识库助手，擅长综合多源信息回答问题。",
                temperature=0.5,
                max_tokens=4096
            )
            if not response or not response.strip():
                # think 模式思考过长导致 content 为空 → 返回来源摘要
                logger.warning("Answer generation returned empty, returning source summary")
                sources_summary = "\n\n".join(
                    f"【{p['title']}】\n{p['content'][:300]}..." for p in pages
                )
                return f"无法生成综合回答，以下是与"{query}"相关的知识库内容：\n\n{sources_summary}"
            return response.strip()
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"回答生成失败: {e}"
