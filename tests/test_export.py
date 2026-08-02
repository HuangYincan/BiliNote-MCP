"""多格式导出 + 平台接手 handoff 的单元测试。

覆盖：
1. SRT / VTT / JSON 渲染：时间格式、`-->` 转义、多段、空 segments、毫秒进位；
2. exporter 落盘：临时目录、返回 file:// 路径、manifest 记录、未知格式忽略；
3. detect_platform / handoff_result：合法平台不变、未知 URL 返回 unsupported + handoff。

不碰真实网络 / 转写引擎 / LLM / DB。

运行：
    cd <repo>
    .venv/bin/python tests/test_export.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.transcriber_model import TranscriptSegment
from app.services import pipeline

from bilinote_mcp.export import export_transcript
from bilinote_mcp.export.json import to_json
from bilinote_mcp.export.srt import to_srt
from bilinote_mcp.export.vtt import to_vtt


def _segs():
    return [
        TranscriptSegment(start=0.0, end=3.5, text="你好，世界"),
        TranscriptSegment(start=3.5, end=6.75, text="Second line --> arrow"),
        TranscriptSegment(start=59.9999, end=61.0, text="进位测试"),
    ]


class SrtTest(unittest.TestCase):
    def test_basic_timestamps(self):
        out = to_srt([TranscriptSegment(0, 3.5, "hi")])
        self.assertIn("00:00:00,000 --> 00:00:03,500", out)
        self.assertIn("hi", out)

    def test_arrow_escaped(self):
        out = to_srt([TranscriptSegment(0, 1, "a --> b")])
        self.assertIn("a → b", out)
        self.assertNotIn("a --> b", out)

    def test_millisecond_carry(self):
        # 59.9999s 的毫秒进位 → 00:01:00,000
        out = to_srt(_segs())
        self.assertIn("00:01:00,000 --> 00:01:01,000", out)

    def test_empty_segments(self):
        self.assertEqual(to_srt([]), "")
        self.assertEqual(to_srt(None), "")

    def test_negative_seconds_clamped(self):
        out = to_srt([TranscriptSegment(-1.0, 0.5, "x")])
        self.assertIn("00:00:00,000", out)


class VttTest(unittest.TestCase):
    def test_header(self):
        self.assertTrue(to_vtt([]).startswith("WEBVTT\n\n"))

    def test_dot_timestamps(self):
        out = to_vtt([TranscriptSegment(0, 3.5, "hi")])
        self.assertIn("00:00:00.000 --> 00:00:03.500", out)

    def test_arrow_escaped(self):
        out = to_vtt([TranscriptSegment(0, 1, "a --> b")])
        self.assertNotIn("a --> b", out)


class JsonTest(unittest.TestCase):
    def test_structure(self):
        data = json.loads(to_json({"language": "zh", "full_text": "hello", "segments": _segs()}))
        self.assertEqual(data["language"], "zh")
        self.assertEqual(len(data["segments"]), 3)
        self.assertEqual(data["segments"][0]["start"], 0.0)
        self.assertEqual(data["segments"][0]["text"], "你好，世界")

    def test_none_source(self):
        data = json.loads(to_json(None))
        self.assertEqual(data["segments"], [])
        self.assertIsNone(data["language"])

    def test_object_source(self):
        from app.models.transcriber_model import TranscriptResult

        tr = TranscriptResult(language="en", full_text="abc", segments=[TranscriptSegment(1, 2, "b")])
        data = json.loads(to_json(tr))
        self.assertEqual(data["language"], "en")
        self.assertEqual(data["segments"][0]["end"], 2.0)


class ExporterTest(unittest.TestCase):
    def test_writes_all_formats_to_file_uris(self):
        with tempfile.TemporaryDirectory() as d:
            result = export_transcript(
                {"language": "zh", "full_text": "x", "segments": _segs()},
                formats=["srt", "vtt", "json"],
                out_dir=d,
                task_id="t1",
            )
            self.assertEqual(sorted(result.keys()), ["json", "srt", "vtt"])
            for fmt, uri in result.items():
                self.assertTrue(uri.startswith("file://"))
                p = Path(uri.replace("file://", ""))
                self.assertTrue(p.exists())

    def test_unknown_format_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            result = export_transcript(
                {"segments": _segs()}, formats=["srt", "bogus"], out_dir=d, task_id="t2"
            )
            self.assertEqual(sorted(result.keys()), ["srt"])

    def test_manifest_recorded(self):
        with tempfile.TemporaryDirectory() as d, mock.patch(
            "bilinote_mcp.export.exporter.record_task_paths"
        ) as rec:
            export_transcript({"segments": _segs()}, formats=["srt"], out_dir=d, task_id="t3")
            rec.assert_called_once()
            # 记录的是 srt 文件的路径
            self.assertTrue(str(rec.call_args[0][1][0]).endswith("transcript.srt"))


class PlatformHandoffTest(unittest.TestCase):
    def test_supported_platforms(self):
        self.assertEqual(pipeline.detect_platform("https://www.bilibili.com/video/BV1xx"), "bilibili")
        self.assertEqual(pipeline.detect_platform("https://www.youtube.com/watch?v=abc"), "youtube")
        self.assertEqual(pipeline.detect_platform("https://v.douyin.com/x"), "douyin")
        self.assertEqual(pipeline.detect_platform("/Users/x/video.mp4"), "local")

    def test_unknown_returns_generic(self):
        # 未知 URL → generic（yt-dlp 通用提取），不再返回 unsupported
        self.assertEqual(pipeline.detect_platform("https://unsupported.example.com/v"), "generic")
        self.assertEqual(pipeline.detect_platform("https://www.xiaohongshu.com/explore/123"), "generic")

    def test_empty_url_raises(self):
        with self.assertRaises(ValueError):
            pipeline.detect_platform("")

    def test_handoff_result_structure(self):
        r = pipeline.handoff_result("https://unsupported.example.com/v")
        self.assertTrue(r["handoff"])
        self.assertEqual(r["platform"], "unsupported")
        self.assertEqual(r["ok"], False)
        self.assertIn("hint", r)
        self.assertIn("url", r)


if __name__ == "__main__":
    unittest.main()
