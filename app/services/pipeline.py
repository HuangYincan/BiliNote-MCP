"""pipeline.py —— BiliNote 流水线独立步骤层。

把 NoteGenerator.generate() 的整体编排拆成**可独立调用**的无状态步骤函数。
每个函数一个职责、输入输出明确；MCP 工具层与 generate() 共用同一套实现，支持任意组合：

  - `fetch_subtitles`      : 只取平台字幕（不下载、不转写）
  - `transcribe_audio`     : 只做语音识别（ASR，给定音频/视频文件）
  - `extract_frames`       : 只抽视频关键帧（画面理解素材，给定本地 mp4）
  - `fetch_comments_danmaku`: 只抓 B 站弹幕 + 评论区观点
  - `summarize_material`   : 只做 LLM 总结（吃素材包，给定转写/帧/评论）

步骤间用「素材包」material dict 传递（与 note.py._build_note_material 一致）：
  `{title, transcript, frames[file://...], comments_danmaku, video_path, audio_path}`

安全纪律：只读不写（除 extract_frames 持久化帧到 save_dir）；不碰状态机/缓存/DB，
那些属于编排层（generate）的职责。
"""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Union

from app.downloaders.base import Downloader
from app.gpt.base import GPT
from app.gpt.gpt_factory import GPTFactory
from app.models.gpt_model import GPTSource
from app.models.model_config import ModelConfig
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.constant import SUPPORT_PLATFORM_MAP
from app.services.provider import ProviderService
from app.transcriber.base import Transcriber
from app.transcriber.transcriber_provider import _transcribers, get_transcriber
from app.utils.video_reader import VideoReader

logger = logging.getLogger(__name__)

NOTE_OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))

_PLATFORM_HINTS = [
    ("bilibili", ("bilibili.com", "b23.tv")),
    ("youtube", ("youtube.com", "youtu.be")),
    ("douyin", ("douyin.com",)),
    ("tiktok", ("tiktok.com",)),
    ("kuaishou", ("kuaishou.com", "gifshow.com")),
]


# ---------------- 平台 / 引擎 ----------------

def detect_platform(url: str) -> str:
    """从 URL / 本地路径识别平台（与 server._detect_platform 一致）。"""
    u = (url or "").strip().lower()
    if not u:
        raise ValueError("url 为空")
    if u.startswith(("file:", "/", "./", "../", "~/")) or Path(u).expanduser().exists():
        return "local"
    for platform, needles in _PLATFORM_HINTS:
        if any(n in u for n in needles):
            return platform
    raise ValueError(
        f"无法识别视频平台: {url[:80]}（支持 bilibili / youtube / douyin / tiktok / kuaishou / 本地文件路径）"
    )


def get_downloader(platform: str) -> Downloader:
    """按平台取下载器实例。"""
    d = SUPPORT_PLATFORM_MAP.get(platform)
    if d is None:
        raise ValueError(f"不支持的平台：{platform}")
    return d


def build_transcriber() -> Transcriber:
    """按当前转写器配置实例化转写器（与 note.py._init_transcriber 一致）。"""
    from app.services.transcriber_config_manager import TranscriberConfigManager

    ttype = TranscriberConfigManager().get_transcriber_type()
    if ttype not in _transcribers:
        raise ValueError(f"不支持的转写器：{ttype}")
    return get_transcriber(transcriber_type=ttype)


def get_gpt(provider_id: str, model_name: Optional[str] = None) -> GPT:
    """按供应商 id 构建 GPT 实例（与 note.py._get_gpt 一致）。"""
    provider = ProviderService.get_provider_by_id(provider_id)
    if not provider:
        raise ValueError(f"未找到模型供应商: provider_id={provider_id}")
    config = ModelConfig(
        api_key=provider["api_key"],
        base_url=provider["base_url"],
        model_name=model_name,
        provider=provider["type"],
        name=provider["name"],
    )
    return GPTFactory().from_config(config)


# ---------------- 步骤 1：平台字幕 ----------------

def fetch_subtitles(video_url: str, platform: Optional[str] = None) -> Optional[dict]:
    """只取平台字幕（人工/自动字幕），不下载音视频、不转写。

    返回 TranscriptResult 的 asdict（{language, full_text, segments}）；无字幕/失败返回 None。
    """
    if platform is None:
        platform = detect_platform(video_url)
    try:
        tr = get_downloader(platform).download_subtitles(video_url)
        if tr and getattr(tr, "segments", None):
            return asdict(tr)
    except Exception as exc:  # noqa: BLE001 —— 字幕失败不阻断
        logger.warning(f"获取平台字幕失败 platform={platform}: {exc}")
    return None


# ---------------- 步骤 2：语音识别（ASR） ----------------

def transcribe_audio(audio_file: Union[str, Path], transcriber: Optional[Transcriber] = None) -> dict:
    """只做语音识别：给定音频/视频文件 → 转写结果 asdict（{language, full_text, segments}）。

    不配置 transcriber 时按当前转写器配置构建。
    """
    audio_file = str(audio_file)
    if not Path(audio_file).exists():
        raise FileNotFoundError(f"音频/视频文件不存在: {audio_file}")
    if transcriber is None:
        transcriber = build_transcriber()
    tr = transcriber.transcript(file_path=audio_file)
    return asdict(tr)


# ---------------- 步骤 3：视频关键帧抽取（画面理解素材） ----------------

