from dataclasses import dataclass
from typing import Optional

from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult


@dataclass
class NoteResult:
    markdown: str                  # GPT 总结的 Markdown 内容
    transcript: TranscriptResult                # Whisper 转写结果
    audio_meta: AudioDownloadResult  # 音频下载的元信息（title、duration、封面等）
    note_dir: Optional[str] = None  # 便携笔记实际写入目录（含 note.md，截图另有 Assets/），未写文件时 None
    material: Optional[dict] = None  # material_only 模式下的素材包（title/transcript/frames/comments/音视频路径），不走 LLM 总结时填充