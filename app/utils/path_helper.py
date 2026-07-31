import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))


def get_data_dir():
    """稳定的可写数据目录。优先 BILINOTE_DATA_DIR（由 bilinote_mcp.config 设置）。"""
    env = os.getenv("BILINOTE_DATA_DIR")
    if env:
        os.makedirs(env, exist_ok=True)
        return env
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = PROJECT_ROOT

    data_path = os.path.join(base_dir, "data")
    os.makedirs(data_path, exist_ok=True)
    return data_path


def get_model_dir(subdir: str = "whisper") -> str:
    """模型缓存目录。优先 BILINOTE_MODEL_DIR/<subdir>（已安装包时由 config 设置）。"""
    env = os.getenv("BILINOTE_MODEL_DIR")
    if env:
        path = os.path.join(env, subdir)
        os.makedirs(path, exist_ok=True)
        return path
    # 判断是否为打包状态（PyInstaller）
    if getattr(sys, 'frozen', False):
        # exe 执行，放在 APPDATA 或 ~/.cache 下
        base_dir = os.path.join(os.getenv("APPDATA") or str(Path.home()), "BiliNote", "models")
    else:
        # 开发时，相对项目根目录
        base_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "models"))

    path = os.path.join(base_dir, subdir)
    os.makedirs(path, exist_ok=True)
    return path


def get_app_dir(subdir: str = "") -> str:
    """
    返回一个稳定的可写目录（下载缓存 / 中间帧等）。
    - 优先 BILINOTE_DATA_DIR（由 bilinote_mcp.config 设置）
    - 开发时：使用项目 data 目录
    - 打包后：使用 exe 所在目录
    """
    env = os.getenv("BILINOTE_DATA_DIR")
    if env:
        full_path = os.path.join(env, subdir)
        os.makedirs(full_path, exist_ok=True)
        return full_path
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = PROJECT_ROOT

    full_path = os.path.join(base_dir, subdir)
    os.makedirs(full_path, exist_ok=True)
    return full_path
