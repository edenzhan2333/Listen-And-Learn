"""CosyVoice TTS 客户端封装 —— 项目中唯一的音频生成入口

使用阿里云 DashScope SDK 调用 CosyVoice 模型
模型: cosyvoice-v3.5-plus
音色: longanyang(男) / longanhuan(女)
支持 SSML 标签控制语速/音高/音量/停顿
内置自动重试机制
"""

import logging
import re
import time
from pathlib import Path
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 3

# CosyVoice 支持的标准 SSML 标签白名单
_VALID_SSML_TAGS = re.compile(r'</?(speak|break|prosody|voice|emphasis|p|s|phoneme|say-as|sub)\b[^>]*/?>', re.IGNORECASE)


def _sanitize_tts_text(text: str) -> str:
    """清洗 TTS 文本：移除所有非标准 SSML 标签。

    CosyVoice 只支持标准 SSML 标签，GLM 有时会生成 <|emotion:xxx|> 之类的
    非标准标签，会导致 "SSML text is illegal" 错误。此函数作为兜底清洗。
    """
    # 移除所有 <|...|> 格式的标签（GLM 的 emotion/instruction 标签）
    text = re.sub(r'<\|[^|]*\|>', '', text)
    # 移除 think 模式的 think 标签（如果泄漏到 content 中）
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'</?think>', '', text)
    # 移除白名单以外的所有 <xxx> 标签
    # 先保护合法标签，移除所有 <...>，再恢复合法标签
    placeholders = {}
    def _save_valid(m):
        key = f"\x00VALID_TAG_{len(placeholders)}\x00"
        placeholders[key] = m.group(0)
        return key
    text = _VALID_SSML_TAGS.sub(_save_valid, text)
    text = re.sub(r'<[^>]+>', '', text)
    for key, val in placeholders.items():
        text = text.replace(key, val)
    return text


class CosyVoiceTTSClient:
    """CosyVoice TTS 客户端 —— 带自动重试"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        self.model = settings.TTS_MODEL

    def synthesize(
        self,
        text: str,
        voice: str = "longanhuan",
        save_path: Optional[Path] = None,
        instruction: str = None,
    ) -> bytes:
        """
        调用 CosyVoice TTS API 合成音频

        Args:
            text: 要合成的文本（可包含 SSML 标签）
            voice: 音色 (longanyang/longanhuan 等)
            save_path: 保存路径
            instruction: 情感指令

        Returns:
            音频二进制数据 (mp3)
        """
        # 兜底清洗：移除非标准 SSML 标签，防止 "SSML text is illegal"
        text = _sanitize_tts_text(text)

        # 先尝试带 SSML 标签合成
        try:
            return self._synthesize_with_retry(text, voice, save_path, instruction, use_ssml=True)
        except Exception as ssml_error:
            # SSML 模式全部失败 → 降级为纯文本模式（移除所有标签）
            if "<speak>" in text or "<break" in text:
                logger.warning(f"SSML TTS failed, falling back to plain text: {ssml_error}")
                plain_text = _VALID_SSML_TAGS.sub('', text)  # 移除所有SSML标签
                plain_text = re.sub(r'<[^>]+>', '', plain_text).strip()
                if plain_text:
                    return self._synthesize_with_retry(plain_text, voice, save_path, instruction, use_ssml=False)
            raise

    def _synthesize_with_retry(
        self,
        text: str,
        voice: str,
        save_path: Optional[Path],
        instruction: str,
        use_ssml: bool = True,
    ) -> bytes:
        """内部方法：带重试的 TTS 合成"""
        logger.info(f"CosyVoice TTS: voice={voice}, text_len={len(text)}, "
                     f"ssml={use_ssml}, text_preview={text[:80]}...")

        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                from dashscope.audio.http_tts.http_speech_synthesizer import HttpSpeechSynthesizer

                kwargs = {
                    "model": self.model,
                    "text": text,
                    "voice": voice,
                    "format": "mp3",
                    "sample_rate": 24000,
                    "stream": False,
                    "api_key": self.api_key,
                }

                if instruction:
                    kwargs["instruction"] = instruction

                if use_ssml and ("<speak>" in text or "<break" in text):
                    kwargs["enable_ssml"] = True

                result = HttpSpeechSynthesizer.call(**kwargs)

                # 检查是否有错误
                if hasattr(result, 'status_code') and result.status_code != 200:
                    error_msg = getattr(result, 'message', '') or str(result)
                    logger.error(f"CosyVoice API error: status={result.status_code}, msg={error_msg}, text_preview={text[:100]}")
                    raise Exception(f"CosyVoice API error {result.status_code}: {error_msg}")

                if hasattr(result, 'audio_url') and result.audio_url:
                    audio_data = self._download_audio(result.audio_url)
                elif hasattr(result, 'output') and result.output:
                    audio_data = result.output
                else:
                    raise Exception(f"Unexpected result format: {result}")

                if save_path and audio_data:
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(save_path, "wb") as f:
                        f.write(audio_data)
                    logger.info(f"Audio saved to {save_path} ({len(audio_data)} bytes)")

                return audio_data

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"CosyVoice TTS error, attempt {attempt}/{MAX_RETRIES} (ssml={use_ssml}): {e}"
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)

        raise Exception(f"CosyVoice TTS failed after {MAX_RETRIES} attempts (ssml={use_ssml}). Last error: {last_error}")

    def _download_audio(self, url: str) -> bytes:
        """下载音频 URL"""
        import requests
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return response.content

    def synthesize_segment(
        self,
        text: str,
        voice: str,
        save_path: Path,
        instruction: str = None,
    ) -> Path:
        """合成单段音频并保存，返回文件路径"""
        self.synthesize(text, voice, save_path=save_path, instruction=instruction)
        return save_path


# 全局实例
tts_client = CosyVoiceTTSClient()
