"""Agent 日志记录器 —— Harness 框架自动记录每次 Agent 调用"""

import json
import time
import sqlite3
from datetime import datetime
from typing import Any, Optional
from app.database import get_db


class AgentLogger:
    """记录 Agent 调用日志到数据库"""

    @staticmethod
    def log(
        agent_name: str,
        step: str,
        input_data: Any,
        output_data: Any,
        tools_used: list[str] = None,
        task_id: Optional[str] = None,
        status: str = "success",
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
        quality_score: Optional[int] = None,
        quality_comment: Optional[str] = None,
    ) -> int:
        """记录一条 Agent 日志，返回日志 ID"""
        with get_db() as conn:
            cur = conn.execute(
                """INSERT INTO agent_logs
                   (agent_name, task_id, step, input, output, tools_used,
                    duration_ms, status, error, quality_score, quality_comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    agent_name,
                    task_id,
                    step,
                    json.dumps(input_data, ensure_ascii=False, default=str),
                    json.dumps(output_data, ensure_ascii=False, default=str),
                    json.dumps(tools_used or [], ensure_ascii=False),
                    duration_ms,
                    status,
                    error,
                    quality_score,
                    quality_comment,
                )
            )
            return cur.lastrowid

    @staticmethod
    def log_badcase(
        agent_log_id: int,
        category: str,
        description: str,
        severity: str = "medium",
        suggestion: str = "",
    ):
        """记录一个 badcase"""
        with get_db() as conn:
            conn.execute(
                """INSERT INTO bad_cases
                   (agent_log_id, category, description, severity, suggestion)
                   VALUES (?, ?, ?, ?, ?)""",
                (agent_log_id, category, description, severity, suggestion),
            )

    @staticmethod
    def update_quality(log_id: int, score: int, comment: str):
        """更新日志的质量评分"""
        with get_db() as conn:
            conn.execute(
                "UPDATE agent_logs SET quality_score=?, quality_comment=? WHERE id=?",
                (score, comment, log_id),
            )

    @staticmethod
    def get_logs(
        agent_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """查询日志列表"""
        query = "SELECT * FROM agent_logs WHERE 1=1"
        params = []
        if agent_name:
            query += " AND agent_name=?"
            params.append(agent_name)
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_log(log_id: int) -> Optional[dict]:
        """获取单条日志详情"""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM agent_logs WHERE id=?", (log_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_overview() -> dict:
        """获取监控总览统计"""
        with get_db() as conn:
            # 各 Agent 统计
            rows = conn.execute(
                """SELECT agent_name,
                          COUNT(*) as total,
                          SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success,
                          SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
                          AVG(duration_ms) as avg_duration,
                          AVG(quality_score) as avg_score
                   FROM agent_logs
                   GROUP BY agent_name"""
            ).fetchall()
            agents = []
            for r in rows:
                total = r["total"] or 0
                success = r["success"] or 0
                agents.append({
                    "agent_name": r["agent_name"],
                    "total_calls": total,
                    "success_count": success,
                    "failed_count": r["failed"] or 0,
                    "success_rate": round(success / total * 100, 1) if total else 0,
                    "avg_duration_ms": round(r["avg_duration"] or 0, 1),
                    "avg_quality_score": round(r["avg_score"] or 0, 2),
                })

            # badcase 统计
            bc = conn.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN resolved=0 THEN 1 ELSE 0 END) as unresolved FROM bad_cases"
            ).fetchone()

            return {
                "agents": agents,
                "total_badcases": bc["total"] or 0,
                "unresolved_badcases": bc["unresolved"] or 0,
            }


class Timer:
    """简单的计时上下文管理器"""

    def __init__(self):
        self.start_time = None
        self.elapsed_ms = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = int((time.time() - self.start_time) * 1000)
