"""Feedback Optimizer Agent —— 反馈优化 Agent

分析用户反馈，执行优化动作，使 Agent 持续改进。
"""

import logging
import json
from typing import Any, Optional
from app.harness.base_agent import BaseAgent
from app.harness.logger import AgentLogger
from app.tools.zhipu_client import ZhipuClient
from app.database import get_db

logger = logging.getLogger(__name__)


class FeedbackOptimizerAgent(BaseAgent):
    name = "feedback_optimizer_agent"

    def __init__(self, task_id: Optional[str] = None):
        super().__init__(task_id)
        self.zhipu = ZhipuClient()

    async def run(self, feedback_id: int = None, **kwargs) -> dict:
        """处理一条用户反馈"""
        if not feedback_id:
            return {"error": "no feedback_id"}

        # 获取反馈
        with get_db() as conn:
            fb = conn.execute(
                "SELECT * FROM feedback WHERE id=?", (feedback_id,)
            ).fetchone()
            if not fb:
                return {"error": "feedback not found"}
            feedback = dict(fb)

        # Step 1: 分析反馈
        analysis = self._analyze_feedback(feedback)

        # Step 2: 诊断根因并生成优化建议
        optimization = self._generate_optimization(analysis, feedback)

        # Step 3: 应用优化
        applied = self._apply_optimization(optimization)

        # Step 4: 标记反馈已处理
        with get_db() as conn:
            conn.execute(
                "UPDATE feedback SET status='processed' WHERE id=?", (feedback_id,)
            )

        result = {
            "feedback_id": feedback_id,
            "analysis": analysis,
            "optimization": optimization,
            "applied": applied,
        }
        AgentLogger.log(
            self.name, "process_feedback",
            feedback, result,
            tools_used=["zhipu_chat", "update_config"],
            task_id=self.task_id
        )
        return result

    def _analyze_feedback(self, feedback: dict) -> dict:
        """用 GLM-5.1 分析反馈内容"""
        prompt = f"""请分析以下用户反馈:

反馈类型: {feedback.get('type', 'unknown')}
反馈内容: {feedback.get('content', '')}
播客ID: {feedback.get('podcast_id', 'N/A')}

请分析:
1. 反馈涉及哪个 Agent（news_collector/script_writer/audio_producer/knowledge_base）
2. 问题的具体类别（内容准确性/播客风格/时长/标签使用/翻译质量/知识库错误/其他）
3. 严重程度（low/medium/high）
4. 具体问题描述

以 JSON 格式输出:
{{
  "target_agent": "agent名称",
  "category": "问题类别",
  "severity": "low/medium/high",
  "description": "问题描述",
  "root_cause": "根因分析"
}}"""

        try:
            return self.zhipu.chat_json(prompt, temperature=0.3, max_tokens=1024)
        except Exception as e:
            logger.error(f"Feedback analysis failed: {e}")
            return {
                "target_agent": "unknown",
                "category": "unknown",
                "severity": "medium",
                "description": feedback.get("content", ""),
                "root_cause": "analysis failed"
            }

    def _generate_optimization(self, analysis: dict, feedback: dict) -> dict:
        """生成优化建议"""
        target_agent = analysis.get("target_agent", "unknown")

        prompt = f"""基于以下反馈分析，生成 Agent 优化建议:

目标 Agent: {target_agent}
问题类别: {analysis.get('category', '')}
严重程度: {analysis.get('severity', '')}
问题描述: {analysis.get('description', '')}
根因: {analysis.get('root_cause', '')}
原始反馈: {feedback.get('content', '')}

请生成具体的优化建议:
1. 是否需要调整 prompt（如果需要，给出调整方向）
2. 是否需要调整参数（temperature等）
3. 是否需要修正知识库内容
4. 其他优化措施

以 JSON 格式输出:
{{
  "need_prompt_update": true/false,
  "prompt_adjustment": "prompt调整方向",
  "need_param_update": true/false,
  "param_adjustment": {{"temperature": 0.7}},
  "need_kb_correction": true/false,
  "kb_correction_detail": "知识库修正详情",
  "other_actions": "其他措施"
}}"""

        try:
            return self.zhipu.chat_json(prompt, temperature=0.3, max_tokens=1024)
        except Exception as e:
            logger.error(f"Optimization generation failed: {e}")
            return {
                "need_prompt_update": False,
                "prompt_adjustment": "",
                "need_param_update": False,
                "param_adjustment": {},
                "need_kb_correction": False,
                "kb_correction_detail": "",
                "other_actions": ""
            }

    def _apply_optimization(self, optimization: dict) -> dict:
        """应用优化建议"""
        applied = []

        if optimization.get("need_prompt_update"):
            # 创建新的 prompt 版本
            adjustment = optimization.get("prompt_adjustment", "")
            if adjustment:
                # 获取当前 prompt
                from app.harness.prompts import DEFAULT_PROMPTS
                # 在实际应用中，这里会基于调整方向生成新 prompt
                # 简化实现：记录调整建议到日志
                applied.append(f"prompt调整建议已记录: {adjustment}")
                logger.info(f"Prompt optimization recorded: {adjustment}")

        if optimization.get("need_param_update"):
            params = optimization.get("param_adjustment", {})
            if params:
                applied.append(f"参数调整建议已记录: {json.dumps(params, ensure_ascii=False)}")

        if optimization.get("need_kb_correction"):
            detail = optimization.get("kb_correction_detail", "")
            if detail:
                applied.append(f"知识库修正建议: {detail}")

        other = optimization.get("other_actions", "")
        if other:
            applied.append(f"其他措施: {other}")

        return {"actions": applied}
