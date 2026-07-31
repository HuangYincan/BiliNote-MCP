"""运行时环境初始化。

必须在 import app.*（vendored 核心流水线）之前调用 setup_environment()：
`app/db/engine.py` 与 `app/services/note.py` 在模块 import 时读取
DATABASE_URL / NOTE_OUTPUT_DIR 等环境变量。
"""
import os
from pathlib import Path


def setup_environment() -> Path:
    """解析数据目录并设置环境变量（仅在没有显式设置时填充默认值）。

    返回数据根目录 Path。可用环境变量：
      - BILINOTE_DATA_DIR      数据根目录（默认 <仓库>/data）
      - BILINOTE_BACKEND_URL   兼容字段（本仓库不依赖后端，预留）
    """
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = Path(
        os.environ.get("BILINOTE_DATA_DIR") or (repo_root / "data")
    ).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    note_results = data_dir / "note_results"
    screenshots = data_dir / "static" / "screenshots"
    config_dir = data_dir / "config"
    for d in (note_results, screenshots, config_dir):
        d.mkdir(parents=True, exist_ok=True)

    # SQLite 数据库（engine.py 在 import 时读）
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{data_dir / 'bili_note.db'}")
    # 笔记/截图输出目录（note.py 在 import 时读）
    os.environ.setdefault("NOTE_OUTPUT_DIR", str(note_results))
    os.environ.setdefault("IMAGE_OUTPUT_DIR", str(screenshots))
    # Markdown 里截图 URL 前缀 —— 用 file:// 绝对路径，agent 可直接读取
    os.environ.setdefault("IMAGE_BASE_URL", screenshots.as_uri())
    # 转写引擎默认值（transcriber_config_manager 无配置文件时 fallback）
    os.environ.setdefault("TRANSCRIBER_TYPE", "fast-whisper")
    os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
    # 配置目录（transcriber_config / cookie 落到这里，避免依赖 CWD）
    os.environ.setdefault("BILINOTE_CONFIG_DIR", str(config_dir))
    # note.py 引用到的后端地址变量（本仓库不使用，仅保证不报错）
    os.environ.setdefault("API_BASE_URL", "http://localhost")
    os.environ.setdefault("BACKEND_PORT", "8483")

    return data_dir
