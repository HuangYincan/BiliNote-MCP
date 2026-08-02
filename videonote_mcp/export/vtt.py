"""WebVTT 字幕渲染器（纯函数，零依赖）。

输入 `TranscriptSegment(start, end, text)` 列表，输出标准 WebVTT (.vtt) 文本：
  WEBVTT

  00:00:00.000 --> 00:00:03.500
  你好，世界
"""
from typing import List, Union

from app.models.transcriber_model import TranscriptSegment


def _ts(seconds: float) -> str:
    """秒 → VTT 时间戳 `HH:MM:SS.mmm`（毫秒三位，向下取整，负值归零）。"""
    s = max(0.0, float(seconds))
    h = int(s // 3600)
    m = int(s % 3600 // 60)
    sec = int(s % 60)
    ms = int(round((s - int(s)) * 1000))
    if ms == 1000:  # 进位边界：.9999 会 round 到 1000
        ms = 0
        sec += 1
        if sec == 60:
            sec = 0
            m += 1
            if m == 60:
                m = 0
                h += 1
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"


def to_vtt(segments: Union[List[TranscriptSegment], List[dict]]) -> str:
    """把段落列表渲染为 WebVTT 文本。兼容 TranscriptSegment 对象或 dict。

    文本内的 `-->` 会替换为全角箭头 `→` 以免破坏时间轴分隔符。
    """
    lines = ["WEBVTT", ""]
    if not segments:
        return "WEBVTT\n\n"
    for seg in segments:
        if isinstance(seg, dict):
            start, end, text = seg.get("start", 0), seg.get("end", 0), seg.get("text", "")
        else:
            start, end, text = seg.start, seg.end, seg.text
        safe = (text or "").replace("-->", "→")
        lines.append(f"{_ts(start)} --> {_ts(end)}")
        lines.append(safe)
        lines.append("")
    return "\n".join(lines)
