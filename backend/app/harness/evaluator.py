"""测评引擎 —— 数据驱动的 Agent 优化机制"""

import json
from typing import Optional
from app.harness.logger import AgentLogger
from app.tools.zhipu_client import ZhipuClient


class Evaluator:
    """Agent 输出质量测评引擎"""

    EVALUATION_CRITERIA = {
        "news_collector_agent": "评估新闻采集质量：覆盖度（是否覆盖所有领域）、准确性（信息是否准确）、去重率（是否有重复新闻）、图片质量（是否有配图）、来源可靠性。",
        "knowledge_base_agent": "评估知识库维护质量：页面一致性、交叉引用完整度、信息时效性、摘要质量、索引更新。",
        "script_writer_agent": "评估播客文案质量：内容连贯性、时长符合度（约2500-3000字中文）、标签使用合理性、中英文一致性、对谈自然度、领域覆盖。",
        "audio_producer_agent": "评估音频制作质量：生成成功率、音色匹配度（marcus/chloe）、拼接流畅度、音频时长。",
        "orchestrator_agent": "评估编排质量：任务拆解合理性、步骤依赖正确性、执行监控有效性、错误处理。",
        "feedback_optimizer_agent": "评估反馈处理质量：问题诊断准确性、优化建议合理性。",
        "evaluation_agent": "评估测评质量：评分合理性、badcase检测准确性、建议可行性。",
        "kb_search_agent": "评估知识库搜索质量：回答准确性、来源引用完整度、理解用户意图、表达清晰度、信息覆盖度。",
    }

    def __init__(self):
        self.zhipu = ZhipuClient()

    def evaluate_log(self, log_id: int) -> dict:
        """评估单条 Agent 日志"""
        log = AgentLogger.get_log(log_id)
        if not log:
            return {"error": "log not found"}

        agent_name = log["agent_name"]
        criteria = self.EVALUATION_CRITERIA.get(
            agent_name, "评估该 Agent 的输出质量。"
        )

        # 构建评估 prompt
        prompt = f"""你是 Agent 测评引擎。请评估以下 Agent 调用的输出质量。

Agent: {agent_name}
步骤: {log['step']}
输入: {log['input'][:2000] if log['input'] else 'N/A'}
输出: {log['output'][:2000] if log['output'] else 'N/A'}
状态: {log['status']}
错误: {log['error'] or '无'}

评估标准: {criteria}

请以 JSON 格式输出:
{{
  "score": 1-5的整数,
  "comment": "评语（指出优点和不足）",
  "badcases": [
    {{"category": "问题类别", "description": "问题描述", "severity": "low/medium/high", "suggestion": "优化建议"}}
  ]
}}

如果状态为 failed，score 应为 1-2。如果输出质量良好，badcases 可以为空数组。"""

        try:
            response = self.zhipu.chat(prompt)
            result = self._parse_evaluation(response)

            # 更新日志质量评分
            AgentLogger.update_quality(
                log_id, result["score"], result["comment"]
            )

            # 记录 badcase
            for bc in result.get("badcases", []):
                AgentLogger.log_badcase(
                    agent_log_id=log_id,
                    category=bc.get("category", "unknown"),
                    description=bc.get("description", ""),
                    severity=bc.get("severity", "medium"),
                    suggestion=bc.get("suggestion", ""),
                )

            return result

        except Exception as e:
            return {"error": f"evaluation failed: {e}"}

    def evaluate_agent_recent(self, agent_name: str, limit: int = 10) -> dict:
        """评估某 Agent 最近的调用"""
        logs = AgentLogger.get_logs(agent_name=agent_name, limit=limit)
        if not logs:
            return {"agent_name": agent_name, "message": "no logs found"}

        results = []
        for log in logs:
            if log["quality_score"] is None:
                r = self.evaluate_log(log["id"])
                results.append({"log_id": log["id"], **r})
            else:
                results.append({
                    "log_id": log["id"],
                    "score": log["quality_score"],
                    "comment": log["quality_comment"],
                })

        avg_score = sum(r.get("score", 0) for r in results) / len(results) if results else 0
        return {
            "agent_name": agent_name,
            "evaluated_count": len(results),
            "avg_score": round(avg_score, 2),
            "results": results,
        }

    def _parse_evaluation(self, response: str) -> dict:
        """解析 GLM 返回的评估结果"""
        # 尝试从响应中提取 JSON
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找到第一个 { 和最后一个 }
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(response[start:end + 1])
            except json.JSONDecodeError:
                pass

        return {
            "score": 3,
            "comment": f"无法解析评估结果: {response[:200]}",
            "badcases": [],
        }
