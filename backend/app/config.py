"""应用配置 —— 从环境变量加载所有配置项"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- 阿里云 CosyVoice (音频生成) ---
    DASHSCOPE_API_KEY: str = ""
    TTS_MODEL: str = "cosyvoice-v3-plus"
    MALE_VOICE: str = "longanyang"        # 龙安洋，阳光大男孩
    FEMALE_VOICE: str = "longanhuan"      # 龙安欢，欢脱元气女

    # --- 智谱AI (文本生成 / Agent 编排) ---
    ZAI_API_KEY: str = ""
    ZAI_MODEL: str = "glm-5.2"            # 使用 glm-5.2
    ZAI_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4/"

    # --- 服务配置 ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- 路径 ---
    DATA_DIR: Path = Path("/opt/listenandlearn/data")
    KB_DIR: Path = Path("")             # 运行时拼接
    PODCAST_DIR: Path = Path("")
    NEWS_DIR: Path = Path("")
    DB_PATH: Path = Path("")

    # --- 播客配置 ---
    MAX_PODCAST_DAYS: int = 180         # 播客文件保留天数

    # --- 领域（只专注AI领域） ---
    DOMAINS: list[str] = ["AI"]
    DOMAIN_KEYS: dict[str, str] = {"AI": "ai"}
    NEWS_PER_DOMAIN: int = 10          # 每天最多10条新闻
    NEWS_SOURCE_URL: str = "https://news.aibase.com/zh/news"

    # --- Agent ---
    MAX_RETRIES: int = 3
    TOOL_TIMEOUT: int = 60

    class Config:
        env_file = ".env"
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 拼接运行时路径
        self.KB_DIR = self.DATA_DIR / "knowledge_base"
        self.PODCAST_DIR = self.DATA_DIR / "podcasts"
        self.NEWS_DIR = self.DATA_DIR / "news"
        self.DB_PATH = self.DATA_DIR / "listenandlearn.db"

    def ensure_dirs(self):
        """确保所有数据目录存在（惰性创建，避免导入时出错）"""
        for d in [self.DATA_DIR, self.KB_DIR, self.PODCAST_DIR, self.NEWS_DIR]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
# 惰性创建目录 —— 不在导入时执行，由 main.py 的 lifespan 调用 ensure_dirs()
