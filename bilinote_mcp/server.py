"""BiliNote-Mcp —— 把 BiliNote 的核心能力封装为 MCP 工具。

架构：内嵌流水线（`app/` 为 vendored 自上游的核心模块），**无需启动 FastAPI 后端**。
生成笔记为异步任务：`generate_note` 立即返回 task_id，后台线程执行
`NoteGenerator.generate()`，进度写入 note_results/{task_id}.status.json，
最终结果写入 note_results/{task_id}.json。

运行时环境（数据目录、DB、输出目录）在 import app.* 之前由 config.setup_environment()
初始化，详见 bilinote_mcp/config.py。
"""
import json
import logging
import os
import re
import shutil
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from bilinote_mcp.config import get_app_config, setup_environment
from bilinote_mcp.provider_probe import probe_models

DATA_DIR = setup_environment()

# MCP stdio 传输用 stdout 承载 JSON-RPC；vendored 代码里有大量裸 print()（含模块导入时）
# 会污染协议。进程级把 print 重定向到 stderr —— 必须在 import app.* 之前生效
#（FastMCP 通过 sys.stdout.buffer 写响应，不受影响）。
import builtins as _builtins

_orig_print = _builtins.print


def _print_to_stderr(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    _orig_print(*args, **kwargs)


_builtins.print = _print_to_stderr

# vendored 核心流水线
from app.db.engine import get_engine
from app.db.init_db import init_db
from app.db.model_dao import get_models_by_provider, insert_model
from app.db.provider_dao import seed_default_providers
from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.services.cookie_manager import CookieConfigManager
from app.services.note import NOTE_OUTPUT_DIR, NoteGenerator
from app.services.provider import ProviderService
from app.services.transcriber_config_manager import TranscriberConfigManager
from app.transcriber import model_download_state as dl_state
from app.utils.logger import get_logger
from app.utils.model_status import check_whisper_model_exists, is_downloading
from app.utils.path_helper import get_model_dir

from mcp.server.fastmcp import FastMCP

logger = get_logger(__name__)

# 确保数据库表存在（幂等，init_db 使用 create_all）；空库时预置内置供应商
# （openai/deepseek/qwen/groq/ollama…，固定 id + 正确 base_url + 空 key，用 update_provider 填 key）
init_db()
seed_default_providers()

# 支持生成笔记的平台（与 app/services/constant.py 的 SUPPORT_PLATFORM_MAP 对应）
_PLATFORM_HINTS = [
    ("bilibili", ("bilibili.com", "b23.tv")),
    ("youtube", ("youtube.com", "youtu.be")),
    ("douyin", ("douyin.com",)),
    ("tiktok", ("tiktok.com",)),
    ("kuaishou", ("kuaishou.com", "gifshow.com")),
]
WHISPER_MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"]

mcp = FastMCP("bilinote")

# ---------- 后台任务 ----------

_pool = ThreadPoolExecutor(max_workers=int(os.environ.get("BILINOTE_MAX_WORKERS", "3")))


def _write_status(task_id: str, status, message: Optional[str] = None) -> None:
    """写入 {task_id}.status.json（与上游 NoteGenerator._update_status 兼容）。"""
    data = {"status": status.value if isinstance(status, TaskStatus) else str(status)}
    if message:
        data["message"] = message
    f = NOTE_OUTPUT_DIR / f"{task_id}.status.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(f)


def _absolutize_images(markdown: Optional[str]) -> str:
    """把 Markdown 里相对 /static/screenshots/... 的图片路径改写为 file:// 绝对路径。"""
    if not markdown:
        return markdown
    base = DATA_DIR / "static" / "screenshots"

    def _repl(m):
        try:
            return f"]({(base / m.group(2)).as_uri()})"
        except Exception:
            return m.group(0)

    return re.sub(r"\]\(/?(static/screenshots/[^)]+)\)", _repl, markdown)


def _run_note_task(task_id: str, **params) -> None:
    """在后台线程执行 NoteGenerator.generate，并落盘最终结果。"""
    _write_status(task_id, "INITIALIZING", message="正在准备…")
    try:
        generator = NoteGenerator()
        result = generator.generate(task_id=task_id, **params)
        if result is None:
            # generate() 内部已写 FAILED 状态
            return
        payload = {
            "markdown": result.markdown,
            "transcript": asdict(result.transcript) if result.transcript else None,
            "audio_meta": asdict(result.audio_meta) if result.audio_meta else None,
        }
        # 便携笔记 / 指定输出目录：note.md 若写出，返回其所在目录
        if params.get("notes_dir"):
            note_dir = Path(params["notes_dir"])
            if (note_dir / "note.md").exists():
                payload["note_dir"] = str(note_dir)
        elif "screenshot" in (params.get("_format") or []):
            note_dir = NOTE_OUTPUT_DIR / task_id
            if (note_dir / "note.md").exists():
                payload["note_dir"] = str(note_dir)
        (NOTE_OUTPUT_DIR / f"{task_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"笔记生成成功 task_id={task_id}")
    except Exception as e:
        logger.error(f"任务异常 task_id={task_id}: {e}", exc_info=True)
        _write_status(task_id, TaskStatus.FAILED, message=str(e))


def _detect_platform(url: str) -> str:
    """从 URL / 本地路径识别平台。"""
    u = (url or "").strip().lower()
    if not u:
        raise ValueError("url 为空")
    if u.startswith(("file:", "/", "./", "../", "~/")) or Path(u).expanduser().exists():
        return "local"
    for platform, needles in _PLATFORM_HINTS:
        if any(n in u for n in needles):
            return platform
    raise ValueError(
        f"无法识别视频平台: {url[:80]}（支持 bilibili / youtube / douyin / tiktok / kuaishou / 本地文件路径）"
    )


def _fetch_live_models(provider: Dict) -> Optional[List[str]]:
    """尝试实时请求供应商的 /v1/models 列表。失败返回 None。"""
    r = probe_models(
        provider.get("api_key"),
        provider.get("base_url"),
        name=provider.get("name", ""),
        timeout=15.0,
    )
    if not r["ok"]:
        logger.warning(f"实时拉取模型列表失败（回退到本地数据库）: {r['error']}")
        return None
    return r["models"]


# ---------- MCP 工具 ----------


@mcp.tool()
def generate_note(
    video_url: str,
    platform: Optional[str] = None,
    quality: str = "medium",
    provider_id: Optional[str] = None,
    model_name: Optional[str] = None,
    format: Optional[List[str]] = None,
    style: Optional[str] = None,
    screenshot: bool = False,
    link: bool = False,
    video_understanding: Optional[bool] = None,
    video_interval: Optional[int] = None,
    grid_size: Optional[List[int]] = None,
    notes_dir: Optional[str] = None,
) -> str:
    """提交一个视频链接/本地文件，异步生成 AI Markdown 笔记。

    - video_url: 必填，B 站/YouTube/抖音/快手链接或本地文件路径；
    - platform: 可省略，自动识别；
    - quality: fast / medium / slow；
    - provider_id: LLM 供应商 id（先 list_providers 查看，add_provider 新增）；
    - model_name: 省略时取已配置的默认模型（setup 向导设置），否则取该供应商第一个可用模型；
    - format: 附加内容，如 ["toc","link","screenshot","summary"]；
    - style: 输出风格（minimal/detailed/academic/tutorial/xiaohongshu 等）；
    - video_understanding / video_interval / grid_size: 视频理解（需多模态模型）；不传时用 setup ③ 配置的默认（默认关 / 6s）；显式传入始终覆盖；
    - screenshot + format 含 "screenshot": 插入图片，产出便携笔记 note.md + Assets/（相对引用）；
    - notes_dir: 便携笔记的输出目录（可选；缺省 BILINOTE_NOTES_DIR 环境变量，再缺省 note_results/{task_id}/）。

    返回 {task_id, status, platform}。之后用 get_task_status / wait_for_note 查询结果；
    SUCCESS 时 result.note_dir 指向便携笔记目录。
    """
    if not provider_id:
        raise ValueError("需要 provider_id（先调用 list_providers 查看，或 add_provider 新增 LLM 供应商）")
    if platform is None:
        platform = _detect_platform(video_url)
    if platform == "local" and not Path(video_url).expanduser().exists():
        raise ValueError(f"本地文件不存在: {video_url}")

    try:
        q = DownloadQuality(quality)
    except ValueError:
        raise ValueError(f"quality 必须为 fast / medium / slow，收到: {quality}")

    if not model_name:
        model_name = get_app_config().get(f"default_model:{provider_id}") or ""
    if not model_name:
        models = get_models_by_provider(provider_id)
        if models:
            model_name = models[0]["model_name"]
    if not model_name:
        raise ValueError(
            f"供应商 {provider_id} 还没有可用模型：请先 list_models 查看，或 add_model 添加模型名"
        )

    # 视频理解默认：参数没传（None）时用 setup ③ 配置的默认（默认关 / 0→6s）；
    # 显式传 False/0/具体秒数仍是显式值，覆盖默认
    if video_understanding is None:
        video_understanding = bool(get_app_config().get("video_understanding", False))
    if video_interval is None:
        video_interval = int(get_app_config().get("video_interval") or 0)

    task_id = uuid.uuid4().hex
    _write_status(task_id, TaskStatus.PENDING, message="任务排队中")
    params = dict(
        video_url=video_url,
        platform=platform,
        quality=q,
        model_name=model_name,
        provider_id=provider_id,
        link=link,
        screenshot=screenshot,
        _format=format or [],
        style=style,
        video_understanding=video_understanding,
        video_interval=video_interval,
        grid_size=grid_size or [],
        notes_dir=notes_dir or get_app_config().get("notes_dir") or os.environ.get("BILINOTE_NOTES_DIR") or None,
    )
    _pool.submit(_run_note_task, task_id, **params)
    logger.info(f"已提交任务 task_id={task_id} platform={platform} model={model_name}")
    return json.dumps(
        {"task_id": task_id, "status": "PENDING", "platform": platform, "model_name": model_name},
        ensure_ascii=False,
    )


@mcp.tool()
def get_task_status(task_id: str) -> str:
    """查询笔记生成任务进度。SUCCESS 时 result 含 markdown / transcript / audio_meta。"""
    status_file = NOTE_OUTPUT_DIR / f"{task_id}.status.json"
    if not status_file.exists():
        return json.dumps(
            {"status": "PENDING", "message": "任务排队中", "task_id": task_id, "result": None},
            ensure_ascii=False,
        )
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        data = {"status": "PENDING", "message": "状态文件读取失败"}

    status = data.get("status", "PENDING")
    result = None
    result_file = NOTE_OUTPUT_DIR / f"{task_id}.json"
    if status == "SUCCESS" and result_file.exists():
        try:
            result = json.loads(result_file.read_text(encoding="utf-8"))
            if result and result.get("markdown"):
                result["markdown"] = _absolutize_images(result["markdown"])
        except Exception as e:
            logger.error(f"读取结果文件失败 task_id={task_id}: {e}")

    return json.dumps(
        {
            "status": status,
            "message": data.get("message", ""),
            "task_id": task_id,
            "result": result,
        },
        ensure_ascii=False,
    )


@mcp.tool()
def wait_for_note(task_id: str, timeout: int = 120, poll_interval: int = 3) -> str:
    """阻塞轮询笔记生成任务直到完成（或超时）。长视频可能超过 timeout，可用多次调用续等。

    返回与 get_task_status 相同的结构，SUCCESS 时 result 含最终 Markdown。
    """
    deadline = time.time() + max(1, timeout)
    while time.time() < deadline:
        resp = json.loads(get_task_status(task_id))
        if resp["status"] in ("SUCCESS", "FAILED"):
            return json.dumps(resp, ensure_ascii=False)
        time.sleep(max(1, poll_interval))
    return json.dumps(
        {
            "status": "TIMEOUT",
            "message": f"等待 {timeout}s 仍未完成，可再次调用 wait_for_note / get_task_status 续等",
            "task_id": task_id,
            "result": None,
        },
        ensure_ascii=False,
    )


@mcp.tool()
def list_providers() -> str:
    """列出已配置的 LLM 供应商（id、名称、类型、启用状态、api_key 掩码）。"""
    rows = ProviderService.get_all_providers_safe()
    return json.dumps(rows, ensure_ascii=False)


@mcp.tool()
def add_provider(name: str, api_key: str, base_url: str, type: str) -> str:
    """新增一个 LLM 供应商。type 取值参考：openai / deepseek / qwen / groq / custom。

    添加后建议调用 list_models 确认模型可用，或用 add_model 手动添加模型名。
    """
    if not name or not api_key or not base_url or not type:
        raise ValueError("name / api_key / base_url / type 均必填")
    provider_id = ProviderService.add_provider(
        name=name, api_key=api_key, base_url=base_url, logo="custom", type_=type
    )
    return json.dumps({"id": provider_id, "name": name}, ensure_ascii=False)


@mcp.tool()
def update_provider(
    provider_id: str,
    api_key: Optional[str] = None,
    name: Optional[str] = None,
    base_url: Optional[str] = None,
    enabled: Optional[int] = None,
) -> str:
    """更新 LLM 供应商配置（base_url / name / enabled 等非敏感字段）。

    填 api_key 建议走对话外通道（更安全）：用户在独立终端执行
    `bilinote-mcp providers set <provider_id> --api-key '...'`。
    本工具也接受 api_key（给明确接受 key 经过对话的用户用）；改非敏感字段不受限。
    """
    data = {}
    if api_key is not None:
        data["api_key"] = api_key
    if name is not None:
        data["name"] = name
    if base_url is not None:
        data["base_url"] = base_url
    if enabled is not None:
        data["enabled"] = enabled
    if not data:
        raise ValueError("至少提供 api_key / name / base_url / enabled 之一")
    updated = ProviderService.update_provider(provider_id, data)
    if not updated:
        raise ValueError(f"更新失败：供应商 {provider_id} 不存在")
    return json.dumps({"updated": provider_id, "enabled": updated.get("enabled")}, ensure_ascii=False)


@mcp.tool()
def list_models(provider_id: str) -> str:
    """列出某 LLM 供应商可用的模型。

    优先实时请求供应商的 /v1/models 接口；接口不可用时回退到本地数据库已添加的模型。
    """
    provider = ProviderService.get_provider_by_id(provider_id)
    if not provider:
        raise ValueError(f"供应商不存在: {provider_id}（先 add_provider 新增）")
    live = _fetch_live_models(provider)
    if live:
        return json.dumps({"source": "provider_api", "models": sorted(live)}, ensure_ascii=False)
    db_models = get_models_by_provider(provider_id)
    return json.dumps({"source": "database", "models": db_models}, ensure_ascii=False)


@mcp.tool()
def add_model(provider_id: str, model_name: str) -> str:
    """手动把一个模型名添加为某供应商的可用模型（供应商 /v1/models 接口不可用时用）。"""
    if not model_name:
        raise ValueError("model_name 必填")
    insert_model(provider_id=provider_id, model_name=model_name)
    return json.dumps(
        {"added": True, "provider_id": provider_id, "model_name": model_name}, ensure_ascii=False
    )


@mcp.tool()
def get_transcriber_config() -> str:
    """查看当前转写引擎配置（fast-whisper 本地 / groq / bcut / kuaishou / mlx-whisper 云端）与模型就绪状态。"""
    mgr = TranscriberConfigManager()
    cfg = mgr.get_config()
    ready = mgr.is_model_ready()
    return json.dumps(
        {
            **cfg,
            "ready": ready["ready"],
            "downloading": ready["downloading"],
            "reason": ready["reason"],
        },
        ensure_ascii=False,
    )


@mcp.tool()
def set_transcriber(transcriber_type: str, whisper_model_size: Optional[str] = None) -> str:
    """切换转写引擎。

    transcriber_type: fast-whisper（本地，需下载模型）/ groq（云端）/ bcut / kuaishou / mlx-whisper。
    切到 fast-whisper 时可用 whisper_model_size 指定模型尺寸（tiny/base/small/medium/large-v3）。
    """
    mgr = TranscriberConfigManager()
    cfg = mgr.update_config(transcriber_type, whisper_model_size)
    return json.dumps(cfg, ensure_ascii=False)


@mcp.tool()
def list_transcriber_models() -> str:
    """列出本地 whisper 模型（fast-whisper）的下载状态。"""
    rows = []
    for size in WHISPER_MODEL_SIZES:
        downloaded = check_whisper_model_exists(size, "whisper")
        state = dl_state.get_status(size) or ("done" if downloaded else "none")
        rows.append({"size": size, "downloaded": downloaded, "state": state})
    return json.dumps({"whisper_models": rows}, ensure_ascii=False)


@mcp.tool()
def download_transcriber_model(model_size: str, transcriber_type: str = "fast-whisper") -> str:
    """在后台下载 whisper 模型（仅本地引擎需要）。下载中/完成后用 list_transcriber_models 查询。"""
    size = model_size.strip().lower()
    if transcriber_type == "fast-whisper":
        key = size

        def _dl():
            try:
                dl_state.mark_downloading(key)
                from app.transcriber.whisper_models import resolve_whisper_model
                from faster_whisper import WhisperModel

                target = resolve_whisper_model(size)
                WhisperModel(
                    model_size_or_path=target,
                    device="cpu",
                    compute_type="int8",
                    download_root=get_model_dir("whisper"),
                )
                dl_state.mark_done(key)
                logger.info(f"whisper 模型 {size} 下载完成")
            except Exception as e:
                dl_state.mark_failed(key, str(e))
                logger.error(f"whisper 模型 {size} 下载失败: {e}", exc_info=True)

        _pool.submit(_dl)
        return json.dumps(
            {"started": True, "model_size": size, "transcriber_type": "fast-whisper"},
            ensure_ascii=False,
        )

    if transcriber_type == "mlx-whisper":
        if not (sys.platform == "darwin"):
            raise ValueError("mlx-whisper 仅在 macOS 可用，请改用 fast-whisper")

        def _dl_mlx():
            try:
                dl_state.mark_downloading(f"mlx-{size}")
                from app.transcriber.mlx_whisper_transcriber import MLX_MODEL_MAP
                from huggingface_hub import snapshot_download

                repo_id = MLX_MODEL_MAP.get(size)
                if not repo_id:
                    raise ValueError(f"未找到 mlx 模型映射: {size}")
                snapshot_download(
                    repo_id=repo_id,
                    local_dir=os.path.join(get_model_dir("mlx-whisper"), repo_id),
                )
                dl_state.mark_done(f"mlx-{size}")
            except Exception as e:
                dl_state.mark_failed(f"mlx-{size}", str(e))
                logger.error(f"mlx 模型 {size} 下载失败: {e}", exc_info=True)

        _pool.submit(_dl_mlx)
        return json.dumps(
            {"started": True, "model_size": size, "transcriber_type": "mlx-whisper"},
            ensure_ascii=False,
        )

    raise ValueError(f"仅支持本地模型下载：fast-whisper / mlx-whisper，收到: {transcriber_type}")


@mcp.tool()
def health_check() -> str:
    """检查 MCP 运行环境：FFmpeg、数据库、转写器配置与本地 whisper 模型就绪状态。"""
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    db_ok, db_err = True, ""
    try:
        with get_engine().connect():
            pass
    except Exception as e:
        db_ok, db_err = False, str(e)

    cfg = TranscriberConfigManager().get_config()
    ready = TranscriberConfigManager().is_model_ready()
    models = [
        {"size": s, "downloaded": check_whisper_model_exists(s, "whisper")}
        for s in WHISPER_MODEL_SIZES
    ]
    return json.dumps(
        {
            "ffmpeg": "ok" if ffmpeg_ok else "missing",
            "db": "ok" if db_ok else f"error: {db_err}",
            "transcriber": {
                **cfg,
                "ready": ready["ready"],
                "downloading": ready["downloading"],
                "reason": ready["reason"],
            },
            "whisper_models": models,
            "data_dir": str(DATA_DIR),
        },
        ensure_ascii=False,
    )


@mcp.tool()
def validate_url(url: str) -> str:
    """判断视频链接属于哪个平台，以及是否受支持。

    支持：bilibili（含 b23.tv）、youtube（含 youtu.be）、douyin、tiktok、kuaishou、本地文件路径。
    """
    try:
        platform = _detect_platform(url)
        return json.dumps(
            {"supported": True, "platform": platform, "reason": f"识别为 {platform}"},
            ensure_ascii=False,
        )
    except ValueError as e:
        return json.dumps({"supported": False, "reason": str(e)}, ensure_ascii=False)


@mcp.tool()
def set_downloader_cookie(platform: str, cookie: str) -> str:
    """设置平台下载 Cookie（如 bilibili 的 SESSDATA），用于下载需登录/会员的内容。"""
    if not platform or not cookie:
        raise ValueError("platform / cookie 均必填")
    CookieConfigManager().set(platform, cookie)
    return json.dumps({"saved": True, "platform": platform}, ensure_ascii=False)


# ---------- 入口 ----------


def main() -> None:
    """MCP server 入口。CLI（providers）由 bilinote_mcp.cli:main 分发，本函数只跑 MCP stdio。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    init_db()
    try:
        import events

        events.register_handler()
        logger.info("已注册转写完成清理事件")
    except Exception as e:
        logger.warning(f"注册事件监听器失败: {e}")
    logger.info(f"BiliNote-Mcp 启动 | 数据目录: {DATA_DIR}")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
