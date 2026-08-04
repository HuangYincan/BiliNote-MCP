"""说话人分离（app/services/diarization.py）单元测试。

不碰真实 pyannote（重依赖未装）——验证：
1. pyannote 未装时 diarize_audio 抛 RuntimeError 带安装指引；
2. 缺 HF_TOKEN 时报错；
3. assign_speakers 按时间重叠对齐给段填 speaker。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.transcriber_model import TranscriptSegment
from app.services import diarization


def _real_import_blocker():
    """返回一个 __import__ 替身：仅对 pyannote.audio 抛 ImportError，其余透传。"""
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "pyannote.audio":
            raise ImportError("no pyannote")
        return real_import(name, *args, **kwargs)

    return fake_import


class DiarizeNotInstalledTest(unittest.TestCase):
    def test_raises_install_hint_when_pyannote_missing(self):
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            with mock.patch("builtins.__import__", side_effect=_real_import_blocker()):
                with self.assertRaises(RuntimeError) as ctx:
                    diarization.diarize_audio(f.name, hf_token="t")
        self.assertIn("pyannote", str(ctx.exception))

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            diarization.diarize_audio("/no/such.wav", hf_token="t")

    def test_missing_token_raises(self):
        # pyannote 可 import 但未传 token 且环境无 HUGGINGFACE_HUB_TOKEN → RuntimeError
        import types

        fake_pkg = types.ModuleType("pyannote.audio")
        fake_pkg.Pipeline = mock.Mock()
        sys.modules["pyannote.audio"] = fake_pkg
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav") as f:
                with mock.patch.dict(
                    "os.environ", {}, clear=False
                ):
                    # 确保模块内读 HUGGINGFACE_HUB_TOKEN 为空
                    with mock.patch(
                        "app.services.diarization.os.environ.get", return_value=""
                    ):
                        with self.assertRaises(RuntimeError) as ctx:
                            diarization.diarize_audio(f.name)  # 无 hf_token
                    self.assertIn("HF_TOKEN", str(ctx.exception))
        finally:
            sys.modules.pop("pyannote.audio", None)


class AssignSpeakersTest(unittest.TestCase):
    def _turns(self):
        return [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
            {"start": 5.0, "end": 10.0, "speaker": "SPEAKER_01"},
        ]

    def test_assigns_overlap_speaker(self):
        segs = [
            TranscriptSegment(0, 2, "你好"),
            TranscriptSegment(6, 8, "世界"),
        ]
        out = diarization.assign_speakers(segs, self._turns())
        self.assertEqual(out[0].speaker, "SPEAKER_00")
        self.assertEqual(out[1].speaker, "SPEAKER_01")

    def test_no_overlap_keeps_none(self):
        segs = [TranscriptSegment(100, 102, "无重叠")]
        out = diarization.assign_speakers(segs, self._turns())
        self.assertIsNone(out[0].speaker)

    def test_original_not_mutated(self):
        segs = [TranscriptSegment(0, 2, "你好")]
        diarization.assign_speakers(segs, self._turns())
        self.assertIsNone(segs[0].speaker)


if __name__ == "__main__":
    unittest.main(verbosity=2)
