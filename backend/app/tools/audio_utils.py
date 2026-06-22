"""音频工具 —— 播客音频拼接和时长计算"""

import logging
import subprocess
from pathlib import Path
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)


def concat_audio_mp3(segments: List[Path], output_path: Path) -> Path:
    """
    拼接多个 MP3 文件为一个完整音频

    使用 ffmpeg 进行无损拼接（copy codec）。
    如果 ffmpeg 不可用，回退到 pydub。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 方法1: 使用 ffmpeg concat
    try:
        # 创建文件列表
        list_file = output_path.parent / "concat_list.txt"
        with open(list_file, "w") as f:
            for seg in segments:
                f.write(f"file '{seg.absolute()}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0:
            list_file.unlink(missing_ok=True)
            logger.info(f"Audio concatenated (ffmpeg): {len(segments)} segments -> {output_path}")
            return output_path
        else:
            logger.warning(f"ffmpeg concat failed, trying pydub: {result.stderr.decode()[:200]}")
    except FileNotFoundError:
        logger.warning("ffmpeg not found, falling back to pydub")
    except Exception as e:
        logger.warning(f"ffmpeg concat error: {e}, falling back to pydub")

    # 方法2: 使用 pydub 回退
    try:
        from pydub import AudioSegment
        combined = AudioSegment.empty()
        for seg in segments:
            audio = AudioSegment.from_mp3(str(seg))
            combined += audio
        combined.export(str(output_path), format="mp3")
        logger.info(f"Audio concatenated (pydub): {len(segments)} segments -> {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"pydub concat also failed: {e}")
        # 方法3: 简单的二进制拼接（MP3 可以直接拼接）
        with open(output_path, "wb") as out_f:
            for seg in segments:
                with open(seg, "rb") as in_f:
                    out_f.write(in_f.read())
        logger.info(f"Audio concatenated (binary): {len(segments)} segments -> {output_path}")
        return output_path


def get_mp3_duration(file_path: Path) -> int:
    """获取 MP3 文件时长（秒）"""
    try:
        # 尝试使用 ffprobe
        cmd = [
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0:
            return int(float(result.stdout.decode().strip()))
    except Exception:
        pass

    try:
        # 回退到 pydub
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(str(file_path))
        return int(len(audio) / 1000)
    except Exception:
        # 最终回退：估算（MP3 128kbps ≈ 1MB/分钟）
        file_size = file_path.stat().st_size
        return int(file_size / (128 * 1024 / 8))


def cleanup_segments(segment_dir: Path):
    """清理临时分段音频文件"""
    for f in segment_dir.glob("segment_*.mp3"):
        f.unlink(missing_ok=True)
    list_file = segment_dir / "concat_list.txt"
    list_file.unlink(missing_ok=True)
