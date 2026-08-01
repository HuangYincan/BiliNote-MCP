"""
task_manifest 清理功能测试（不碰真实网络/数据库，只用临时目录）。

运行：
    cd /Users/acccan/.claude/jobs/80e51cb0/tmp/wt-an-cleanup
    PYTHONPATH=/Users/acccan/.claude/jobs/80e51cb0/tmp/wt-an-cleanup \
    /Users/acccan/hyc/tools/BiliNote-Mcp/.venv/bin/python tests/test_task_manifest.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.task_manifest import (  # noqa: E402
    cleanup_all_files,
    cleanup_task_files,
    get_task_paths,
    list_task_files,
    record_task_paths,
)


class TaskManifestTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        # resolve 掉 macOS 的 /var → /private/var 软链，保证 manifest 记录与解析一致
        self.root = Path(self._tmp.name).resolve()
        # 目录布局模拟 MCP 数据目录（config.setup_environment 建的那一套）
        self.note_dir = self.root / "note_results"
        self.screens = self.root / "static" / "screenshots"
        self.cfg = self.root / "config"
        self.logs = self.root / "logs"
        self.models = self.root / "models"
        for d in (self.note_dir, self.screens, self.cfg, self.logs, self.models):
            d.mkdir(parents=True, exist_ok=True)
        os.environ["BILINOTE_DATA_DIR"] = str(self.root)
        os.environ["NOTE_OUTPUT_DIR"] = str(self.note_dir)
        os.environ["IMAGE_OUTPUT_DIR"] = str(self.screens)
        os.environ["BILINOTE_CONFIG_DIR"] = str(self.cfg)

    def tearDown(self):
        self._tmp.cleanup()
        for k in (
            "BILINOTE_DATA_DIR",
            "NOTE_OUTPUT_DIR",
            "IMAGE_OUTPUT_DIR",
            "BILINOTE_CONFIG_DIR",
        ):
            os.environ.pop(k, None)

    # ---------- 造假 task 产物 ----------

    def _make_task(self, task_id: str) -> Path:
        """造一个假 task：中间文件 + dl 目录 + 便携笔记目录（note.md + Assets）。"""
        (self.note_dir / f"{task_id}_audio.json").write_text("{}", encoding="utf-8")
        (self.note_dir / f"{task_id}_transcript.json").write_text("{}", encoding="utf-8")
        (self.note_dir / f"{task_id}_markdown.md").write_text("# 缓存", encoding="utf-8")
        (self.note_dir / f"{task_id}.status.json").write_text(
            '{"status":"SUCCESS"}', encoding="utf-8"
        )
        (self.note_dir / f"{task_id}.json").write_text(
            '{"markdown":"# 最终"}', encoding="utf-8"
        )
        dl = self.note_dir / f"dl_{task_id}"
        dl.mkdir(exist_ok=True)
        (dl / "video.mp4").write_bytes(b"x")
        note_dir = self.note_dir / task_id
        note_dir.mkdir(exist_ok=True)
        (note_dir / "note.md").write_text("# 最终笔记", encoding="utf-8")
        assets = note_dir / "Assets"
        assets.mkdir(exist_ok=True)
        (assets / "1.jpg").write_bytes(b"y")
        record_task_paths(
            task_id,
            [
                self.note_dir / f"{task_id}_audio.json",
                self.note_dir / f"{task_id}_transcript.json",
                self.note_dir / f"{task_id}_markdown.md",
                self.note_dir / f"{task_id}.status.json",
                self.note_dir / f"{task_id}.json",
                dl,
                note_dir,
                note_dir / "note.md",
            ],
        )
        return note_dir

    # ---------- manifest 记录 / 读取 ----------

    def test_record_and_get_dedup(self):
        tid = "abc123"
        record_task_paths(tid, [str(self.note_dir / f"{tid}_a.json"), str(self.note_dir / f"{tid}_b.json")])
        record_task_paths(tid, [str(self.note_dir / f"{tid}_b.json"), str(self.note_dir / f"{tid}_c.json")])
        paths = get_task_paths(tid)
        self.assertEqual(len(paths), 3)
        self.assertIn(str(self.note_dir / f"{tid}_a.json"), paths)
        self.assertIn(str(self.note_dir / f"{tid}_b.json"), paths)
        self.assertIn(str(self.note_dir / f"{tid}_c.json"), paths)

    def test_get_task_paths_missing(self):
        self.assertEqual(get_task_paths("nope"), [])

    def test_record_empty_task_id_noop(self):
        record_task_paths("", [str(self.note_dir / "x.json")])
        self.assertFalse((self.note_dir / ".manifest.json").exists())

    # ---------- get_task_files（先查后清） ----------

    def test_list_task_files(self):
        tid = "task01"
        note_dir = self._make_task(tid)
        info = list_task_files(tid)
        self.assertEqual(info["task_id"], tid)
        # manifest 记录的路径都在 existing 里（去重后）
        for p in get_task_paths(tid):
            self.assertIn(str(Path(p)), info["existing"])
        # 前缀模式扫描到 dl 目录与最终笔记
        self.assertTrue(any("dl_" in s for s in info["existing"]))
        self.assertTrue(any(s.endswith("note.md") for s in info["existing"]))
        self.assertTrue(note_dir.exists())

    # ---------- cleanup_note ----------

    def test_cleanup_note_keeps_note(self):
        tid = "task02"
        note_dir = self._make_task(tid)
        res = cleanup_task_files(tid, include_note=False)
        # 中间产物被删
        self.assertFalse((self.note_dir / f"{tid}_audio.json").exists())
        self.assertFalse((self.note_dir / f"{tid}_transcript.json").exists())
        self.assertFalse((self.note_dir / f"{tid}_markdown.md").exists())
        self.assertFalse((self.note_dir / f"{tid}.json").exists())
        self.assertFalse((self.note_dir / f"dl_{tid}").exists())
        # 截图 Assets 被删
        self.assertFalse((note_dir / "Assets").exists())
        # 最终笔记保留
        self.assertTrue((note_dir / "note.md").exists())
        self.assertTrue(res["note_kept"])
        # include_note=False 时 manifest 保留（后续还能查/整删）
        self.assertTrue((self.note_dir / f"{tid}.manifest.json").exists())

    def test_cleanup_note_include_note(self):
        tid = "task03"
        note_dir = self._make_task(tid)
        res = cleanup_task_files(tid, include_note=True)
        # 连最终笔记 + manifest 一起删
        self.assertFalse(note_dir.exists())
        self.assertFalse((self.note_dir / f"{tid}.manifest.json").exists())
        self.assertFalse((self.note_dir / f"dl_{tid}").exists())
        self.assertFalse((self.note_dir / f"{tid}_audio.json").exists())
        self.assertFalse(res["note_kept"])

    # ---------- 路径穿越防护 ----------

    def test_cleanup_note_path_traversal_rejected(self):
        tid = "task04"
        self._make_task(tid)
        outside = self.root.parent / "evil.txt"
        outside.write_text("do not delete", encoding="utf-8")
        # 恶意路径进 manifest：数据目录外的绝对路径 + 相对穿越路径
        record_task_paths(tid, [str(outside), "../../../../etc/passwd"])
        res = cleanup_task_files(tid, include_note=True)
        # 外部文件仍在（越界路径被 resolve 校验拒绝）
        self.assertTrue(outside.exists())
        self.assertNotIn(str(outside), res["deleted"])
        self.assertNotIn(str(outside), res["errors"])
        # 数据目录内的正常产物照常被删
        self.assertFalse((self.note_dir / f"{tid}_audio.json").exists())
        self.assertFalse((self.note_dir / f"dl_{tid}").exists())
        outside.unlink(missing_ok=True)

    # ---------- cleanup_all ----------

    def test_cleanup_all_keeps_config_models(self):
        (self.note_dir / "x.json").write_text("{}", encoding="utf-8")
        (self.screens / "a.jpg").write_bytes(b"a")
        (self.logs / "mcp_stderr.log").write_text("log", encoding="utf-8")
        (self.cfg / "app_config.json").write_text("{}", encoding="utf-8")
        (self.models / "whisper").mkdir(exist_ok=True)
        (self.models / "whisper" / "model.bin").write_bytes(b"m")
        res = cleanup_all_files(include_config=False, include_models=False)
        # 清空 note_results / screenshots / logs
        self.assertEqual(list(self.note_dir.iterdir()), [])
        self.assertEqual(list(self.screens.iterdir()), [])
        self.assertEqual(list(self.logs.iterdir()), [])
        # 保留 config / models
        self.assertTrue((self.cfg / "app_config.json").exists())
        self.assertTrue((self.models / "whisper" / "model.bin").exists())
        self.assertIn("config", res["kept"])
        self.assertIn("models", res["kept"])

    def test_cleanup_all_include_config(self):
        (self.note_dir / "y.json").write_text("{}", encoding="utf-8")
        (self.cfg / "app_config.json").write_text("{}", encoding="utf-8")
        (self.models / "whisper").mkdir(exist_ok=True)
        (self.models / "whisper" / "model.bin").write_bytes(b"m")
        res = cleanup_all_files(include_config=True, include_models=False)
        # config 被清，models 保留
        self.assertEqual(list(self.cfg.iterdir()), [])
        self.assertTrue((self.models / "whisper" / "model.bin").exists())
        self.assertIn("models", res["kept"])
        self.assertNotIn("config", res["kept"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
