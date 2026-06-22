"""智谱 AI (GLM-5.1) 客户端封装 —— 项目中所有文本类 AI 功能的唯一入口

严格规则:
- 模型固定为 glm-5.1
- 仅用于文本生成任务
- 支持: 对话 / web_search / function calling / 流式
"""

import json
import logging
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class ZhipuClient:
    """智谱 AI 客户端封装"""

    def __init__(self):
        self.api_key = settings.ZAI_API_KEY
        self.model = settings.ZAI_MODEL  # glm-5.1
        self.base_url = settings.ZAI_BASE_URL
        self._client = None

    @property
    def client(self):
        """惰性初始化 zai-sdk 客户端"""
        if self._client is None:
            try:
                from zai import ZhipuAiClient
                self._client = ZhipuAiClient(api_key=self.api_key)
            except ImportError:
                # 如果 zai-sdk 不可用，回退到直接 HTTP 调用
                logger.warning("zai-sdk not installed, using HTTP fallback")
                self._client = _HttpZhipuClient(self.api_key, self.base_url)
        return self._client

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: List[Dict] = None,
    ) -> str:
        """同步对话调用，返回文本内容"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.info(f"ZhipuAI chat: model={self.model}, prompt_len={len(prompt)}, max_tokens={max_tokens}")

        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)

            # 调试日志：检查响应结构
            choice = response.choices[0]
            content = choice.message.content
            finish_reason = getattr(choice, 'finish_reason', 'unknown')

            if not content:
                # content 为空时，只记录日志，绝不返回 reasoning_content（思考过程）
                # 之前 bug：把 reasoning_content 当作正文返回，导致文案充满思考过程
                reasoning = getattr(choice.message, 'reasoning_content', None)
                logger.error(
                    f"ZhipuAI returned empty content! "
                    f"finish_reason={finish_reason}, "
                    f"prompt_len={len(prompt)}, "
                    f"has_reasoning={bool(reasoning)}, "
                    f"reasoning_preview={reasoning[:200] if reasoning else 'N/A'}"
                )
                return ""

            logger.info(f"ZhipuAI response: content_len={len(content)}, finish_reason={finish_reason}")
            return content
        except Exception as e:
            logger.error(f"ZhipuAI chat failed: {e}")
            raise

    def chat_with_web_search(
        self,
        prompt: str,
        system_prompt: str = "",
        search_query: str = "",
        temperature: float = 0.5,
        max_tokens: int = 4096,
    ) -> str:
        """带联网搜索的对话调用

        Args:
            prompt: 发给模型的提示词（用于整理结果）
            system_prompt: 系统提示词
            search_query: 搜索关键词（简短，如果为空则用 prompt 作为搜索词）
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 搜索词：优先用 search_query，否则回退到 prompt
        actual_query = search_query if search_query else prompt

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[
                    {
                        "type": "web_search",
                        "web_search": {
                            "search_query": actual_query,
                            "search_result": True,
                        },
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"ZhipuAI web_search failed: {e}")
            raise

    def chat_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Any:
        """对话调用并解析 JSON 返回"""
        raw = self.chat(prompt, system_prompt, temperature, max_tokens)
        return self._extract_json(raw)

    def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
    ):
        """流式对话，逐 token 返回"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @staticmethod
    def _extract_json(text: str) -> Any:
        """从文本中提取 JSON —— 多策略容错"""
        if not text or not text.strip():
            raise ValueError("Empty response")

        text = text.strip()

        # 策略1: 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 策略2: 从 markdown 代码块中提取
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 策略3: 找到第一个 { 或 [ 到最后一个 } 或 ]
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end != -1 and end > start:
                candidate = text[start:end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # 策略4: 修复常见 JSON 格式问题后重试
                    try:
                        # 移除可能的尾部逗号
                        fixed = re.sub(r',\s*([}\]])', r'\1', candidate)
                        return json.loads(fixed)
                    except json.JSONDecodeError:
                        continue

        # 策略5: 逐行扫描，找包含 JSON 的行
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith(('{', '[')) and line.endswith(('}', ']')):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue

        raise ValueError(f"Cannot extract JSON from: {text[:200]}")

        raise ValueError(f"Cannot extract JSON from: {text[:200]}")


class _HttpZhipuClient:
    """zai-sdk 不可用时的 HTTP 回退实现"""

    def __init__(self, api_key: str, base_url: str):
        import httpx
        self.api_key = api_key
        self.base_url = base_url
        self.http = httpx.Client(timeout=120.0)

        # 模拟 zai-sdk 的接口结构
        self.chat = self._Chat(self)

    class _Chat:
        def __init__(self, parent):
            self.completions = parent._Completions(parent)

    class _Completions:
        def __init__(self, parent):
            self.parent = parent

        def create(self, model, messages, temperature=0.7, max_tokens=4096,
                   tools=None, tool_choice=None, stream=False, **kwargs):
            url = f"{self.parent.base_url}chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
            }
            if tools:
                payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

            headers = {
                "Authorization": f"Bearer {self.parent.api_key}",
                "Content-Type": "application/json",
            }

            resp = self.parent.http.post(url, json=payload, headers=headers)
            resp.raise_for_status()

            if stream:
                return self._stream_response(resp)
            else:
                data = resp.json()
                return _HttpZhipuClient._Response(data)

        def _stream_response(self, resp):
            # 简化的流式处理
            for line in resp.iter_lines():
                if line and line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    import json as _json
                    data = _json.loads(data_str)
                    yield _HttpZhipuClient._Response(data)

    class _Response:
        """模拟 zai-sdk 的响应对象"""
        def __init__(self, data):
            self._data = data
            self.choices = [
                _HttpZhipuClient._Choice(c) for c in data.get("choices", [])
            ]

    class _Choice:
        def __init__(self, data):
            self._data = data
            self.message = _HttpZhipuClient._Message(data.get("message", {}))
            self.delta = _HttpZhipuClient._Delta(data.get("delta", {}))

    class _Message:
        def __init__(self, data):
            self.content = data.get("content", "")
            self.tool_calls = data.get("tool_calls")

    class _Delta:
        def __init__(self, data):
            self.content = data.get("content")
            self.reasoning_content = data.get("reasoning_content")
