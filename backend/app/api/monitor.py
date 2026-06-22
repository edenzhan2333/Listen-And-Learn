"""监控 API 路由 —— Agent 日志、Badcase、指标、配置"""

from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import MonitorOverview, AgentLogList, BadcaseList, AgentConfigUpdate
from app.harness.logger import AgentLogger
from app.database import get_db
import json

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/overview", response_model=MonitorOverview)
async def overview():
    """监控总览"""
    data = AgentLogger.get_overview()
    return MonitorOverview(**data)


@router.get("/logs", response_model=AgentLogList)
async def list_logs(
    agent_name: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """Agent 日志列表"""
    logs = AgentLogger.get_logs(
        agent_name=agent_name, status=status, limit=limit, offset=offset
    )
    total = len(logs)
    return AgentLogList(logs=logs, total=total)


@router.get("/logs/{log_id}")
async def get_log(log_id: int):
    """日志详情"""
    log = AgentLogger.get_log(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log


@router.get("/evaluations")
async def get_evaluations(limit: int = Query(20, le=100)):
    """获取最近的评测结果（含评分/理由/正确率/评判标准）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT al.id, al.agent_name, al.step, al.status, al.quality_score,
                      al.quality_comment, al.input, al.output, al.error,
                      al.created_at,
                      (SELECT COUNT(*) FROM bad_cases bc WHERE bc.agent_log_id = al.id) as badcase_count,
                      (SELECT COUNT(*) FROM bad_cases bc WHERE bc.agent_log_id = al.id AND bc.resolved = 0) as unresolved_count
               FROM agent_logs al
               WHERE al.quality_score IS NOT NULL
               ORDER BY al.created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            # 解析 input/output 为摘要
            if d.get("input"):
                try:
                    d["input_preview"] = d["input"][:300]
                except Exception:
                    d["input_preview"] = ""
            if d.get("output"):
                try:
                    d["output_preview"] = d["output"][:300]
                except Exception:
                    d["output_preview"] = ""
            results.append(d)
        return {"evaluations": results}


@router.get("/evaluations/summary")
async def get_evaluations_summary():
    """获取各 Agent 的评测汇总（平均分/正确率/评测标准）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT agent_name,
                      COUNT(*) as total,
                      AVG(quality_score) as avg_score,
                      SUM(CASE WHEN quality_score >= 4 THEN 1 ELSE 0 END) as good_count,
                      SUM(CASE WHEN quality_score <= 2 THEN 1 ELSE 0 END) as bad_count,
                      SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
               FROM agent_logs
               WHERE quality_score IS NOT NULL
               GROUP BY agent_name"""
        ).fetchall()

        # 评测标准
        criteria = {
            "news_collector_agent": "新闻覆盖度、准确性、来源可靠性、摘要质量",
            "knowledge_base_agent": "页面一致性、交叉引用完整度、信息时效性",
            "script_writer_agent": "内容连贯性、时长符合度、SSML标签合理性、中英一致性",
            "audio_producer_agent": "生成成功率、音色匹配度、拼接流畅度",
            "orchestrator_agent": "任务拆解合理性、执行监控有效性",
            "feedback_optimizer_agent": "问题诊断准确性、优化建议合理性",
            "evaluation_agent": "评分合理性、badcase检测准确性",
        }

        results = []
        for r in rows:
            total = r["total"] or 0
            good = r["good_count"] or 0
            success = r["success_count"] or 0
            results.append({
                "agent_name": r["agent_name"],
                "total_evaluated": total,
                "avg_score": round(r["avg_score"] or 0, 2),
                "pass_rate": round(good / total * 100, 1) if total else 0,
                "success_rate": round(success / total * 100, 1) if total else 0,
                "bad_count": r["bad_count"] or 0,
                "criteria": criteria.get(r["agent_name"], "综合输出质量"),
            })

        return {"summary": results}


@router.get("/badcases", response_model=BadcaseList)
async def list_badcases(
    resolved: int = Query(None, description="0=未解决, 1=已解决, None=全部"),
    limit: int = Query(50, le=200),
):
    """Badcase 列表"""
    query = ("SELECT bc.id, bc.agent_log_id, bc.category, bc.description, "
             "bc.severity, bc.suggestion, bc.resolved, bc.created_at, "
             "al.agent_name, al.step "
             "FROM bad_cases bc LEFT JOIN agent_logs al ON bc.agent_log_id = al.id WHERE 1=1")
    params = []
    if resolved is not None:
        query += " AND bc.resolved=?"
        params.append(resolved)
    query += " ORDER BY bc.created_at DESC LIMIT ?"
    params.append(limit)
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return BadcaseList(badcases=[dict(r) for r in rows])


@router.post("/badcases/{badcase_id}/resolve")
async def resolve_badcase(badcase_id: int):
    """标记 Badcase 已处理"""
    with get_db() as conn:
        result = conn.execute(
            "UPDATE bad_cases SET resolved=1 WHERE id=?", (badcase_id,)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Badcase not found")
    return {"status": "resolved", "id": badcase_id}


@router.get("/metrics")
async def get_metrics(agent_name: str = Query(None)):
    """指标趋势"""
    query = "SELECT * FROM agent_metrics WHERE 1=1"
    params = []
    if agent_name:
        query += " AND agent_name=?"
        params.append(agent_name)
    query += " ORDER BY date DESC, created_at DESC LIMIT 100"
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return {"metrics": [dict(r) for r in rows]}


@router.get("/configs")
async def list_configs(agent_name: str = Query(None)):
    """Agent 配置列表"""
    query = "SELECT * FROM agent_configs WHERE 1=1"
    params = []
    if agent_name:
        query += " AND agent_name=?"
        params.append(agent_name)
    query += " ORDER BY agent_name, created_at DESC"
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        configs = []
        for r in rows:
            d = dict(r)
            if d.get("parameters"):
                try:
                    d["parameters"] = json.loads(d["parameters"])
                except Exception:
                    pass
            configs.append(d)
        return {"configs": configs}


@router.put("/configs/{config_id}")
async def update_config(config_id: int, req: AgentConfigUpdate):
    """更新 Agent 配置"""
    with get_db() as conn:
        # 先将旧配置设为非活跃
        old = conn.execute(
            "SELECT agent_name FROM agent_configs WHERE id=?", (config_id,)
        ).fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="Config not found")

        # 创建新版本
        old_config = conn.execute(
            "SELECT * FROM agent_configs WHERE id=?", (config_id,)
        ).fetchone()

        new_prompt = req.prompt_text or old_config["prompt_text"]
        new_params = json.dumps(req.parameters) if req.parameters else old_config["parameters"]

        # 将同 agent 的所有配置设为非活跃
        conn.execute(
            "UPDATE agent_configs SET active=0 WHERE agent_name=?",
            (old["agent_name"],)
        )

        # 插入新版本
        cur = conn.execute(
            "INSERT INTO agent_configs (agent_name, prompt_version, prompt_text, parameters, active) "
            "VALUES (?, ?, ?, ?, 1)",
            (
                old["agent_name"],
                f"v{int(old_config['prompt_version'][1:]) + 1}" if old_config["prompt_version"].startswith("v") else "v2",
                new_prompt,
                new_params,
            )
        )
        new_id = cur.lastrowid

    return {"id": new_id, "status": "updated", "message": "配置已更新，新版本已激活"}


@router.post("/evaluate")
async def trigger_evaluation(
    agent_name: str = Query(None),
    log_id: int = Query(None),
):
    """手动触发测评"""
    import asyncio
    from app.harness.evaluator import Evaluator

    evaluator = Evaluator()

    if log_id:
        result = await asyncio.get_event_loop().run_in_executor(
            None, evaluator.evaluate_log, log_id
        )
        return {"evaluation": result}
    elif agent_name:
        result = await asyncio.get_event_loop().run_in_executor(
            None, evaluator.evaluate_agent_recent, agent_name, 10
        )
        return {"evaluation": result}
    else:
        # 评估所有 Agent
        from app.harness.logger import AgentLogger
        overview = AgentLogger.get_overview()
        results = []
        for agent_info in overview["agents"]:
            name = agent_info["agent_name"]
            r = await asyncio.get_event_loop().run_in_executor(
                None, evaluator.evaluate_agent_recent, name, 5
            )
            results.append(r)
        return {"evaluations": results}
