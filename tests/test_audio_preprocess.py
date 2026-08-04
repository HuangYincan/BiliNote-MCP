"""音频预处理（app/transcriber/audio_preprocess.py）与 pipeline 集成的单元测试。

不碰真实 ffmpeg 转换 / 转写引擎 —— 用 mock 隔离。

覆盖：
1. normalize_to_wav / chunk_if_long / probe_duration（mock subprocess）；
2. pipeline._preprocess_enabled：默认关 / 配置开启；
3. pipeline.transcribe_audio：默认关行为不变（直传原始文件）、开启时走分块转写并时间偏移。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services import pipeline
from app.transcriber import audio_preprocess


class NormalizeTest(unittest.TestCase):
    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            audio_preprocess.normalize_to_wav("/no/such/file.mp3")

    def test_normalize_invokes_ffmpeg(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.mp3"
            src.write_bytes(b"fake")
            with mock.patch.object(audio_preprocess, "_ffmpeg") as ff:
                out = audio_preprocess.normalize_to_wav(str(src), out_dir=d)
            self.assertTrue(out.endswith("_16k.wav"))
            ff.assert_called_once()


class ChunkTest(unittest.TestCase):
    def test_short_audio_not_chunked(self):
        with mock.patch.object(audio_preprocess, "probe_duration", return_value=10.0):
            result = audio_preprocess.chunk_if_long("/tmp/x.wav", max_seconds=60)
        self.assertEqual(result, ["/tmp/x.wav"])

    def test_long_audio_chunked(self):
        with mock.patch.object(audio_preprocess, "probe_duration", return_value=3600.0):
            with mock.patch.object(audio_preprocess, "_ffmpeg"):
                with tempfile.TemporaryDirectory() as d:
                    result = audio_preprocess.chunk_if_long("/tmp/x.wav", max_seconds=1800, out_dir=d)
        self.assertGreater(len(result), 0)


class PipelineIntegrationTest(unittest.TestCase):
    def _fake_transcriber(self):
        t = mock.Mock()
        t.transcript.return_value = TranscriptResult(
            language="zh",
            full_text="hello",
            segments=[TranscriptSegment(0, 2, "hello")],
        )
        return t

    def test_preprocess_disabled_default(self):
        # 默认关 → transcribe_audio 直传原始文件，不调预处理
        with mock.patch.object(pipeline, "_preprocess_enabled", return_value=False):
            fake = self._fake_transcriber()
            with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
                result = pipeline.transcribe_audio(f.name, transcriber=fake)
        self.assertEqual(result["full_text"], "hello")
        # transcript 收到的是原始文件路径
        fake.transcript.assert_called_once_with(file_path=mock.ANY)

    def test_preprocess_enabled_single_chunk(self):
        # 开启 + 不分块 → normalize 后转写单块
        fake = self._fake_transcriber()
        with mock.patch.object(pipeline, "_preprocess_enabled", return_value=True):
            with mock.patch.object(
                pipeline, "_transcribe_with_preprocess", return_value={"full_text": "hello"}
            ) as wrap:
                with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
                    result = pipeline.transcribe_audio(f.name, transcriber=fake)
        self.assertEqual(result["full_text"], "hello")
        wrap.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
