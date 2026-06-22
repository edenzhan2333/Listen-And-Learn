"""工具注册中心 —— 每个 Agent 声明可用工具，框架统一注入和管理"""

from typing import Callable, Any, Dict, List, Optional
import asyncio
import functools
from app.config import settings


class Tool:
    """工具包装类"""

    def __init__(
        self,
        name: str,
        func: Callable,
        description: str = "",
        timeout: int = None,
    ):
        self.name = name
        self.func = func
        self.description = description
        self.timeout = timeout or settings.TOOL_TIMEOUT

    async def call(self, **kwargs) -> Any:
        """异步调用工具，带超时控制"""
        if asyncio.iscoroutinefunction(self.func):
            return await asyncio.wait_for(self.func(**kwargs), timeout=self.timeout)
        else:
            # 同步函数包装为异步
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, functools.partial(self.func, **kwargs)),
                timeout=self.timeout,
            )


class ToolRegistry:
    """工具注册中心"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(
        self,
        name: str,
        func: Callable,
        description: str = "",
        timeout: int = None,
    ):
        """注册一个工具"""
        self._tools[name] = Tool(name, func, description, timeout)

    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def get_many(self, names: List[str]) -> Dict[str, Tool]:
        """获取多个工具"""
        return {n: self._tools[n] for n in names if n in self._tools}

    def list_all(self) -> List[dict]:
        """列出所有已注册工具"""
        return [
            {"name": t.name, "description": t.description}
            for t in self._tools.values()
        ]


# 全局工具注册中心
registry = ToolRegistry()