def extract_frames(
    video_path: Union[str, Path],
    video_interval: int = 6,
    grid_size: Optional[List[int]] = None,
    save_dir: Optional[Union[str, Path]] = None,
) -> List[str]:
    """只做视频画面理解素材：给定本地 mp4 → 按间隔抽帧并持久化。

    返回持久化后的帧图片 **file:// 绝对路径** 列表（供多模态模型 Read / 喂给 summarize_material）。
    save_dir 缺省为 note_results/frames_<视频名>/。
    """
    video_path = str(video_path)
    if not Path(video_path).exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")
    grid = tuple(grid_size) if grid_size else (3, 3)
    reader = VideoReader(
        video_path=video_path,
        grid_size=grid,
        frame_interval=int(video_interval) or 6,
        unit_width=960,
        unit_height=540,
        save_quality=80,
    )
    data_uris = reader.run()

    if save_dir is None:
        save_dir = NOTE_OUTPUT_DIR / f"frames_{Path(video_path).stem}"
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    frames: List[str] = []
    for i, data_uri in enumerate(data_uris, start=1):
        try:
            if isinstance(data_uri, str) and data_uri.startswith("data:image"):
                b64 = data_uri.split(",", 1)[1]
                p = save_dir / f"frame_{i}.jpg"
                p.write_bytes(base64.b64decode(b64))
                frames.append(p.as_uri())
            else:
                logger.warning(f"跳过非 data URI 帧 (index={i}): {str(data_uri)[:60]}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"帧 {i} 落盘失败，跳过: {exc}")
    return frames


# ---------------- 步骤 4：弹幕 + 评论区观点 ----------------

def fetch_comments_danmaku(video_url: str, comments_limit: int = 20) -> Optional[str]:
    """抓取 B 站弹幕汇总 + 热门评论，拼成一段提示词文本（失败返回 None，不阻断）。

    与 fetch_comments / fetch_danmaku 两个独立工具同源（BilibiliCommentFetcher），
    这里是「拼接成一段」的聚合版，供 summarize_material / generate 直接注入。
    """
    try:
        from app.downloaders.bilibili_comment import BilibiliCommentFetcher

        fetcher = BilibiliCommentFetcher()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"BilibiliCommentFetcher 不可用，跳过弹幕/评论抓取: {exc}")
        return None

    parts: List[str] = []

    danmaku = fetcher.fetch_danmaku(str(video_url))
    if danmaku.get("ok"):
        summary = danmaku.get("danmaku_summary") or ""
        if summary:
            parts.append(f"【弹幕】\n{summary}")
    else:
        logger.warning(f"弹幕抓取失败，跳过: {danmaku.get('error')}")

    comments = fetcher.fetch_comments(str(video_url), limit=comments_limit)
    if comments.get("ok"):
        rows = comments.get("comments") or []
        if rows:
            lines = [
                f"- {c.get('user', '')}({c.get('likes', 0)}赞): {c.get('content', '')}"
                for c in rows
            ]
            parts.append("【热门评论】\n" + "\n".join(lines))
    else:
        logger.warning(f"评论抓取失败，跳过: {comments.get('error')}")

    if not parts:
        return None
    return "\n\n".join(parts)


# ---------------- 步骤 5：LLM 总结（吃素材包） ----------------

def _frames_to_data_uris(frames: Optional[List[str]]) -> List[str]:
    """把素材包里的 file:// 帧路径转成 base64 data URI（GPTSource.video_img_urls 用）。"""
    if not frames:
        return []
    uris: List[str] = []
    for f in frames:
        try:
            p = Path(f)
            if str(f).startswith("file://"):
                from urllib.parse import urlparse

                p = Path(urlparse(str(f)).path)
            if not p.exists():
                logger.warning(f"帧文件不存在，跳过: {f}")
                continue
            b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
            uris.append(f"data:image/jpeg;base64,{b64}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"帧转 base64 失败，跳过: {f}: {exc}")
    return uris


def summarize_material(
    material: dict,
    gpt: GPT,
    style: Optional[str] = None,
    extras: Optional[str] = None,
    formats: Optional[List[str]] = None,
    screenshot: bool = False,
    link: bool = False,
    tags: Optional[List] = None,
    checkpoint_key: Optional[str] = None,
    cancel_event=None,
) -> str:
    """只做 LLM 总结：给定素材包（转写/帧/评论）+ GPT 实例 → 返回 Markdown。

    不写缓存、不写库、不更新状态 —— 那些是编排层（generate）的职责。
    素材包缺字段时安全兜底（title 空、无帧、无评论都可用）。tags 透传给 GPTSource
    （generate() 重构时传 audio_meta.raw_info.get("tags", []) 保持行为一致）。
    """
    transcript = material.get("transcript") or {}
    segments: List = transcript.get("segments") or []
    seg_objs: List[TranscriptSegment] = []
    for s in segments:
        seg_objs.append(s if isinstance(s, TranscriptSegment) else TranscriptSegment(**s))

    source = GPTSource(
        title=material.get("title") or "",
        segment=seg_objs,
        tags=tags or [],
        screenshot=screenshot,
        video_img_urls=_frames_to_data_uris(material.get("frames")),
        comments_danmaku=material.get("comments_danmaku"),
        link=link,
        _format=formats or [],
        style=style,
        extras=extras,
        checkpoint_key=checkpoint_key,
    )
    return gpt.summarize(source, cancel_event=cancel_event)
