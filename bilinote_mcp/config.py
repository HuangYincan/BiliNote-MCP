"""运行时环境初始化。

必须在 import app.*（vendored 核心流水线）之前调用 setup_environment()：
`app/db/engine.py` 与 `app/services/note.py` 在模块 import 时读取
DATABASE_URL / NOTE_OUTPUT_DIR 等环境变量。

数据根目录的解析逻辑：
  - 源码 checkout（`bilinote_mcp/` 同级有 pyproject.toml）→ 仓库根 `data/`；
  - 已安装包（uvx / uv tool / pip，代码在 site-packages 或 uv 缓存里）→ 用户数据目录
    （macOS/Linux：`~/.local/share/bilinote-mcp`；Windows：`%APPDATA%/bilinote-mcp`），
    绝不写进 site-packages。
可用环境变量 BILINOTE_DATA_DIR 可显式覆盖。
"""
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_IS_SOURCE_CHECKOUT = (_REPO_ROOT / "pyproject.toml").exists()


def _default_data_dir() -> Path:
    if _IS_SOURCE_CHECKOUT:
        return _REPO_ROOT / "data"
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "bilinote-mcp"


def setup_environment() -> Path:
    """解析数据目录并设置环境变量（仅在没有显式设置时填充默认值）。返回数据根目录 Path。"""
    data_dir = Path(os.environ.get("BILINOTE_DATA_DIR") or _default_data_dir()).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    note_results = data_dir / "note_results"
    screenshots = data_dir / "static" / "screenshots"
    config_dir = data_dir / "config"
    models_dir = data_dir / "models"
    for d in (note_results, screenshots, config_dir, models_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 数据根目录本身（logger / path_helper / downloaders 会读）
    os.environ.setdefault("BILINOTE_DATA_DIR", str(data_dir))
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
    # whisper/mlx 模型下载的请求超时：网络不可达时让每次下载快速失败，
    # 避免 huggingface_hub 重试 + WhisperTranscriber 自愈重下长时间阻塞任务
    # （真正需要音频转写的任务会以 FAILED + 明确错误结束，而非卡在 INITIALIZING）。
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "10")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "10")
    # 配置目录（transcriber_config / cookie 落到这里，避免依赖 CWD）
    os.environ.setdefault("BILINOTE_CONFIG_DIR", str(config_dir))
    # 模型目录：已安装包时一定要指到用户数据目录（否则会写进 site-packages）。
    # 源码 checkout 保持原默认 <仓库>/models（已有下载的模型不迁移）。
    if not _IS_SOURCE_CHECKOUT:
        os.environ.setdefault("BILINOTE_MODEL_DIR", str(models_dir))
    # note.py 引用到的后端地址变量（本仓库不使用，仅保证不报错）
    os.environ.setdefault("API_BASE_URL", "http://localhost")
    os.environ.setdefault("BACKEND_PORT", "8483")

    return data_dir


def get_app_config() -> dict:
    """读取持久化应用配置（如默认笔记位置），存于 BILINOTE_CONFIG_DIR/app_config.json。"""
    import json

    path = Path(os.environ.get("BILINOTE_CONFIG_DIR", "config")) / "app_config.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def set_app_config(key: str, value) -> None:
    """持久化应用配置。"""
    import json

    path = Path(os.environ.get("BILINOTE_CONFIG_DIR", "config")) / "app_config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = get_app_config()
    cfg[key] = value
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_app_config(key: str) -> None:
    """删除一条持久化应用配置（不存在则无操作）。

    用于「清除默认模型」等场景：必须删 key，而不是写成 null。
    """
    import json

    path = Path(os.environ.get("BILINOTE_CONFIG_DIR", "config")) / "app_config.json"
    if not path.exists():
        return
    cfg = get_app_config()
    if key not in cfg:
        return
    cfg.pop(key)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
