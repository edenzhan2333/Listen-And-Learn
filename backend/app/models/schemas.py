"""Pydantic 数据模型 —— API 请求/响应 Schema"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import date


# ===== 健康检查 =====
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


# ===== 播客 =====
class PodcastGenerateRequest(BaseModel):
    date: Optional[str] = None  # YYYY-MM-DD，默认今天


class PodcastGenerateResponse(BaseModel):
    job_id: int
    status: str = "running"
    message: str = "播客生成已启动"


class PodcastSummary(BaseModel):
    id: int
    date: str
    status: str
    duration_zh: Optional[int] = None
    duration_en: Optional[int] = None
    has_audio_zh: bool = False
    has_audio_en: bool = False
    created_at: str


class PodcastDetail(BaseModel):
    id: int
    date: str
    status: str
    script_zh: Optional[str] = None
    script_en: Optional[str] = None
    duration_zh: Optional[int] = None
    duration_en: Optional[int] = None
    has_audio_zh: bool = False
    has_audio_en: bool = False
    news_items: list[dict] = []
    created_at: str


class FeedbackRequest(BaseModel):
    type: str = Field(description="反馈类型: content/style/duration/tag/kb_error")
    content: str = Field(description="反馈内容")


class FeedbackResponse(BaseModel):
    id: int
    status: str = "pending"
    message: str = "反馈已提交"


# ===== 知识库 =====
class KBSearchResponse(BaseModel):
    query: str
    results: list[dict]


class KBPageListResponse(BaseModel):
    domain: Optional[str] = None
    pages: list[dict]


class KBPageDetail(BaseModel):
    path: str
    title: str
    content: str  # HTML 或 markdown
    domain: Optional[str] = None
    category: Optional[str] = None


# ===== 监控 =====
class MonitorOverview(BaseModel):
    agents: list[dict]
    total_badcases: int
    unresolved_badcases: int


class AgentLogList(BaseModel):
    logs: list[dict]
    total: int


class BadcaseList(BaseModel):
    badcases: list[dict]


class AgentConfigUpdate(BaseModel):
    prompt_text: Optional[str] = None
    parameters: Optional[dict] = None


# ===== 任务 =====
class JobStatus(BaseModel):
    id: int
    type: str
    status: str
    progress: int
    detail: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class JobListResponse(BaseModel):
    jobs: list[dict]
