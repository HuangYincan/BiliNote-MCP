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

from bilinote_mcp.config import setup_environment

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


def _download_whisper(size: str) -> None:
    """在终端下载 fast-whisper 模型（阻塞）。"""
    from app.transcriber.whisper_models import resolve_whisper_model
    from faster_whisper import WhisperModel
    from app.utils.path_helper import get_model_dir

    print(f"正在下载 whisper-{size}（首次约几十MB~数GB，请稍候）…", file=sys.stdout)
    WhisperModel(
        model_size_or_path=resolve_whisper_model(size),
        device="cpu", compute_type="int8",
        download_root=get_model_dir("whisper"),
    )
    print(f"✓ whisper-{size} 下载完成", file=sys.stdout)


def _setup_cli() -> None:
    """交互式配置向导：主菜单 + 各配置区，方向键选择、可随时返回，可反复运行修改配置。"""
    try:
        from InquirerPy import inquirer
    except ImportError:
        print("（未安装 InquirerPy，使用纯文本提示；`uv sync` 后可启用方向键/高亮选择）", file=sys.stderr)
        _setup_cli_fallback()
        return
    print("⚙  BiliNote-MCP 配置向导（↑↓ 选择 / 回车确认 / 随时 Ctrl-C 退出，可反复进入修改）", file=sys.stdout)
    print("    API key 为隐藏输入，不经过 agent 对话。", file=sys.stdout)
    try:
        _wizard(inquirer)
    except (EOFError, KeyboardInterrupt):
        print("（已取消）", file=sys.stdout)


def _wizard(inq) -> None:
    while True:
        choice = inq.select(
            message="选择要配置的项目",
            choices=[
                {"name": "① LLM 供应商（填 key / 改 base_url / 新增）", "value": "llm"},
                {"name": "② 语音转写引擎（选引擎 / 模型尺寸 / 下载）", "value": "transcriber"},
                {"name": "③ 其他（平台 Cookie / 默认笔记位置）", "value": "other"},
                {"name": "✔ 完成 / 退出", "value": "exit"},
            ],
            default="llm",
        ).execute()
        if choice == "llm":
            _wizard_llm(inq)
        elif choice == "transcriber":
            _wizard_transcriber(inq)
        elif choice == "other":
            _wizard_other(inq)
        else:
            print("✔ 配置完成。验证：`bilinote-mcp providers list`、`bilinote-mcp transcriber list`", file=sys.stdout)
            return


def _wizard_llm(inq) -> None:
    while True:
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
        pick = inq.select(message="LLM 供应商（选择一个编辑；key 掩码显示）", choices=choices).execute()
        if pick[0] == "back":
            return
        if pick[0] == "add":
            name = inq.text(message="供应商名称").execute()
            base_url = inq.text(message="base_url（如 https://relay.example.com/v1）").execute()
            key = inq.secret(message="API key（隐藏输入）").execute()
            if name and base_url and key:
                new_id = ProviderService.add_provider(name=name, api_key=key, base_url=base_url, logo="custom", type_="custom")
                print(f"✓ 已新增 {name} → id={new_id}", file=sys.stdout)
            else:
                print("⚠ 信息不完整，未新增", file=sys.stdout)
            continue
        pid = pick[1]
        key = inq.secret(message=f"新的 API key（{pid}，直接回车保持不变）").execute()
        if key:
            ProviderService.update_provider(pid, {"api_key": key})
            print(f"✓ 已更新 {pid} 的 key", file=sys.stdout)
        base_url = inq.text(message=f"base_url（{pid}，直接回车保持不变）").execute()
        if base_url:
            ProviderService.update_provider(pid, {"base_url": base_url})


