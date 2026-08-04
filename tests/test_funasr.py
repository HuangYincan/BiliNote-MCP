"""FunASR 中文引擎（app/transcriber/funasr_transcriber.py）单元测试。

不碰真实 funasr（重依赖未装）——mock AutoModel.generate 验证结果映射。

覆盖：
1. funasr 未装 → RuntimeError 安装指引；
2. sentence_info 毫秒 → TranscriptSegment 秒（含除 1000）映射；
3. 无 sentence_info（极短音频）→ 整段单段；
4. 空结果 → 空 TranscriptResult；
5. TranscriptSegment 带标点文本原样保留。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.transcriber.funasr_transcriber import FunASRTranscriber


class FunASRNotInstalledTest(unittest.TestCase):
    def test_raises_install_hint_when_funasr_missing(self):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "funasr":
                raise ImportError("no funasr")
            return real_import(name, *args, **kwargs)

        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            t = FunASRTranscriber()
            with mock.patch("builtins.__import__", side_effect=fake_import):
                with self.assertRaises(RuntimeError) as ctx:
                    t.transcript(f.name)
        self.assertIn("funasr", str(ctx.exception))


class FunASRMappingTest(unittest.TestCase):
    def _make_transcriber(self, result):
        t = FunASRTranscriber()
        model = mock.Mock()
        model.generate.return_value = result
        t._model = model
        return t

    def test_sentence_info_mapped_to_segments(self):
        # sentence_info start/end 是毫秒 → 秒（/1000）
        res = [{
            "text": "大家好。这是标点。",
            "sentence_info": [
                {"start": 0, "end": 1200, "text": "大家好。"},
                {"start": 1200, "end": 3500, "text": "这是标点。"},
            ],
        }]
        t = self._make_transcriber(res)
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            out = t.transcript(f.name)
        self.assertEqual(len(out.segments), 2)
        self.assertEqual(out.segments[0].start, 0.0)
        self.assertEqual(out.segments[0].end, 1.2)  # 1200ms / 1000
        self.assertEqual(out.segments[1].start, 1.2)
        self.assertEqual(out.segments[1].end, 3.5)
        self.assertEqual(out.segments[0].text, "大家好。")
        self.assertEqual(out.full_text, "大家好。这是标点。")
        self.assertEqual(out.language, "zh")

    def test_no_sentence_info_single_segment(self):
        res = [{"text": "极短音频整段文本。"}]
        t = self._make_transcriber(res)
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            out = t.transcript(f.name)
        self.assertEqual(len(out.segments), 1)
        self.assertEqual(out.segments[0].text, "极短音频整段文本。")

    def test_empty_result(self):
        t = self._make_transcriber([])
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            out = t.transcript(f.name)
        self.assertEqual(out.segments, [])
        self.assertEqual(out.full_text, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
