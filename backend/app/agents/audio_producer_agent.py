"""Audio Producer Agent —— 音频制作 Agent

解析文案，按说话人分段，调用 Boson API 生成音频，拼接为完整播客。
注意: 此 Agent 不调用智谱AI，音频生成只使用 Boson API。
"""

import logging
import asyncio
import re
from typing import Any, Optional
from pathlib import Path
from app.harness.base_agent import BaseAgent
from app.harness.logger import AgentLogger, Timer
from app.tools.boson_client import tts_client
from app.tools.audio_utils import concat_audio_mp3, get_mp3_duration, cleanup_segments
from app.config import settings

logger = logging.getLogger(__name__)


class AudioProducerAgent(BaseAgent):
    name = "audio_producer_agent"

    # 说话人到 voice 的映射 (CosyVoice 音色)
    VOICE_MAP = {
        "MARCUS": settings.MALE_VOICE,   # longanyang 龙安洋
        "CHLOE": settings.FEMALE_VOICE,  # longanhuan 龙安欢
    }

    def __init__(self, task_id: Optional[str] = None):
        super().__init__(task_id)

    async def run(self, script: str = None, lang: str = "zh", date_str: str = None, **kwargs) -> dict:
        """生成播客音频"""
        if not script:
            return {"error": "no script"}

        timer = Timer()
        timer.__enter__()

        try:
            # Step 1: 解析文案为分段
            segments = self._parse_script(script)
            logger.info(f"Parsed {len(segments)} segments for {lang} audio")

            if not segments:
                raise ValueError("No segments parsed from script")

            # Step 2: 为每段生成音频（超长段落自动切分）
            podcast_dir = settings.PODCAST_DIR / date_str if date_str else settings.PODCAST_DIR / "temp"
            podcast_dir.mkdir(parents=True, exist_ok=True)
            segment_dir = podcast_dir / f"segments_{lang}"
            segment_dir.mkdir(parents=True, exist_ok=True)

            MAX_TEXT_LEN = 200  # CosyVoice 单次请求文本上限（SSML 标签也占字符，留余量）
            audio_segments = []
            failed_segments = []
            for i, seg in enumerate(segments):
                voice = self.VOICE_MAP.get(seg["speaker"], settings.FEMALE_VOICE)
                text = seg["text"]

                # 剥离外层 <speak></speak> 标签后再切分，切分后每段重新包裹
                # 避免切分破坏 SSML 标签结构导致 413 错误
                has_speak_wrap = text.strip().startswith("<speak>") and text.strip().endswith("</speak>")
                if has_speak_wrap:
                    inner_text = text.strip()[7:-8].strip()
                else:
                    inner_text = text

                sub_texts = self._split_long_text(inner_text, MAX_TEXT_LEN)

                # 重新包裹 <speak></speak>
                if has_speak_wrap:
                    sub_texts = [f"<speak>{t}</speak>" for t in sub_texts]
                sub_paths = []
                success = True

                for j, sub_text in enumerate(sub_texts):
                    sub_path = segment_dir / f"segment_{i:04d}_{j:02d}.mp3"
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda t=sub_text, v=voice, p=sub_path: tts_client.synthesize_segment(t, v, p)
                        )
                        sub_paths.append(sub_path)
                    except Exception as e:
                        logger.error(f"Segment {i+1} (part {j+1}) TTS failed: {e}")
                        success = False
                        break
                    await asyncio.sleep(1)

                if success and sub_paths:
                    audio_segments.extend(sub_paths)
                    logger.info(f"Segment {i+1}/{len(segments)} generated: {seg['speaker']} ({len(sub_texts)} parts) -> {sub_paths[0].name}")
                else:
                    failed_segments.append(i)

            if not audio_segments:
                raise ValueError("No audio segments generated successfully")

            # Step 3: 拼接音频
            output_path = podcast_dir / f"audio_{lang}.mp3"
            await asyncio.get_event_loop().run_in_executor(
                None, concat_audio_mp3, audio_segments, output_path
            )

            # Step 4: 获取时长
            duration = await asyncio.get_event_loop().run_in_executor(
                None, get_mp3_duration, output_path
            )

            # Step 5: 清理临时分段文件
            await asyncio.get_event_loop().run_in_executor(
                None, cleanup_segments, segment_dir
            )

            timer.__exit__()
            result = {
                "audio_path": str(output_path),
                "duration": duration,
                "segments_total": len(segments),
                "segments_success": len(audio_segments),
                "segments_failed": len(failed_segments),
                "failed_indices": failed_segments,
                "lang": lang,
            }
            AgentLogger.log(
                self.name, f"produce_{lang}",
                {"script_len": len(script), "segments": len(segments)},
                result,
                tools_used=["boson_tts", "concat_audio"],
                duration_ms=timer.elapsed_ms,
                task_id=self.task_id
            )
            return result

        except Exception as e:
            timer.__exit__()
            AgentLogger.log(
                self.name, f"produce_{lang}",
                {"script_len": len(script) if script else 0},
                None, status="failed", error=str(e),
                duration_ms=timer.elapsed_ms, task_id=self.task_id
            )
            raise

    def _parse_script(self, script: str) -> list[dict]:
        """
        解析播客文案为分段列表 —— 支持多种格式变体

        支持的格式:
        - [MARCUS]: 文本
        - [Marcus]: 文本
        - **MARCUS:** 文本
        - MARCUS: 文本
        - <speak>包裹的文本也算
        """
        segments = []
        lines = script.strip().split("\n")

        current_speaker = None
        current_text = []

        # 多种说话人标识的正则
        speaker_patterns = [
            r'^\[([A-Za-z]+)\]:\s*(.*)',        # [MARCUS]: 或 [Marcus]:
            r'^\*\*([A-Za-z]+)\*\*:\s*(.*)',     # **MARCUS**:
            r'^([A-Z]{3,}):\s*(.*)',             # MARCUS: (全大写至少3字符)
        ]

        def match_speaker(line):
            for pattern in speaker_patterns:
                m = re.match(pattern, line)
                if m:
                    speaker = m.group(1).upper()
                    # 只接受已知的说话人
                    if speaker in self.VOICE_MAP:
                        return speaker, m.group(2).strip()
            return None, None

        for line in lines:
            line = line.strip()
            if not line:
                if current_text and current_speaker:
                    segments.append({
                        "speaker": current_speaker,
                        "text": " ".join(current_text).strip()
                    })
                    current_text = []
                continue

            speaker, text = match_speaker(line)
            if speaker:
                # 保存前一段
                if current_text and current_speaker:
                    segments.append({
                        "speaker": current_speaker,
                        "text": " ".join(current_text).strip()
                    })
                current_speaker = speaker
                if text:
                    current_text = [text]
            else:
                # 继续当前说话人的文本
                if current_speaker:
                    current_text.append(line)

        # 保存最后一段
        if current_text and current_speaker:
            segments.append({
                "speaker": current_speaker,
                "text": " ".join(current_text).strip()
            })

        # 过滤空文本
        segments = [s for s in segments if s["text"]]

        if len(segments) == 0:
            logger.warning(f"Parsed 0 segments! Script preview (first 500 chars): {script[:500]}")

        return segments

    def _split_long_text(self, text: str, max_len: int = 300) -> list[str]:
        """将过长文本切分为多段，尽量在标点处断开"""
        if len(text) <= max_len:
            return [text]

        parts = []
        # 按句号/问号/感叹号/分号切分
        import re
        sentences = re.split(r'(?<=[。！？；!?;])', text)

        current = ""
        for sent in sentences:
            if not sent:
                continue
            if len(current) + len(sent) <= max_len:
                current += sent
            else:
                if current:
                    parts.append(current)
                # 单句就超长，硬切
                while len(sent) > max_len:
                    parts.append(sent[:max_len])
                    sent = sent[max_len:]
                current = sent

        if current:
            parts.append(current)

        return parts
