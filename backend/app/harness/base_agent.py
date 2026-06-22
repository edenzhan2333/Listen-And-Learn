"""Agent 基类 —— 所有 Agent 的公共基础设施"""

import json
import time
import traceback
from abc import ABC, abstractmethod
from typing import Any, Optional
from app.config import settings
from app.harness.logger import AgentLogger, Timer
from app.harness.tool_registry import ToolRegistry, registry
from app.database import get_db


class BaseAgent(ABC):
    """Agent 基类 —— 提供日志记录、错误重试、工具访问、prompt 管理能力"""

    name: str = "base_agent"

    def __init__(self, task_id: Optional[str] = None):
        self.task_id = task_id
        self.tools = registry  # 全局工具注册中心

    def get_prompt(self) -> str:
        """从数据库获取当前生效的 prompt"""
        with get_db() as conn:
            row = conn.execute(
                "SELECT prompt_text, parameters FROM agent_configs "
                "WHERE agent_name=? AND active=1 ORDER BY id DESC LIMIT 1",
                (self.name,),
            ).fetchone()
            if row:
                return row["prompt_text"]
        # 回退到默认
        from app.harness.prompts import DEFAULT_PROMPTS
        return DEFAULT_PROMPTS.get(self.name, "")

    def get_parameters(self) -> dict:
        """获取 Agent 参数"""
        with get_db() as conn:
            row = conn.execute(
                "SELECT parameters FROM agent_configs "
                "WHERE agent_name=? AND active=1 ORDER BY id DESC LIMIT 1",
                (self.name,),
            ).fetchone()
            if row and row["parameters"]:
                try:
                    return json.loads(row["parameters"])
                except Exception:
                    pass
        return {"temperature": 0.7}

    def run_logged(self, step: str, input_data: Any, tools_used: list[str] = None) -> tuple[int, Timer]:
        """开始一次带日志的执行，返回 (log_id, timer)"""
        timer = Timer()
        timer.__enter__()
        return 0, timer  # log_id 稍后在 finish_logged 中写入

    def finish_logged(
        self,
        agent_name: str,
        step: str,
        input_data: Any,
        output_data: Any,
        timer: Timer,
        tools_used: list[str] = None,
        status: str = "success",
        error: Optional[str] = None,
    ) -> int:
        """完成一次带日志的执行，写入数据库"""
        timer.__exit__()
        log_id = AgentLogger.log(
            agent_name=agent_name,
            task_id=self.task_id,
            step=step,
            input_data=input_data,
            output_data=output_data,
            tools_used=tools_used or [],
            status=status,
            error=error,
            duration_ms=timer.elapsed_ms,
        )
        return log_id

    def execute_with_logging(
        self,
        step: str,
        input_data: Any,
        exec_func,
        tools_used: list[str] = None,
    ) -> tuple[Any, int]:
        """执行一个函数并自动记录日志 + 错误重试"""
        timer = Timer()
        error = None
        result = None
        status = "success"

        for attempt in range(settings.MAX_RETRIES):
            timer = Timer()
            timer.__enter__()
            try:
                result = exec_func()
                status = "success"
                error = None
                break
            except Exception as e:
                timer.__exit__()
                error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                status = "failed"
                if attempt < settings.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    result = None

        if timer.elapsed_ms is None:
            timer.elapsed_ms = 0

        log_id = AgentLogger.log(
            agent_name=self.name,
            task_id=self.task_id,
            step=step,
            input_data=input_data,
            output_data=result,
            tools_used=tools_used or [],
            duration_ms=timer.elapsed_ms or 0,
            status=status,
            error=error,
        )
        return result, log_id

    @abstractmethod
    async def run(self, **kwargs) -> Any:
        """Agent 主执行逻辑（子类实现）"""
        ...
