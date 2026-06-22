"""Script Writer Agent —— 播客文案 Agent

基于新闻+知识库上下文，生成双主持人对谈文案（中/英），嵌入TTS标签。
英文文案翻译后与原新闻核对，确保专有名词翻译准确。
"""

import logging
import asyncio
import re
from typing import Any, Optional
from datetime import datetime
from pathlib import Path
from app.harness.base_agent import BaseAgent
from app.harness.logger import AgentLogger, Timer
from app.tools.zhipu_client import ZhipuClient
from app.config import settings

logger = logging.getLogger(__name__)


class ScriptWriterAgent(BaseAgent):
    name = "script_writer_agent"

    def __init__(self, task_id: Optional[str] = None):
        super().__init__(task_id)
        self.zhipu = ZhipuClient()

    async def run(self, news_items: list[dict] = None, date_str: str = None, **kwargs) -> dict:
        """生成中英文播客文案"""
        if not news_items:
            logger.error("No news items, cannot generate script")
            raise ValueError("no news items")

        logger.info(f"Generating script for {len(news_items)} news items on {date_str}")

        # Step 1: 生成中文文案
        timer = Timer()
        timer.__enter__()
        try:
            script_zh = await self._generate_chinese_script(news_items, date_str)
            # 清洗文案：过滤掉 GLM 的思考过程，只保留对谈内容
            script_zh = self._clean_script(script_zh)
            if not script_zh or len(script_zh) < 100:
                logger.warning(f"Chinese script too short ({len(script_zh)} chars), retrying...")
                script_zh = await self._generate_chinese_script(news_items, date_str)
                script_zh = self._clean_script(script_zh)
            if not script_zh or len(script_zh) < 100:
                raise ValueError(f"Chinese script generation returned empty or too short: {len(script_zh)} chars")
        except Exception as e:
            timer.__exit__()
            logger.error(f"Chinese script generation failed: {e}")
            AgentLogger.log(self.name, "generate_zh", {"date": date_str}, None,
                          status="failed", error=str(e), task_id=self.task_id)
            raise
        timer.__exit__()
        logger.info(f"Chinese script generated: {len(script_zh)} chars")
        AgentLogger.log(self.name, "generate_zh",
                       {"date": date_str, "news_count": len(news_items)},
                       {"script_len": len(script_zh)},
                       tools_used=["zhipu_chat"], task_id=self.task_id)

        # Step 2: 翻译为英文
        timer = Timer()
        timer.__enter__()
        try:
            script_en = await self._translate_to_english(script_zh)
            script_en = self._clean_script(script_en)
            if not script_en or len(script_en) < 100:
                logger.warning(f"English script too short ({len(script_en)} chars), retrying...")
                script_en = await self._translate_to_english(script_zh)
                script_en = self._clean_script(script_en)
            if not script_en or len(script_en) < 100:
                raise ValueError(f"English translation returned empty or too short: {len(script_en)} chars")
        except Exception as e:
            timer.__exit__()
            logger.error(f"English translation failed: {e}")
            AgentLogger.log(self.name, "translate_en", {"date": date_str}, None,
                          status="failed", error=str(e), task_id=self.task_id)
            raise
        timer.__exit__()
        logger.info(f"English script generated: {len(script_en)} chars")
        AgentLogger.log(self.name, "translate_en",
                       {"zh_len": len(script_zh)}, {"en_len": len(script_en)},
                       tools_used=["zhipu_chat"], task_id=self.task_id)

        # Step 3: 英文核对 —— 与原新闻对照，修正专有名词
        timer = Timer()
        timer.__enter__()
        try:
            script_en = await self._verify_english(script_en, news_items)
            script_en = self._clean_script(script_en)
        except Exception as e:
            timer.__exit__()
            logger.error(f"English verification failed: {e}")
            # 核对失败不阻塞流程，使用未核对的版本
        timer.__exit__()
        AgentLogger.log(self.name, "verify_en",
                       {"news_count": len(news_items)}, {"en_len": len(script_en)},
                       tools_used=["zhipu_chat"], task_id=self.task_id)

        # Step 4: 保存文案
        podcast_dir = settings.PODCAST_DIR / date_str
        podcast_dir.mkdir(parents=True, exist_ok=True)
        script_zh_path = podcast_dir / "script_zh.md"
        script_en_path = podcast_dir / "script_en.md"
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: script_zh_path.write_text(script_zh, encoding="utf-8")
        )
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: script_en_path.write_text(script_en, encoding="utf-8")
        )

        return {
            "script_zh": script_zh,
            "script_en": script_en,
            "script_zh_path": str(script_zh_path),
            "script_en_path": str(script_en_path),
        }

    async def _generate_chinese_script(self, news_items: list[dict], date_str: str) -> str:
        """生成中文播客文案"""
        # 构建新闻素材摘要
        news_summary = self._format_news_for_prompt(news_items)

        system_prompt = self.get_prompt()
        prompt = f"""请基于以下AI领域新闻素材，生成一份约10分钟的播客对谈文案（中文）。

日期: {date_str}
新闻素材:

{news_summary}

要求:
1. 双主持人对谈格式: [MARCUS] 和 [CHLOE] 交替发言
2. 总字数约 2000 字左右（字数不强求，约10分钟）
3. 覆盖最重要的AI新闻
4. 每条新闻有简要介绍和评论
5. 对谈自然流畅，有互动感
6. 合理使用SSML标签让播客生动:
   - 停顿: <break time="500ms"/> 或 <break time="1s"/>
   - 语速控制: <speak rate="1.2">加快语速的文本</speak>
7. 每个说话人的台词用 <speak></speak> 标签包裹
8. 开头要有欢迎语，结尾要有总结和告别
9. 每行一个说话人，格式: [MARCUS]: <speak>文本内容<break time="500ms"/>更多文本</speak>
10. 只能使用 <speak>、<break>、</speak> 三种 SSML 标签
11. 严禁使用 <|emotion:xxx|>、<|...|> 等任何非标准标签，这些会导致 TTS 失败

SSML标签示例:
[MARCUS]: <speak>欢迎收听 Listen and Learn！<break time="500ms"/>今天我们来聊聊昨天AI圈的大事。</speak>
[CHLOE]: <speak>哈哈，我已经迫不及待了！<break time="300ms"/>先从最重要的新闻开始吧。</speak>

直接输出文案，不要其他说明。只输出一版最终文案，不要输出多个版本或反复修改。"""

        response = self.zhipu.chat(
            prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=8192
        )
        return response.strip()

    async def _translate_to_english(self, script_zh: str) -> str:
        """将中文文案翻译为英文"""
        prompt = f"""请将以下中文播客文案翻译为英文。

要求:
1. 保持内容完全一致
2. 保持 [MARCUS] 和 [CHLOE] 的说话人轮次不变
3. 保留所有 SSML 标签（<speak>、<break> 等）的位置和格式不变
4. 翻译要自然流畅，适合英语播客
5. 专有名词（公司名、产品名等）暂时按字面翻译，后续会核对修正
6. 直接输出英文文案，不要其他说明

中文文案:

{script_zh}"""

        response = self.zhipu.chat(
            prompt,
            system_prompt="你是专业的中英翻译专家，擅长播客文案翻译。",
            temperature=0.3,
            max_tokens=8192
        )
        return response.strip()

    async def _verify_english(self, script_en: str, news_items: list[dict]) -> str:
        """英文核对 —— 与原新闻对照，修正专有名词翻译"""
        # 收集原始英文标题和来源URL作为参考
        references = []
        for item in news_items:
            if item.get("title_en") or item.get("source_url"):
                references.append(
                    f"- 中文标题: {item.get('title_zh', '')}\n"
                    f"  英文原标题: {item.get('title_en', 'N/A')}\n"
                    f"  来源: {item.get('source_url', 'N/A')}"
                )
        references_text = "\n".join(references)

        prompt = f"""请核对以下英文播客文案中的专有名词翻译是否准确。

参考信息（原始新闻标题和来源）:
{references_text}

英文文案:
{script_en}

核对要求:
1. 公司名必须使用官方英文名（如 OpenAI, Google, Microsoft, Tesla, ByteDance）
2. 产品名必须使用官方英文名（如 ChatGPT, Gemini, Claude, GPT-6）
3. 技术术语使用通用英文表达（如 大语言模型→Large Language Model/LLM）
4. 人名使用英文原名
5. 不要改变文案结构、说话人轮次和TTS标签
6. 只修正专有名词相关的翻译，不改变其他内容

请直接输出修正后的完整英文文案，不要其他说明。"""

        response = self.zhipu.chat(
            prompt,
            system_prompt="你是专业的英文校对专家，擅长科技新闻领域的专有名词核对。",
            temperature=0.2,
            max_tokens=8192
        )
        return response.strip()

    def _clean_script(self, script: str) -> str:
        """清洗文案：过滤思考过程、多版本重复，只保留最终版对谈内容"""
        if not script:
            return ""

        lines = script.strip().split("\n")

        # 版本分隔词：遇到这些词说明 GLM 在输出新版本，清空之前的积累
        version_separator = re.compile(
            r'^(让我重新|重新写|再优化|重新优化|修改后|另一个版本|第二个版本|版本[2-9二三四五]|'
            r'重写一遍|调整后|改进版|修改一下|再来一版|最终版|以下是最终|这是修改后)',
            re.IGNORECASE
        )

        # 只保留以说话人标记开头的行及其续行
        speaker_pattern = re.compile(r'^\[?(MARCUS|CHLOE|Marcus|Chloe)\]?\s*[:：]\s*(.*)', re.IGNORECASE)

        cleaned_lines = []
        in_speaker_line = False

        for line in lines:
            line_stripped = line.strip()

            # 检测版本分隔词：清空已积累的行，只保留最后一个版本
            if version_separator.match(line_stripped):
                if cleaned_lines:
                    logger.info(f"Detected version separator, discarding {len(cleaned_lines)} previous lines: {line_stripped[:50]}")
                    cleaned_lines = []
                in_speaker_line = False
                continue

            # 匹配说话人行
            match = speaker_pattern.match(line_stripped)
            if match:
                in_speaker_line = True
                speaker = match.group(1).upper()
                text = match.group(2)
                text = self._strip_non_ssml_tags(text)
                cleaned_lines.append(f"[{speaker}]: {text}")
            elif in_speaker_line and line_stripped:
                # 说话人行的续行
                if '<speak>' in line_stripped or '<break' in line_stripped or '</speak>' in line_stripped:
                    cleaned_lines.append(self._strip_non_ssml_tags(line_stripped))
                elif not line_stripped.startswith(('#', '##', '等等', '让我', '需要', '我需要', '首先', '接下来', '然后', '最后')):
                    if not re.match(r'^(好的|好的，|这是|根据|基于|为了|因为|所以|但是|不过|另外|此外)', line_stripped):
                        cleaned_lines.append(self._strip_non_ssml_tags(line_stripped))
            else:
                in_speaker_line = False

        result = "\n".join(cleaned_lines).strip()

        if len(result) < len(script) * 0.3:
            logger.warning(f"Cleaned script too short ({len(result)} vs {len(script)}), returning original")
            return self._strip_non_ssml_tags(script.strip())

        logger.info(f"Script cleaned: {len(script)} -> {len(result)} chars (removed {len(script) - len(result)})")
        return result

    @staticmethod
    def _strip_non_ssml_tags(text: str) -> str:
        """移除 GLM 生成的非标准 SSML 标签（如 <|emotion:xxx|>）

        CosyVoice 只支持标准 SSML: <speak> <break> <prosody>
        GLM 有时会自作主张加 <|emotion:contemplation|> 之类的标签，必须移除。
        """
        # 移除所有 <|...|> 格式的标签（GLM 的 emotion/instruction 标签）
        text = re.sub(r'<\|[^|]*\|>', '', text)
        # 移除 think 模式的 <think>...</think> 标签（如果泄漏到 content 中）
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # 移除孤立的 <think> 或 </think> 标签
        text = re.sub(r'</?think>', '', text)
        return text

    def _format_news_for_prompt(self, news_items: list[dict]) -> str:
        """将新闻素材格式化为 prompt 文本 —— 限制长度避免 prompt 过长"""
        lines = []
        for i, item in enumerate(news_items, 1):
            title = item.get('title_zh', '')[:100]
            summary = item.get('summary_zh', '')[:200]
            lines.append(f"{i}. {title}")
            lines.append(f"   摘要: {summary}")
            lines.append("")
        return "\n".join(lines)
