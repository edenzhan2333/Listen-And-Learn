"""FastAPI 主入口 —— Listen and Learn 后端"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api import health, podcast, knowledge_base, monitor
from app.services.cleanup_service import CleanupService

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting Listen and Learn backend...")
    settings.ensure_dirs()
    init_db()
    logger.info("Database initialized")

    from app.tools.wiki_manager import WikiManager
    WikiManager().ensure_structure()
    logger.info("Knowledge base structure ensured")

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        CleanupService.run_cleanup,
        CronTrigger(hour=3, minute=0),
        id="cleanup_job"
    )
    scheduler.start()
    logger.info("Scheduled cleanup job (daily at 03:00)")
    app.state.scheduler = scheduler

    yield

    scheduler.shutdown(wait=False)
    logger.info("Listen and Learn backend stopped")


app = FastAPI(
    title="Listen and Learn",
    description="AI 播客 + 知识库全栈应用后端",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(podcast.router, prefix="/api", tags=["podcast"])
app.include_router(knowledge_base.router, prefix="/api", tags=["knowledge_base"])
app.include_router(monitor.router, prefix="/api", tags=["monitor"])


@app.get("/")
async def root():
    return {
        "name": "Listen and Learn",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
