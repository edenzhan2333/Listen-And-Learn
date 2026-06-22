"""Orchestrator Agent —— 编排 Agent

接收用户意图，拆解任务，分配给子 Agent，监控执行，汇总结果。
"""

import logging
import asyncio
from typing import Any, Optional
from datetime import datetime
from app.harness.base_agent import BaseAgent
from app.harness.logger import AgentLogger, Timer
from app.tools.zhipu_client import ZhipuClient
from app.database import get_db

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    name = "orchestrator_agent"

    def __init__(self, task_id: Optional[str] = None):
        super().__init__(task_id)
        self.zhipu = ZhipuClient()

    async def run_podcast_pipeline(self, date_str: str) -> dict:
        """
        执行完整播客生成流水线:
        1. 新闻采集 (6领域并行)
        2. 知识库更新
        3. 文案生成 (中英文)
        4. 音频生成 (中英文并行)
        5. 测评
        """
        from app.agents.news_collector_agent import NewsCollectorAgent
        from app.agents.knowledge_base_agent import KnowledgeBaseAgent
        from app.agents.script_writer_agent import ScriptWriterAgent
        from app.agents.audio_producer_agent import AudioProducerAgent
        from app.agents.evaluation_agent import EvaluationAgent

        results = {"date": date_str, "steps": []}
        timer = Timer()

        # ========== Step 1: 新闻采集 (6领域并行) ==========
        timer.__enter__()
        self._update_job_progress(10, "正在采集6个领域的新闻...")
        try:
            news_agent = NewsCollectorAgent(task_id=self.task_id)
            all_news = await news_agent.run(date_str=date_str)
            results["news_items"] = all_news
            results["steps"].append({"step": "news_collection", "status": "success", "count": len(all_news)})
        except Exception as e:
            logger.error(f"News collection failed: {e}")
            results["steps"].append({"step": "news_collection", "status": "failed", "error": str(e)})
            timer.__exit__()
            AgentLogger.log(self.name, "news_collection", {"date": date_str}, None,
                            status="failed", error=str(e), duration_ms=timer.elapsed_ms)
            self._update_job_progress(0, f"新闻采集失败: {e}", status="failed", error=str(e))
            return results
        timer.__exit__()
        AgentLogger.log(self.name, "news_collection", {"date": date_str}, {"count": len(all_news)},
                        duration_ms=timer.elapsed_ms, task_id=self.task_id)

        # 检查新闻是否采集成功
        if not all_news:
            logger.error("No news collected, aborting podcast generation")
            results["steps"].append({"step": "news_collection", "status": "failed", "error": "0 news items collected"})
            self._update_job_progress(0, "新闻采集失败：未获取到任何新闻，请检查网络或API", status="failed", error="no news collected")
            return results

        # ========== Step 2: 知识库更新 ==========
        timer.__enter__()
        self._update_job_progress(35, "正在更新知识库...")
        try:
            kb_agent = KnowledgeBaseAgent(task_id=self.task_id)
            kb_result = await kb_agent.run(news_items=all_news, date_str=date_str)
            results["kb_result"] = kb_result
            results["steps"].append({"step": "knowledge_base", "status": "success"})
        except Exception as e:
            logger.error(f"KB update failed: {e}")
            results["steps"].append({"step": "knowledge_base", "status": "failed", "error": str(e)})
        timer.__exit__()
        AgentLogger.log(self.name, "knowledge_base", {"news_count": len(all_news)}, None,
                        duration_ms=timer.elapsed_ms, task_id=self.task_id)

        # ========== Step 3: 文案生成 (中英文) ==========
        timer.__enter__()
        self._update_job_progress(55, "正在生成播客文案...")
        try:
            script_agent = ScriptWriterAgent(task_id=self.task_id)
            scripts = await script_agent.run(news_items=all_news, date_str=date_str)

            # 检查文案是否有效
            if not scripts.get("script_zh") or not scripts.get("script_en"):
                raise ValueError("Script generation returned empty content")

            results["scripts"] = scripts
            results["steps"].append({"step": "script_writing", "status": "success"})
        except Exception as e:
            logger.error(f"Script writing failed: {e}")
            results["steps"].append({"step": "script_writing", "status": "failed", "error": str(e)})
            timer.__exit__()
            self._update_job_progress(55, f"文案生成失败: {e}", status="failed", error=str(e))
            return results
        timer.__exit__()
        AgentLogger.log(self.name, "script_writing", {"date": date_str}, None,
                        duration_ms=timer.elapsed_ms, task_id=self.task_id)

        # ========== Step 4: 音频生成 (中英文并行) ==========
        timer.__enter__()
        self._update_job_progress(75, "正在生成播客音频...")
        try:
            audio_agent = AudioProducerAgent(task_id=self.task_id)
            audio_zh_task = asyncio.create_task(
                audio_agent.run(script=scripts["script_zh"], lang="zh", date_str=date_str)
            )
            audio_en_task = asyncio.create_task(
                audio_agent.run(script=scripts["script_en"], lang="en", date_str=date_str)
            )
            audio_zh_result, audio_en_result = await asyncio.gather(
                audio_zh_task, audio_en_task, return_exceptions=True
            )
            results["audio_zh"] = audio_zh_result if not isinstance(audio_zh_result, Exception) else {"error": str(audio_zh_result)}
            results["audio_en"] = audio_en_result if not isinstance(audio_en_result, Exception) else {"error": str(audio_en_result)}
            results["steps"].append({"step": "audio_production", "status": "success"})
        except Exception as e:
            logger.error(f"Audio production failed: {e}")
            results["steps"].append({"step": "audio_production", "status": "failed", "error": str(e)})
        timer.__exit__()
        AgentLogger.log(self.name, "audio_production", {"date": date_str}, None,
                        duration_ms=timer.elapsed_ms, task_id=self.task_id)

        # ========== Step 5: 更新播客记录 ==========
        self._update_job_progress(90, "正在保存播客记录...")
        try:
            self._save_podcast_record(date_str, results)
        except Exception as e:
            logger.error(f"Save podcast record failed: {e}")

        # ========== Step 6: 测评 ==========
        timer.__enter__()
        self._update_job_progress(95, "正在评估生成质量...")
        try:
            eval_agent = EvaluationAgent(task_id=self.task_id)
            eval_result = await eval_agent.run(job_results=results)
            results["evaluation"] = eval_result
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
        timer.__exit__()

        # ========== 完成 ==========
        self._update_job_progress(100, "播客生成完成！", status="success")
        AgentLogger.log(self.name, "pipeline_complete", {"date": date_str}, results,
                        task_id=self.task_id)
        return results

    async def run(self, **kwargs) -> Any:
        """主入口 —— 根据参数决定执行哪个流水线"""
        action = kwargs.get("action", "generate_podcast")
        if action == "generate_podcast":
            return await self.run_podcast_pipeline(kwargs["date_str"])
        elif action == "process_feedback":
            from app.agents.feedback_optimizer_agent import FeedbackOptimizerAgent
            fb_agent = FeedbackOptimizerAgent(task_id=self.task_id)
            return await fb_agent.run(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")

    def _update_job_progress(self, progress: int, detail: str, status: str = "running", error: str = None):
        """更新任务进度"""
        if not self.task_id:
            return
        with get_db() as conn:
            conn.execute(
                "UPDATE generation_jobs SET progress=?, detail=?, status=?, error=?, updated_at=datetime('now') WHERE id=?",
                (progress, detail, status, error, self.task_id)
            )

    def _save_podcast_record(self, date_str: str, results: dict):
        """保存播客记录到数据库"""
        audio_zh = results.get("audio_zh", {})
        audio_en = results.get("audio_en", {})
        scripts = results.get("scripts", {})

        with get_db() as conn:
            # 检查是否已有记录
            existing = conn.execute(
                "SELECT id FROM podcasts WHERE date=?", (date_str,)
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE podcasts SET
                       script_zh_path=?, script_en_path=?,
                       audio_zh_path=?, audio_en_path=?,
                       duration_zh=?, duration_en=?, status='ready'
                       WHERE date=?""",
                    (
                        scripts.get("script_zh_path"),
                        scripts.get("script_en_path"),
                        audio_zh.get("audio_path"),
                        audio_en.get("audio_path"),
                        audio_zh.get("duration"),
                        audio_en.get("duration"),
                        date_str,
                    )
                )
            else:
                conn.execute(
                    """INSERT INTO podcasts
                       (date, script_zh_path, script_en_path, audio_zh_path, audio_en_path,
                        duration_zh, duration_en, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'ready')""",
                    (
                        date_str,
                        scripts.get("script_zh_path"),
                        scripts.get("script_en_path"),
                        audio_zh.get("audio_path"),
                        audio_en.get("audio_path"),
                        audio_zh.get("duration"),
                        audio_en.get("duration"),
                    )
                )
