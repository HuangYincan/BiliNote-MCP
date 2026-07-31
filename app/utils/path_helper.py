import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))


def get_data_dir():
    if getattr(sys, 'frozen', False):

        base_dir = os.path.dirname(sys.executable)
    else:

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))

    data_path = os.path.join(base_dir, "data")
    os.makedirs(data_path, exist_ok=True)
    return data_path


def get_model_dir(subdir: str = "whisper") -> str:
    # 判断是否为打包状态（PyInstaller）
    if getattr(sys, 'frozen', False):
        # exe 执行，放在 APPDATA 或 ~/.cache 下
        base_dir = os.path.join(os.getenv("APPDATA") or str(Path.home()), "BiliNote", "models")
    else:
        # 开发时，相对项目根目录
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../models"))

    path = os.path.join(base_dir, subdir)
    os.makedirs(path, exist_ok=True)
    return path


def get_app_dir(subdir: str = "") -> str:
    """
    返回一个稳定的可写目录：
    - 开发时：使用项目 data 目录
    - 打包后：使用 exe 所在目录
    """
    if getattr(sys, 'frozen', False):
        # 打包后运行：使用 main.exe 所在目录
        base_dir = os.path.dirname(sys.executable)
    else:
        # 开发模式：使用项目的 /data 目录
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))

    full_path = os.path.join(base_dir, subdir)
    os.makedirs(full_path, exist_ok=True)
    return full_path