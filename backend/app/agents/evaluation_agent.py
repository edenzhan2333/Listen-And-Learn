"""Evaluation Agent —— 测评 Agent

数据驱动的 Agent 优化机制 —— 评估各 Agent 输出质量，检测 badcase，生成优化建议。
"""

import logging
import asyncio
from typing import Any, Optional
from app.harness.base_agent import BaseAgent
from app.harness.logger import AgentLogger
from app.harness.evaluator import Evaluator
from app.tools.zhipu_client import ZhipuClient
from app.database import get_db

logger = logging.getLogger(__name__)


class EvaluationAgent(BaseAgent):
    name = "evaluation_agent"

    def __init__(self, task_id: Optional[str] = None):
        super().__init__(task_id)
        self.zhipu = ZhipuClient()
        self.evaluator = Evaluator()

    async def run(self, job_results: dict = None, **kwargs) -> dict:
        """评估一次播客生成流程中各 Agent 的输出质量"""
        if not job_results:
            return {"error": "no job results"}

        # 获取本次任务相关的所有日志
        logs = AgentLogger.get_logs(limit=50)
        if self.task_id:
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT * FROM agent_logs WHERE task_id=? ORDER BY created_at ASC",
                    (self.task_id,)
                ).fetchall()
                logs = [dict(r) for r in rows]

        # 评估每条未评分的日志
        eval_results = []
        for log in logs:
            if log.get("quality_score") is None:
                # 用 asyncio 包装同步调用
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.evaluator.evaluate_log, log["id"]
                )
                eval_results.append({"log_id": log["id"], **result})

        # 汇总
        summary = self._summarize_evaluation(eval_results, job_results)

        AgentLogger.log(
            self.name, "evaluate_job",
            {"task_id": self.task_id, "log_count": len(logs)},
            summary,
            tools_used=["zhipu_chat"],
            task_id=self.task_id
        )
        return summary

    def _summarize_evaluation(self, eval_results: list[dict], job_results: dict) -> dict:
        """汇总评估结果"""
        scores = [r.get("score", 3) for r in eval_results if "score" in r]
        avg_score = sum(scores) / len(scores) if scores else 0

        badcases_count = sum(len(r.get("badcases", [])) for r in eval_results)

        # 生成整体优化建议
        prompt = f"""请基于以下 Agent 评估结果，生成整体优化建议:

评估结果: {eval_results[:5]}
平均分: {avg_score:.1f}/5
Badcase数: {badcases_count}

播客生成结果:
- 新闻采集: {len(job_results.get('news_items', []))} 条
- 文案生成: {'成功' if job_results.get('scripts') else '失败'}
- 中文音频: {'成功' if job_results.get('audio_zh', {}).get('audio_path') else '失败'}
- 英文音频: {'成功' if job_results.get('audio_en', {}).get('audio_path') else '失败'}

请给出:
1. 整体质量评价
2. 主要问题（按严重程度排序）
3. 优化建议（具体可执行）

以 JSON 格式输出:
{{
  "overall_quality": "评价",
  "main_issues": ["问题1", "问题2"],
  "optimization_suggestions": ["建议1", "建议2"]
}}"""

        try:
            suggestions = self.zhipu.chat_json(prompt, temperature=0.3, max_tokens=2048)
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            suggestions = {
                "overall_quality": f"平均分 {avg_score:.1f}/5",
                "main_issues": [],
                "optimization_suggestions": []
            }

        return {
            "evaluated_logs": len(eval_results),
            "avg_score": round(avg_score, 2),
            "total_badcases": badcases_count,
            "details": eval_results,
            "summary": suggestions,
        }
