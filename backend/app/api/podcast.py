"""播客 API 路由"""

import asyncio
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import (
    PodcastGenerateRequest, PodcastGenerateResponse,
    PodcastSummary, PodcastDetail,
    FeedbackRequest, FeedbackResponse,
    JobStatus, JobListResponse,
)
from app.database import get_db
from app.config import settings

router = APIRouter(prefix="/podcast", tags=["podcast"])


@router.post("/generate", response_model=PodcastGenerateResponse)
async def generate_podcast(req: PodcastGenerateRequest):
    """触发今日播客生成"""
    from datetime import datetime
    from pathlib import Path
    from app.config import settings

    date_str = req.date or datetime.now().strftime("%Y-%m-%d")

    # 检查是否已有该日期的播客 —— 允许重新生成
    existing_podcast_id = None
    existing_job_running = False
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id, status FROM podcasts WHERE date=?", (date_str,)
        ).fetchone()
        if existing:
            existing_podcast_id = existing["id"]

        # 检查是否已有正在运行的任务
        running = conn.execute(
            "SELECT id FROM generation_jobs WHERE status='running' AND type='podcast' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if running:
            existing_job_running = True

    # 如果已有任务在运行，不重复启动
    if existing_job_running:
        return PodcastGenerateResponse(
            job_id=running["id"], status="running",
            message=f"{date_str} 的播客正在生成中，请等待完成"
        )

    # 清理旧播客文件（如果已存在）
    if existing:
        old_podcast_dir = settings.PODCAST_DIR / date_str
        if old_podcast_dir.exists():
            import shutil
            shutil.rmtree(old_podcast_dir, ignore_errors=True)

    # 创建生成任务
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO generation_jobs (type, status, progress, detail) "
            "VALUES ('podcast', 'running', 0, '正在启动...')",
        )
        job_id = cur.lastrowid

        # 重置播客记录为生成中状态
        if existing:
            conn.execute(
                "UPDATE podcasts SET status='generating', "
                "script_zh_path=NULL, script_en_path=NULL, "
                "audio_zh_path=NULL, audio_en_path=NULL, "
                "duration_zh=NULL, duration_en=NULL WHERE date=?",
                (date_str,)
            )
        else:
            conn.execute(
                "INSERT INTO podcasts (date, status) VALUES (?, 'generating')",
                (date_str,)
            )

    # 异步启动流水线
    from app.agents.orchestrator_agent import OrchestratorAgent
    agent = OrchestratorAgent(task_id=str(job_id))

    # 在后台运行
    asyncio.create_task(agent.run(action="generate_podcast", date_str=date_str))

    return PodcastGenerateResponse(
        job_id=job_id, status="running",
        message=f"{date_str} 的播客生成已启动"
    )


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(limit: int = Query(10, ge=1, le=50)):
    """获取生成任务列表"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM generation_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return JobListResponse(jobs=[dict(r) for r in rows])


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: int):
    """获取单个任务状态"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM generation_jobs WHERE id=?", (job_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobStatus(**dict(row))


@router.get("/list", response_model=list[PodcastSummary])
async def list_podcasts(limit: int = Query(30, ge=1, le=100)):
    """获取播客列表"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM podcasts ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["has_audio_zh"] = bool(d.get("audio_zh_path"))
            d["has_audio_en"] = bool(d.get("audio_en_path"))
            result.append(PodcastSummary(**d))
        return result


@router.get("/{podcast_id}", response_model=PodcastDetail)
async def get_podcast(podcast_id: int):
    """获取播客详情"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM podcasts WHERE id=?", (podcast_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Podcast not found")

        d = dict(row)
        d["has_audio_zh"] = bool(d.get("audio_zh_path"))
        d["has_audio_en"] = bool(d.get("audio_en_path"))

        # 读取文案
        script_zh = None
        script_en = None
        if d.get("script_zh_path"):
            from pathlib import Path
            p = Path(d["script_zh_path"])
            if p.exists():
                script_zh = p.read_text(encoding="utf-8")
        if d.get("script_en_path"):
            from pathlib import Path
            p = Path(d["script_en_path"])
            if p.exists():
                script_en = p.read_text(encoding="utf-8")
        d["script_zh"] = script_zh
        d["script_en"] = script_en

        # 获取新闻
        news_rows = conn.execute(
            "SELECT * FROM news_items WHERE podcast_date=? ORDER BY domain",
            (d["date"],)
        ).fetchall()
        d["news_items"] = [dict(r) for r in news_rows]

        return PodcastDetail(**d)


@router.get("/{podcast_id}/audio")
async def get_podcast_audio(
    podcast_id: int,
    lang: str = Query("zh", regex="^(zh|en)$"),
):
    """流式返回音频文件"""
    from fastapi.responses import FileResponse
    from pathlib import Path

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM podcasts WHERE id=?", (podcast_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Podcast not found")

        path_field = f"audio_{lang}_path"
        audio_path = row[path_field]
        if not audio_path or not Path(audio_path).exists():
            raise HTTPException(status_code=404, detail=f"Audio ({lang}) not found")

        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            filename=f"podcast_{row['date']}_{lang}.mp3"
        )


@router.get("/{podcast_id}/download")
async def download_podcast_audio(
    podcast_id: int,
    lang: str = Query("zh", regex="^(zh|en)$"),
):
    """下载音频文件（带 Content-Disposition 触发浏览器下载）"""
    from fastapi.responses import FileResponse
    from pathlib import Path

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM podcasts WHERE id=?", (podcast_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Podcast not found")

        path_field = f"audio_{lang}_path"
        audio_path = row[path_field]
        if not audio_path or not Path(audio_path).exists():
            raise HTTPException(status_code=404, detail=f"Audio ({lang}) not found")

        filename = f"podcast_{row['date']}_{lang}.mp3"
        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )


@router.post("/{podcast_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(podcast_id: int, req: FeedbackRequest):
    """提交反馈"""
    with get_db() as conn:
        # 验证播客存在
        row = conn.execute(
            "SELECT id FROM podcasts WHERE id=?", (podcast_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Podcast not found")

        cur = conn.execute(
            "INSERT INTO feedback (podcast_id, type, content) VALUES (?, ?, ?)",
            (podcast_id, req.type, req.content)
        )
        feedback_id = cur.lastrowid

    # 异步触发反馈优化
    from app.agents.feedback_optimizer_agent import FeedbackOptimizerAgent
    agent = FeedbackOptimizerAgent()
    asyncio.create_task(agent.run(feedback_id=feedback_id))

    return FeedbackResponse(
        id=feedback_id, status="pending",
        message="反馈已提交，正在处理"
    )


@router.get("/logs/stream")
async def stream_logs():
    """SSE 实时日志流 —— 供客户端实时查看生成进度"""
    from fastapi.responses import StreamingResponse
    import subprocess
    import asyncio

    async def log_generator():
        # 使用 journalctl 实时跟踪服务日志
        proc = await asyncio.create_subprocess_exec(
            "journalctl", "-u", "listenandlearn", "-f", "--no-pager", "-o", "cat",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield f"data: {line.decode().strip()}\n\n"
        finally:
            proc.terminate()

    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
