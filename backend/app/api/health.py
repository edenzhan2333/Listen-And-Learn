"""健康检查 API —— 客户端首次配置时测试连接"""

from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查 —— 客户端测试后端连接"""
    return HealthResponse(status="ok", version="1.0.0")


@router.get("/config")
async def get_config():
    """返回基本配置信息（不含敏感信息）"""
    return {
        "domains": settings.DOMAINS,
        "max_podcast_days": settings.MAX_PODCAST_DAYS,
        "male_voice": settings.MALE_VOICE,
        "female_voice": settings.FEMALE_VOICE,
    }
