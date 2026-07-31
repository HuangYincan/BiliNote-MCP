"""whisper / mlx 模型下载就绪检查（纯函数，无 FastAPI 依赖）。

上游把模型就绪判断放在 app/routers/config.py（依赖 FastAPI），本仓库剥离 Web 层后
把这两个检查函数 + 下载状态查询抽到这里，供 TranscriberConfigManager 做
「开始转写前确认本地模型已下载」的门禁，也供 MCP 的 health_check / 模型管理工具复用。
"""
import os
from pathlib import Path

from app.transcriber import model_download_state as dl_state
from app.utils.path_helper import get_model_dir


def check_whisper_model_exists(model_size: str, subdir: str = "whisper") -> bool:
    """检查指定 fast-whisper 模型是否已下载完整到本地。"""
    from app.transcriber.whisper_models import (
        resolve_whisper_model,
        is_local_target,
        hf_cache_dirname,
    )
    try:
        target = resolve_whisper_model(model_size)
    except Exception:
        return False
    if is_local_target(target):
        return (Path(target) / "model.bin").exists()

    model_dir = Path(get_model_dir(subdir))
    hf_repo_dir = model_dir / hf_cache_dirname(target) / "snapshots"
    if hf_repo_dir.exists():
        for snapshot in hf_repo_dir.iterdir():
            if (snapshot / "model.bin").exists():
                return True
    legacy = model_dir / f"whisper-{model_size}" / "model.bin"
    return legacy.exists()


def check_mlx_whisper_model_exists(model_size: str) -> bool:
    """检查指定 mlx-whisper 模型是否已下载完整（以 config.json 为判据）。"""
    try:
        from app.transcriber.mlx_whisper_transcriber import MLX_MODEL_MAP
    except Exception:
        return False
    repo_id = MLX_MODEL_MAP.get(model_size)
    if not repo_id:
        return False
    model_dir = get_model_dir("mlx-whisper")
    model_path = os.path.join(model_dir, repo_id)
    return (Path(model_path) / "config.json").exists()


def is_downloading(key: str) -> bool:
    """该模型是否处于「下载中」状态（进程内内存态）。"""
    return dl_state.get_status(key) == dl_state.DOWNLOADING
