"""bilinote-mcp 命令行入口（console script 指向本模块的 main）。

- `bilinote-mcp providers ...` → 轻量 CLI：只导入 provider 相关模块
  （不加载下载器/转写器，启动快、无 import 噪音），在终端直接管理 LLM 供应商。
- 其余参数（含无参数，MCP stdio 模式）→ 懒加载并启动完整 MCP server。

API key 的设计原则：key 由用户在独立终端写入（不经过 agent 对话，
避免泄露给 agent 的 LLM 上游），见 README「安全说明」。
"""
import argparse
import builtins
import json
import os
import sys

from bilinote_mcp.config import get_app_config, set_app_config, setup_environment

# 轻量 CLI 不该被 import 时的裸 print 污染 stdout，先进程级重定向到 stderr
_orig_print = builtins.print


def _print_to_stderr(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    _orig_print(*args, **kwargs)


builtins.print = _print_to_stderr

DATA_DIR = setup_environment()

# 只导入 provider 相关（不触发 app.downloaders / app.transcriber 的 import 噪音）
from app.db.init_db import init_db
from app.db.provider_dao import seed_default_providers
from app.services.provider import ProviderService
from app.services.transcriber_config_manager import TranscriberConfigManager

init_db()
seed_default_providers()

_BUILTIN_PROVIDERS = {
    "1": ("deepseek", "DeepSeek", "https://api.deepseek.com"),
    "2": ("openai", "OpenAI", "https://api.openai.com/v1"),
    "3": ("qwen", "Qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "4": ("groq", "Groq", "https://api.groq.com/openai/v1"),
    "5": ("ollama", "Ollama（本地免费，无需 key）", "http://127.0.0.1:11434/v1"),
}
_WHISPER_SIZES = ("tiny", "base", "small", "medium", "large-v3", "large-v3-turbo")


def _ask(prompt: str, default: str = "") -> str:
    """交互式提问；非交互环境（管道）下返回默认值。"""
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{prompt}{suffix}: ")
    except EOFError:
        return default
    val = val.strip()
    return val or default


def _ask_secret(prompt: str) -> str:
    """隐藏输入的 API key（不经任何对话/日志）。"""
    import getpass

    try:
        return getpass.getpass(f"{prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _tqdm_bar():
    """构造带统一格式的 tqdm 类（snapshot_download 的 tqdm_class 用）。"""
    from tqdm import tqdm

    class _Bar(tqdm):
        def __init__(self, *a, **k):
            k.setdefault("bar_format", "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
            super().__init__(*a, **k)

    return _Bar


def _download_whisper(size: str) -> None:
    """在终端下载 fast-whisper 模型（阻塞，带进度条）。"""
    from app.transcriber.whisper_models import is_local_target, resolve_whisper_model
    from app.utils.path_helper import get_model_dir
    from huggingface_hub import snapshot_download

    target = resolve_whisper_model(size)
    model_dir = get_model_dir("whisper")
    if is_local_target(target):
        print(f"（{target} 为本地路径，无需下载）", file=sys.stdout)
        return
    print(f"正在下载 whisper-{size}（{target}）…", file=sys.stdout)
    snapshot_download(repo_id=target, cache_dir=model_dir, tqdm_class=_tqdm_bar())
    # 让 faster-whisper 真正加载（确认模型可用）
    from faster_whisper import WhisperModel

    WhisperModel(model_size_or_path=target, device="cpu", compute_type="int8", download_root=model_dir)
    print(f"✓ whisper-{size} 下载完成", file=sys.stdout)


def _download_mlx_model(size: str) -> None:
    """在终端下载 mlx-whisper 模型（仅 macOS，阻塞，带进度条）。"""
    try:
        from app.transcriber.mlx_whisper_transcriber import MLX_MODEL_MAP
    except ImportError:
        raise RuntimeError(
            "mlx-whisper 未安装：请用 `uv tool install --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp --with mlx-whisper`"
            "（或 `uvx --from ... --with mlx-whisper`）安装后重试"
        )
    from app.utils.path_helper import get_model_dir
    from huggingface_hub import snapshot_download

    repo_id = MLX_MODEL_MAP.get(size)
    if not repo_id:
        raise ValueError(f"未找到 mlx 模型映射: {size}（可选: {', '.join(MLX_MODEL_MAP.keys())}）")
    print(f"正在下载 mlx-whisper-{size}（{repo_id}）…", file=sys.stdout)
    snapshot_download(
        repo_id=repo_id,
        local_dir=os.path.join(get_model_dir("mlx-whisper"), repo_id),
        tqdm_class=_tqdm_bar(),
    )
    print(f"✓ mlx-whisper-{size} 下载完成", file=sys.stdout)


# 交互配色（ANSI）
_CYAN = "\033[1;36m"
_YELLOW = "\033[1;33m"
_GREEN = "\033[1;32m"
_DIM = "\033[2m"
_RESET = "\033[0m"
# 让「← 左键」= interrupt（返回上一层，与 Ctrl-C 同）；InquirerPy 绑定需带 key 字段、
# action 必须是已注册的（interrupt / answer / skip 等）
_KB = {"interrupt": [{"key": "left"}]}


def _show_header(section: str = "") -> None:
    """清屏并重绘标题，避免历史信息堆积。"""
    print("\033[2J\033[H", end="", file=sys.stdout)
    print(f"{_CYAN}⚙  BiliNote-MCP 配置向导{_RESET}  {_DIM}↑↓ 选择 · 回车确认 · ← 返回 · Ctrl-C 退出{_RESET}", file=sys.stdout)
    if section:
        print(f"{_YELLOW}▶ {section}{_RESET}", file=sys.stdout)
    print("", file=sys.stdout)


def _setup_cli() -> None:
    """交互式配置向导：主菜单 + 各配置区，方向键选择、左键返回、随时可反复进入修改。"""
    try:
        from InquirerPy import inquirer
    except ImportError:
        print("（未安装 InquirerPy，使用纯文本提示；`uv sync` 后可启用方向键/高亮选择）", file=sys.stderr)
        _setup_cli_fallback()
        return
    _show_header()
    print("    API key 为隐藏输入，不经过 agent 对话。", file=sys.stdout)
    try:
        _wizard(inquirer)
    except (EOFError, KeyboardInterrupt):
        print(f"{_GREEN}✔ 已退出{_RESET}", file=sys.stdout)


def _wizard(inq) -> None:
    while True:
        _show_header()
        choice = inq.select(
            message="选择要配置的项目",
            choices=[
                {"name": "① LLM 供应商（填 key / 改 base_url / 新增）", "value": "llm"},
                {"name": "② 语音转写引擎（选引擎 / 模型尺寸 / 下载）", "value": "transcriber"},
                {"name": "③ 其他（平台 Cookie / 默认笔记位置）", "value": "other"},
                {"name": "✔ 完成 / 退出", "value": "exit"},
            ],
            default="llm",
            keybindings=_KB,
        ).execute()
        if choice == "llm":
            _wizard_llm(inq)
        elif choice == "transcriber":
            _wizard_transcriber(inq)
        elif choice == "other":
            _wizard_other(inq)
        else:
            print(f"{_GREEN}✔ 配置完成。验证：`bilinote-mcp providers list`、`bilinote-mcp transcriber list`{_RESET}", file=sys.stdout)
            return


def _wizard_llm(inq) -> None:
    try:
        while True:
            _show_header("① LLM 供应商")
            provs = ProviderService.get_all_providers_safe()
            choices = [
                {
                    "name": f"{p['id']:<10} {p['name']:<12} key={'✓已填' if p['api_key'] else '空'}  {p['base_url']}",
                    "value": ("edit", p["id"]),
                }
                for p in provs
            ]
            choices += [
                {"name": "＋ 新增供应商（中转站/自建）", "value": ("add", None)},
                {"name": "← 返回主菜单", "value": ("back", None)},
            ]
            pick = inq.select(message="选择要编辑的供应商（← 返回）", choices=choices, keybindings=_KB).execute()
            if pick[0] == "back":
                return
            if pick[0] == "add":
                _show_header("新增供应商")
                name = inq.text(message="供应商名称", keybindings=_KB).execute()
                base_url = inq.text(message="base_url（如 https://relay.example.com/v1）", keybindings=_KB).execute()
                key = inq.secret(message="API key（隐藏输入）", keybindings=_KB).execute()
                if name and base_url and key:
                    new_id = ProviderService.add_provider(name=name, api_key=key, base_url=base_url, logo="custom", type_="custom")
                    print(f"{_GREEN}✓ 已新增 {name} → id={new_id}{_RESET}", file=sys.stdout)
                else:
                    print(f"{_YELLOW}⚠ 信息不完整，未新增{_RESET}", file=sys.stdout)
                continue
            pid = pick[1]
            _show_header(f"编辑供应商 {pid}")
            key = inq.secret(message="新的 API key（直接回车保持不变）", keybindings=_KB).execute()
            if key:
                ProviderService.update_provider(pid, {"api_key": key})
                print(f"{_GREEN}✓ 已更新 {pid} 的 key{_RESET}", file=sys.stdout)
            base_url = inq.text(message="base_url（直接回车保持不变）", keybindings=_KB).execute()
            if base_url:
                ProviderService.update_provider(pid, {"base_url": base_url})
    except KeyboardInterrupt:
        return  # 左键/Ctrl-C → 返回主菜单


def _wizard_transcriber(inq) -> None:
    try:
        while True:
            cfg = TranscriberConfigManager().get_config()
            cur = f"{cfg['transcriber_type']} / {cfg['whisper_model_size']}"
            _show_header("② 语音转写引擎")
            cur_engine = cfg["transcriber_type"]
            choices = []
            for val, base in (
                ("fast-whisper", "fast-whisper（本地）"),
                ("groq", "groq（云端，需 key）"),
                ("bcut", "bcut（云端）"),
                ("kuaishou", "kuaishou（云端）"),
                ("mlx-whisper", "mlx-whisper（仅 macOS，GPU）"),
            ):
                # 注意：InquirerPy 选择项 name 里不能嵌 ANSI 转义码（会原样显示），用纯文本
                if val == cur_engine:
                    mark = "  ✓ 当前"
                    if val in ("fast-whisper", "mlx-whisper"):
                        mark += f"  尺寸 {cfg['whisper_model_size']}"
                else:
                    mark = ""
                choices.append({"name": base + mark, "value": val})
            choices.append({"name": "← 返回主菜单", "value": "back"})
            pick = inq.select(
                message=f"当前引擎：{cur}",
                choices=choices,
                default=cur_engine if cur_engine in ("fast-whisper", "groq", "bcut", "kuaishou", "mlx-whisper") else "fast-whisper",
                keybindings=_KB,
            ).execute()
            if pick == "back":
                return
            if pick in ("fast-whisper", "mlx-whisper"):
                _show_header(f"选择 {pick} 模型尺寸")
                sizes = [{"name": s, "value": s} for s in _WHISPER_SIZES]
                sizes.append({"name": "← 取消", "value": "back"})
                size = inq.select(message="模型尺寸", choices=sizes, default=cfg["whisper_model_size"], keybindings=_KB).execute()
                if size == "back":
                    continue
                TranscriberConfigManager().update_config(pick, size)
                print(f"{_GREEN}✓ 已切换 {pick} / {size}{_RESET}", file=sys.stdout)
                # 本地引擎：检查模型是否已下载，未下载则询问是否现在下载
                from app.utils.model_status import check_mlx_whisper_model_exists, check_whisper_model_exists

                if pick == "fast-whisper":
                    downloaded = check_whisper_model_exists(size, "whisper")
                    dl_fn = lambda: _download_whisper(size)
                    label = f"whisper-{size}"
                    mlx_missing = False
                else:  # mlx-whisper
                    # mlx-whisper 是可选依赖；未安装时给出明确指引，并主动问是否改用 fast-whisper
                    try:
                        from app.transcriber.mlx_whisper_transcriber import MLX_MODEL_MAP  # noqa: F401
                        mlx_missing = False
                    except ImportError:
                        mlx_missing = True
                    if mlx_missing:
                        print(
                            f"{_YELLOW}⚠ 当前环境未装 mlx-whisper（可选依赖）。{_RESET}"
                            f"{_DIM}想用 mlx：`uv tool install --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp --with mlx-whisper`，"
                            f"或用 `uvx --from ... --with mlx-whisper` 运行。{_RESET}",
                            file=sys.stdout,
                        )
                        if inq.confirm(message="改用 fast-whisper（当前环境可用）？", default=True, keybindings=_KB).execute():
                            TranscriberConfigManager().update_config("fast-whisper", size)
                            pick, mlx_missing = "fast-whisper", False
                            downloaded = check_whisper_model_exists(size, "whisper")
                            dl_fn = lambda: _download_whisper(size)
                            label = f"whisper-{size}"
                        else:
                            continue  # 回引擎选择
                    else:
                        downloaded = check_mlx_whisper_model_exists(size)
                        dl_fn = lambda: _download_mlx_model(size)
                        label = f"mlx-whisper-{size}"
                if downloaded:
                    print(f"{_DIM}（{label} 已下载，无需再下）{_RESET}", file=sys.stdout)
                elif inq.confirm(message=f"本地模型 {label} 尚未下载，现在下载？（约几十MB~数GB）", default=False, keybindings=_KB).execute():
                    # 专门的下载界面：进度条 + 完成后停留，避免立刻跳回
                    _show_header(f"下载 {label}")
                    print("", file=sys.stdout)
                    try:
                        dl_fn()
                        print(f"{_GREEN}✓ {label} 下载完成{_RESET}", file=sys.stdout)
                    except Exception as e:
                        print(f"{_YELLOW}⚠ 下载失败：{e}（可稍后 `bilinote-mcp transcriber download {size}` 重试）{_RESET}", file=sys.stdout)
                    try:
                        input("（按回车返回）", )
                    except (EOFError, KeyboardInterrupt):
                        pass
            else:
                TranscriberConfigManager().update_config(pick)
                print(f"{_GREEN}✓ 已切换 {pick}{_RESET}", file=sys.stdout)
    except KeyboardInterrupt:
        return  # 左键/Ctrl-C → 返回主菜单


def _wizard_other(inq) -> None:
    try:
        while True:
            from app.services.cookie_manager import CookieConfigManager

            notes_dir = get_app_config().get("notes_dir") or os.environ.get("BILINOTE_NOTES_DIR") or "（默认 note_results/{task_id}/）"
            _show_header("③ 其他设置")
            pick = inq.select(
                message="选择要配置的项（← 返回）",
                choices=[
                    {"name": "平台 Cookie（B 站等需登录内容）", "value": "cookie"},
                    {"name": f"默认笔记位置（图片模式）：{notes_dir}", "value": "notes"},
                    {"name": "← 返回主菜单", "value": "back"},
                ],
                keybindings=_KB,
            ).execute()
            if pick == "back":
                return
            if pick == "cookie":
                _show_header("平台 Cookie")
                platform = inq.select(
                    message="平台",
                    choices=[
                        {"name": "bilibili", "value": "bilibili"},
                        {"name": "youtube", "value": "youtube"},
                        {"name": "douyin", "value": "douyin"},
                        {"name": "kuaishou", "value": "kuaishou"},
                        {"name": "其他（手动输入）", "value": "other"},
                        {"name": "← 返回", "value": "back"},
                    ],
                    keybindings=_KB,
                ).execute()
                if platform == "back":
                    continue
                if platform == "other":
                    platform = inq.text(message="平台名", keybindings=_KB).execute()
                cookie = inq.secret(message=f"{platform} 的 Cookie 值（留空取消）", keybindings=_KB).execute()
                if platform and cookie:
                    CookieConfigManager().set(platform, cookie)
                    print(f"{_GREEN}✓ 已保存 {platform} 的 Cookie{_RESET}", file=sys.stdout)
                else:
                    print(f"{_YELLOW}⚠ 未保存（平台或 Cookie 为空）{_RESET}", file=sys.stdout)
            elif pick == "notes":
                cur = get_app_config().get("notes_dir") or "（默认）"
                _show_header("默认笔记位置")
                new_dir = inq.text(message=f"当前：{cur}。输入新目录（留空=保持默认）", keybindings=_KB).execute()
                if new_dir:
                    set_app_config("notes_dir", new_dir)
                    print(f"{_GREEN}✓ 已保存默认笔记位置：{new_dir}{_RESET}", file=sys.stdout)
    except KeyboardInterrupt:
        return  # 左键/Ctrl-C → 返回主菜单


def _setup_cli_fallback() -> None:
    """无 InquirerPy 时的纯文本兜底向导（同功能，输入编号选择）。"""
    print("=== BiliNote-MCP 配置（纯文本模式） ===", file=sys.stdout)

    provs = ProviderService.get_all_providers_safe()
    if provs:
        print("\n① LLM 供应商（当前）：", file=sys.stdout)
        for i, p in enumerate(provs, 1):
            print(f"   {i}) {p['id']}  key={'已填' if p['api_key'] else '空'}  {p['base_url']}", file=sys.stdout)
        sel = _ask("   选择要编辑的 [1-%d]，0 跳过" % len(provs), default="0")
        if sel.isdigit() and 1 <= int(sel) <= len(provs):
            pid = provs[int(sel) - 1]["id"]
            key = _ask_secret(f"   新的 API key（{pid}，留空不变）")
            if key:
                ProviderService.update_provider(pid, {"api_key": key})
                print(f"   ✓ 已更新 {pid} 的 key", file=sys.stdout)
    if _ask("   新增中转站/自建供应商？[y/N]", default="N").lower() == "y":
        name = _ask("   供应商名称", default="我的中转站")
        base_url = _ask("   base_url")
        key = _ask_secret("   API key")
        if name and base_url and key:
            new_id = ProviderService.add_provider(name=name, api_key=key, base_url=base_url, logo="custom", type_="custom")
            print(f"   ✓ 已新增 → id={new_id}", file=sys.stdout)

    print("\n② 语音转写引擎：", file=sys.stdout)
    print("   1) fast-whisper  2) groq  3) bcut  4) kuaishou  5) mlx-whisper", file=sys.stdout)
    t = _ask("   选择 [1-5]", default="1")
    engines = ("fast-whisper", "groq", "bcut", "kuaishou", "mlx-whisper")
    eng = engines[int(t) - 1] if t.isdigit() and 1 <= int(t) <= 5 else "fast-whisper"
    size = None
    if eng in ("fast-whisper", "mlx-whisper"):
        size = _ask("   模型尺寸（tiny/base/small/medium/large-v3/large-v3-turbo）", default="small")
        if size not in _WHISPER_SIZES:
            size = "small"
    TranscriberConfigManager().update_config(eng, size)
    print(f"   ✓ 已切换 {eng} / {size}", file=sys.stdout)
    if eng == "fast-whisper" and _ask(f"   下载 whisper-{size}？[y/N]", default="N").lower() == "y":
        try:
            _download_whisper(size)
        except Exception as e:
            print(f"   ⚠ 下载失败：{e}", file=sys.stdout)

    print("\n=== 配置完成 ===", file=sys.stdout)


def _providers_cli(argv) -> None:
    parser = argparse.ArgumentParser(
        prog="bilinote-mcp providers",
        description="在终端管理 LLM 供应商（key 不经过 agent 对话，避免泄露给 agent 的 LLM 上游）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出供应商（key 掩码）")
    p_set = sub.add_parser("set", help="给供应商填 key / base_url / name")
    p_set.add_argument("provider_id")
    p_set.add_argument("--api-key", help="API key")
    p_set.add_argument("--base-url", help="base_url")
    p_set.add_argument("--name", help="显示名")
    p_add = sub.add_parser("add", help="新增供应商（如中转站）")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--api-key", required=True)
    p_add.add_argument("--base-url", required=True)
    p_add.add_argument("--type", default="custom")

    opts = parser.parse_args(argv)
    if opts.cmd == "list":
        rows = ProviderService.get_all_providers_safe()
        if not rows:
            print("（暂无供应商，可先启动一次 MCP 自动预置内置供应商）", file=sys.stdout)
            return
        for p in rows:
            key = f"已填 {p['api_key']}" if p["api_key"] else "空"
            print(f"{p['id']:10} {p['name']:12} key={key}  base_url={p['base_url']}", file=sys.stdout)
    elif opts.cmd == "set":
        data = {}
        if opts.api_key is not None:
            data["api_key"] = opts.api_key
        if opts.base_url is not None:
            data["base_url"] = opts.base_url
        if opts.name is not None:
            data["name"] = opts.name
        if not data:
            parser.error("至少提供 --api-key / --base-url / --name 之一")
        updated = ProviderService.update_provider(opts.provider_id, data)
        if not updated:
            print(f"更新失败：供应商 {opts.provider_id} 不存在", file=sys.stderr)
            sys.exit(1)
        print(f"已更新 {opts.provider_id} (enabled={updated.get('enabled')})", file=sys.stdout)
    elif opts.cmd == "add":
        new_id = ProviderService.add_provider(
            name=opts.name, api_key=opts.api_key, base_url=opts.base_url, logo="custom", type_=opts.type
        )
        print(f"已新增 {opts.name} → id={new_id}", file=sys.stdout)


_TRANSCRIBER_ENGINES = ("fast-whisper", "groq", "bcut", "kuaishou", "mlx-whisper")


def _transcriber_cli(argv) -> None:
    """`bilinote-mcp transcriber ...`：在终端管理语音转写引擎。"""
    parser = argparse.ArgumentParser(
        prog="bilinote-mcp transcriber",
        description="在终端管理语音转写引擎（fast-whisper 本地 / groq / bcut / kuaishou / mlx-whisper）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="查看当前转写引擎与就绪状态")
    p_set = sub.add_parser("set", help="切换转写引擎")
    p_set.add_argument("engine", choices=_TRANSCRIBER_ENGINES)
    p_set.add_argument("--size", help="whisper 模型尺寸（tiny/base/small/medium/large-v3）")
    p_dl = sub.add_parser("download", help="下载本地 whisper 模型")
    p_dl.add_argument("size", choices=_WHISPER_SIZES)
    p_dl.add_argument("--engine", default="fast-whisper", choices=("fast-whisper", "mlx-whisper"), help="fast-whisper（默认）或 mlx-whisper（macOS）")

    opts = parser.parse_args(argv)
    mgr = TranscriberConfigManager()
    if opts.cmd == "list":
        cfg = mgr.get_config()
        ready = mgr.is_model_ready()
        print(f"当前引擎: {cfg['transcriber_type']} / {cfg['whisper_model_size']}", file=sys.stdout)
        print(f"就绪: {'✓ ready' if ready['ready'] else '✗ ' + ready['reason']}", file=sys.stdout)
        print(f"可选引擎: {', '.join(_TRANSCRIBER_ENGINES)}", file=sys.stdout)
        print(f"whisper 尺寸: {', '.join(_WHISPER_SIZES)}", file=sys.stdout)
    elif opts.cmd == "set":
        if opts.engine in ("fast-whisper", "mlx-whisper") and not opts.size:
            opts.size = "small"
        cfg = mgr.update_config(opts.engine, opts.size)
        print(f"已切换: {cfg['transcriber_type']} / {cfg['whisper_model_size']}", file=sys.stdout)
        if opts.engine == "fast-whisper":
            print(f"（本地模型还需下载：bilinote-mcp transcriber download {cfg['whisper_model_size']}）", file=sys.stdout)
    elif opts.cmd == "download":
        try:
            if opts.engine == "mlx-whisper":
                _download_mlx_model(opts.size)
            else:
                _download_whisper(opts.size)
        except Exception as e:
            print(f"✗ 下载失败: {e}（可稍后重试或换小尺寸）", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    """入口：providers / setup / transcriber 走轻量 CLI；**无参数**时才是 MCP server（stdio）。"""
    known = ("providers", "setup", "transcriber")
    if len(sys.argv) > 1 and sys.argv[1] in known:
        if sys.argv[1] == "providers":
            _providers_cli(sys.argv[2:])
        elif sys.argv[1] == "setup":
            _setup_cli()
        else:
            _transcriber_cli(sys.argv[2:])
        return
    if len(sys.argv) > 1:
        # 未知参数（如 uvx 选项写错位置）→ 报错而不是静默启动 MCP server
        print(f"未知子命令: {sys.argv[1]}", file=sys.stderr)
        print(f"用法: bilinote-mcp {' | '.join(known)} ...", file=sys.stderr)
        print("（MCP server 模式由客户端无参数启动，不要手动传参）", file=sys.stderr)
        sys.exit(2)
    # MCP 模式（无参数，stdio 客户端启动）：懒加载完整流水线（server.py）
    from bilinote_mcp.server import main as _server_main

    _server_main()


if __name__ == "__main__":
    main()