def _wizard_transcriber(inq) -> None:
    while True:
        cfg = TranscriberConfigManager().get_config()
        cur = f"{cfg['transcriber_type']} / {cfg['whisper_model_size']}"
        pick = inq.select(
            message=f"语音转写引擎（当前：{cur}）",
            choices=[
                {"name": f"fast-whisper（本地）   当前尺寸 {cfg['whisper_model_size']}", "value": "fast-whisper"},
                {"name": "groq（云端，需 key）", "value": "groq"},
                {"name": "bcut（云端）", "value": "bcut"},
                {"name": "kuaishou（云端）", "value": "kuaishou"},
                {"name": "mlx-whisper（仅 macOS，GPU）", "value": "mlx-whisper"},
                {"name": "← 返回主菜单", "value": "back"},
            ],
            default=cfg["transcriber_type"] if cfg["transcriber_type"] in ("fast-whisper", "groq", "bcut", "kuaishou", "mlx-whisper") else "fast-whisper",
        ).execute()
        if pick == "back":
            return
        if pick in ("fast-whisper", "mlx-whisper"):
            sizes = [{"name": s, "value": s} for s in _WHISPER_SIZES]
            sizes.append({"name": "← 取消", "value": "back"})
            size = inq.select(message=f"{pick} 模型尺寸", choices=sizes, default=cfg["whisper_model_size"]).execute()
            if size == "back":
                continue
            TranscriberConfigManager().update_config(pick, size)
            print(f"✓ 已切换 {pick} / {size}", file=sys.stdout)
            if pick == "fast-whisper":
                if inq.confirm(message=f"现在下载 whisper-{size}？（约几十MB~数GB）", default=False).execute():
                    try:
                        _download_whisper(size)
                    except Exception as e:
                        print(f"⚠ 下载失败：{e}（可稍后 `bilinote-mcp transcriber download {size}` 重试）", file=sys.stdout)
        else:
            TranscriberConfigManager().update_config(pick)
            print(f"✓ 已切换 {pick}", file=sys.stdout)


def _wizard_other(inq) -> None:
    while True:
        from app.services.cookie_manager import CookieConfigManager

        notes_dir = os.environ.get("BILINOTE_NOTES_DIR") or "（默认 note_results/{task_id}/）"
        pick = inq.select(
            message="其他设置",
            choices=[
                {"name": "平台 Cookie（B 站等需登录内容）", "value": "cookie"},
                {"name": f"默认笔记位置（图片模式）：{notes_dir}", "value": "notes"},
                {"name": "← 返回主菜单", "value": "back"},
            ],
        ).execute()
        if pick == "back":
            return
        if pick == "cookie":
            platform = inq.text(message="平台（bilibili / youtube / douyin / kuaishou）").execute()
            cookie = inq.secret(message="Cookie 值").execute()
            if platform and cookie:
                CookieConfigManager().set(platform, cookie)
                print(f"✓ 已保存 {platform} 的 Cookie", file=sys.stdout)
            else:
                print("⚠ 未保存（平台或 Cookie 为空）", file=sys.stdout)
        elif pick == "notes":
            new_dir = inq.text(message="默认笔记目录（直接回车=用默认）。改后需在 shell 配置持久化 BILINOTE_NOTES_DIR").execute()
            if new_dir:
                os.environ["BILINOTE_NOTES_DIR"] = new_dir
                print(f"✓ 本次已设 BILINOTE_NOTES_DIR={new_dir}", file=sys.stdout)


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
    p_dl = sub.add_parser("download", help="下载本地 whisper 模型（fast-whisper）")
    p_dl.add_argument("size", choices=_WHISPER_SIZES)

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
            _download_whisper(opts.size)
        except Exception as e:
            print(f"✗ 下载失败: {e}（可稍后重试或换小尺寸）", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    """入口：providers / setup / transcriber 走轻量 CLI，其余进入 MCP server（stdio）。"""
    if len(sys.argv) > 1 and sys.argv[1] == "providers":
        _providers_cli(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        _setup_cli()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "transcriber":
        _transcriber_cli(sys.argv[2:])
        return
    # MCP 模式：懒加载完整流水线（server.py）
    from bilinote_mcp.server import main as _server_main

    _server_main()


if __name__ == "__main__":
    main()
