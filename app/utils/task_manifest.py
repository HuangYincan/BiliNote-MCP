"""task_manifest.py —— 任务产物路径的可追踪清单与清理。

任务生成的文件（下载的视频/音频、转写缓存、markdown 缓存、status/result JSON、
dl_{task_id} 下载目录、note_dir 便携笔记等）会被**尽力而为**地记入
`NOTE_OUTPUT_DIR/{task_id}.manifest.json`，供 AGENT：
  1. `list_task_files` 先查后清（返回 manifest 记录 + 真实存在的文件）；
  2. `cleanup_task_files` 按 task 精确清理（默认保留最终笔记）；
  3. `cleanup_all_files` 全局清理（恢复出厂，默认保留 config/ 与 models/）。

安全纪律：
  - 只删除 manifest 记录 / 明确前缀模式（note_results/{task_id}、dl_{task_id}）的路径；
  - 任何用户/manifest 给的路径在删除前都要 `resolve()` 校验落在数据目录内（防路径穿越）；
  - 删除逐条 try/except，失败跳过并统计。
记录是尽力而为：失败只记日志，绝不阻断生成流水线。
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


# ---------------- 目录解析（读环境变量，测试可注入） ----------------

def get_data_dir() -> Path:
    """数据根目录（config.setup_environment 设置 BILINOTE_DATA_DIR）。"""
    return Path(os.getenv("BILINOTE_DATA_DIR", "data")).expanduser().resolve()


def get_note_dir() -> Path:
    """笔记/任务产物输出目录（与 app.services.note.NOTE_OUTPUT_DIR 一致）。"""
    return Path(os.getenv("NOTE_OUTPUT_DIR", str(get_data_dir() / "note_results"))).expanduser().resolve()


def get_screenshots_dir() -> Path:
    """静态截图目录（与 app.services.note.IMAGE_OUTPUT_DIR 一致）。"""
    return Path(os.getenv("IMAGE_OUTPUT_DIR", str(get_data_dir() / "static" / "screenshots"))).expanduser().resolve()


def get_config_dir() -> Path:
    """配置目录（LLM key / cookie / 转写设置 / app_config）。"""
    return Path(os.getenv("BILINOTE_CONFIG_DIR", str(get_data_dir() / "config"))).expanduser().resolve()


def get_logs_dir() -> Path:
    """日志目录（server 的 stderr 重定向也在此）。"""
    return get_data_dir() / "logs"


def get_models_dir() -> Path:
    """模型缓存目录（whisper/mlx；全局清理默认保留）。"""
    return Path(os.getenv("BILINOTE_MODEL_DIR", str(get_data_dir() / "models"))).expanduser().resolve()


def manifest_path(task_id: str) -> Path:
    return get_note_dir() / f"{task_id}.manifest.json"


# ---------------- manifest 记录 / 读取 ----------------

def record_task_paths(task_id: str, paths: Sequence) -> None:
    """把 task 创建的文件/目录追加进 manifest（去重，原子写 tmp+replace）。

    尽力而为：任何失败只记日志，不抛异常、不阻断调用方。
    """
    if not task_id:
        return
    try:
        existing = get_task_paths(task_id)
        seen = set(existing)
        additions: List[str] = []
        for p in paths:
            if not p:
                continue
            s = str(p)
            if s not in seen:
                seen.add(s)
                additions.append(s)
        if not additions:
            return
        f = manifest_path(task_id)
        f.parent.mkdir(parents=True, exist_ok=True)
        data = {"task_id": task_id, "paths": existing + additions}
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(f)
    except Exception as e:  # noqa: BLE001 —— 记录是尽力而为
        logger.warning("记录 task 路径失败 task_id=%s: %s", task_id, e)


def get_task_paths(task_id: str) -> List[str]:
    """读 manifest；不存在或损坏返回 []。"""
    f = manifest_path(task_id)
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return list(data.get("paths", []))
    except Exception:  # noqa: BLE001
        return []


def remove_manifest(task_id: str) -> None:
    """删除 manifest 文件（include_note=True 的整删收尾）。失败只记日志。"""
    try:
        manifest_path(task_id).unlink(missing_ok=True)
    except Exception as e:  # noqa: BLE001
        logger.warning("删除 manifest 失败 task_id=%s: %s", task_id, e)


# ---------------- 安全删除辅助 ----------------

def _safe_resolve(path, roots: Sequence[Path]) -> Optional[Path]:
    """把用户/manifest 给的路径解析为绝对路径；不在任一 root 内（或解析失败）返回 None。

    路径穿越防护的核心：任何待删路径都必须落在数据目录内。
    """
    try:
        p = Path(str(path)).expanduser().resolve()
    except Exception:  # noqa: BLE001
        return None
    for root in roots:
        try:
            r = Path(str(root)).expanduser().resolve()
        except Exception:  # noqa: BLE001
            continue
        try:
            p.relative_to(r)
            return p
        except ValueError:
            continue
    return None


def _delete_all(paths: Sequence[Path]) -> Dict[str, List]:
    """批量删除文件/目录；返回 {deleted, missing, errors}。深路径先删、逐条容错。"""
    deleted: List[str] = []
    missing: List[str] = []
    errors: List[Dict] = []
    ordered = sorted(
        {str(p) for p in paths if p},
        key=lambda s: (s.count(os.sep), s),
        reverse=True,  # 深路径先删（子先于父）
    )
    for s in ordered:
        p = Path(s)
        try:
            exists = p.exists() or p.is_symlink()
        except Exception:  # noqa: BLE001
            exists = False
        if not exists:
            missing.append(s)
            continue
        try:
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink(missing_ok=True)
            deleted.append(s)
        except Exception as e:  # noqa: BLE001
            errors.append({"path": s, "error": str(e)})
    return {"deleted": deleted, "missing": missing, "errors": errors}


def _note_paths(task_id: str) -> set:
    """该 task 的「最终笔记」路径集合：note_dir 目录与其 note.md。"""
    roots = [get_note_dir(), get_data_dir()]
    notes = set()
    for p in get_task_paths(task_id):
        resolved = _safe_resolve(p, roots)
        if not resolved:
            continue
        if resolved.name == "note.md":
            notes.add(resolved)
        elif resolved.is_dir() and (resolved / "note.md").exists():
            notes.add(resolved)
    # 便携默认笔记目录：note_results/{task_id}/note.md
    portable = get_note_dir() / task_id
    if (portable / "note.md").exists():
        notes.add(portable / "note.md")
        notes.add(portable)
    return notes


# ---------------- 查询 ----------------

def list_task_files(task_id: str) -> Dict:
    """列出某 task 在磁盘上相关的文件/目录（manifest 记录 + {task_id}* 前缀扫描）。

    返回 {task_id, manifest_paths, existing}，existing 是真实存在的文件/目录列表。
    """
    manifest = get_task_paths(task_id)
    roots = [get_note_dir(), get_data_dir()]
    existing: List[str] = []
    for p in manifest:
        resolved = _safe_resolve(p, roots)
        if resolved is not None and (resolved.exists() or resolved.is_symlink()):
            existing.append(str(resolved))
    note_dir = get_note_dir()
    if note_dir.exists():
        for f in note_dir.glob(f"{task_id}*"):
            existing.append(str(f))
    dl = note_dir / f"dl_{task_id}"
    if dl.exists():
        existing.append(str(dl))
    # 去重保序
    existing = list(dict.fromkeys(existing))
    return {"task_id": task_id, "manifest_paths": manifest, "existing": existing}


# ---------------- 清理 ----------------

def cleanup_task_files(task_id: str, include_note: bool = False) -> Dict:
    """按 task 清理中间产物；include_note=True 时连最终笔记（note_dir/note.md）一起删。

    只删 manifest 记录 / note_results/{task_id}* / dl_{task_id} 的路径，
    且 resolve 校验在数据目录内。返回统计（deleted/missing/errors/note_kept）。
    """
    note_dir = get_note_dir()
    roots = [note_dir, get_data_dir()]
    notes = _note_paths(task_id)

    to_delete: set = set()

    # 1. manifest 记录的路径（note 之外；越界/解析失败 → 拒绝）
    for p in get_task_paths(task_id):
        resolved = _safe_resolve(p, roots)
        if resolved is None:
            continue
        if not include_note and resolved in notes:
            continue
        to_delete.add(resolved)

    # 2. 前缀模式：note_results/{task_id}* 文件
    if note_dir.exists():
        for f in note_dir.glob(f"{task_id}*"):
            if f.name == f"{task_id}.manifest.json" and not include_note:
                continue  # include_note=False 时保留 manifest（后续还能查/整删）
            if f.is_file():
                to_delete.add(f)
            elif f.is_dir():
                if include_note:
                    to_delete.add(f)  # 整个便携笔记目录
                else:
                    # 保留 note.md，删中间子目录（Assets/ frames/ 等）
                    for child in f.iterdir():
                        if child.name == "note.md":
                            continue
                        to_delete.add(child)

    # 3. dl_{task_id} 下载目录
    dl = note_dir / f"dl_{task_id}"
    if dl.exists():
        to_delete.add(dl)

    # 4. include_note=True：连便携默认笔记目录/note_dir 一起删，并删 manifest
    if include_note:
        to_delete.update(notes)
        portable = note_dir / task_id
        if portable.exists():
            to_delete.add(portable)
        remove_manifest(task_id)
    else:
        # 双保险：note 绝不进删除集合
        to_delete -= notes

    stats = _delete_all(to_delete)
    return {
        "task_id": task_id,
        "include_note": include_note,
        "note_kept": (not include_note) and bool(notes),
        **stats,
    }


def cleanup_all_files(include_config: bool = False, include_models: bool = False) -> Dict:
    """全局清理（恢复出厂）：清空 note_results / static/screenshots / logs 的所有任务产物。

    默认保留 config/（LLM key / cookie / 转写设置）与 models/（模型可复用、重下成本高）；
    include_config=True 时连 config/ 一起清；include_models=True 时连 models/ 一起清。
    数据库记录（bili_note.db）不动。
    """
    result: Dict = {"cleaned": {}, "kept": []}

    def _empty(d: Path, key: str) -> None:
        if not d.exists() or not d.is_dir():
            result["cleaned"][key] = {"deleted": [], "missing": [], "errors": []}
            return
        result["cleaned"][key] = _delete_all(list(d.iterdir()))

    _empty(get_note_dir(), "note_results")
    _empty(get_screenshots_dir(), "static/screenshots")
    _empty(get_logs_dir(), "logs")

    if include_config:
        _empty(get_config_dir(), "config")
    else:
        result["kept"].append("config")

    if include_models:
        _empty(get_models_dir(), "models")
    else:
        result["kept"].append("models")

    return result
