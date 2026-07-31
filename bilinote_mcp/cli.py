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
_WHISPER_SIZES = ("tiny", "base", "small", "medium", "large-v3")


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


def _setup_cli() -> None:
    """交互式初始化：配置 LLM 供应商 + 语音转写引擎。"""
    print("=== BiliNote-MCP 初始化配置 ===", file=sys.stdout)
    print("API key 为隐藏输入，不经过 agent 对话。随时 Ctrl-C 取消。", file=sys.stdout)

    # ---------- ① LLM 供应商 ----------
    print("\n① 选择 LLM 供应商：", file=sys.stdout)
    for k, (_, name, url) in _BUILTIN_PROVIDERS.items():
        print(f"   {k}) {name}  {url}", file=sys.stdout)
    print("   6) 中转站 / 自建网关（自定义 base_url）", file=sys.stdout)
    choice = _ask("选择 [1-6]", default="1")

    if choice in _BUILTIN_PROVIDERS:
        pid, name, url = _BUILTIN_PROVIDERS[choice]
        if choice == "5":  # ollama
            print(f"   ✓ 使用 {name}（无需 key，请确保本机已启动 ollama）", file=sys.stdout)
        else:
            key = _ask_secret(f"   输入 {name} 的 API key")
            if key:
                ProviderService.update_provider(pid, {"api_key": key})
                print(f"   ✓ 已保存 {name} 的 key（{pid}）", file=sys.stdout)
            else:
                print(f"   ⚠ 未输入 key，可稍后 `bilinote-mcp providers set {pid} --api-key '...'` 补充", file=sys.stdout)
    else:
        name = _ask("   供应商名称", default="我的中转站")
        base_url = _ask("   base_url（如 https://relay.example.com/v1）")
        key = _ask_secret("   API key")
        if not name or not base_url or not key:
            print("   ⚠ 信息不完整，跳过新增", file=sys.stdout)
        else:
            new_id = ProviderService.add_provider(name=name, api_key=key, base_url=base_url, logo="custom", type_="custom")
            print(f"   ✓ 已新增 {name} → id={new_id}", file=sys.stdout)

    # ---------- ② 语音转写引擎 ----------
    print("\n② 选择语音转写引擎：", file=sys.stdout)
    print("   1) fast-whisper（本地离线，免费）", file=sys.stdout)
    print("   2) groq（云端，快，需 groq 的 key）", file=sys.stdout)
    print("   3) bcut / kuaishou（云端，免 key）", file=sys.stdout)
    print("   4) mlx-whisper（仅 macOS Apple Silicon，本地快）", file=sys.stdout)
    t_choice = _ask("选择 [1-4]", default="1")

    if t_choice == "2":
        TranscriberConfigManager().update_config("groq")
        print("   ✓ 已切换到 groq（需 groq 供应商已配 key）", file=sys.stdout)
    elif t_choice == "3":
        TranscriberConfigManager().update_config("bcut")
        print("   ✓ 已切换到 bcut", file=sys.stdout)
    elif t_choice == "4":
        size = _ask("   mlx 模型尺寸", default="small")
        TranscriberConfigManager().update_config("mlx-whisper", size)
        print(f"   ✓ 已切换到 mlx-whisper / {size}", file=sys.stdout)
    else:  # fast-whisper
        size = _ask("   whisper 模型尺寸（tiny/base/small/medium/large-v3）", default="small")
        if size not in _WHISPER_SIZES:
            size = "small"
        TranscriberConfigManager().update_config("fast-whisper", size)
        print(f"   ✓ 已切换到 fast-whisper / {size}", file=sys.stdout)
        if _ask(f"   现在下载 whisper-{size} 模型？（首次约几十MB~数GB）[y/N]", default="N").lower() == "y":
            try:
                from app.transcriber.whisper_models import resolve_whisper_model
                from faster_whisper import WhisperModel
                from app.utils.path_helper import get_model_dir

                print(f"   正在下载 whisper-{size}，请稍候…", file=sys.stdout)
                WhisperModel(
                    model_size_or_path=resolve_whisper_model(size),
                    device="cpu", compute_type="int8",
                    download_root=get_model_dir("whisper"),
                )
                print(f"   ✓ whisper-{size} 下载完成", file=sys.stdout)
            except Exception as e:
                print(f"   ⚠ 下载失败：{e}（可稍后调用 download_transcriber_model 重试）", file=sys.stdout)

    print("\n=== 配置完成 ===", file=sys.stdout)
    print("· 验证：`bilinote-mcp providers list` 看 key 是否已填", file=sys.stdout)
    print("· 生成笔记时告诉 agent provider_id 与 model_name 即可", file=sys.stdout)


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
        size = opts.size
        print(f"正在下载 whisper-{size}（首次约几十MB~数GB，请稍候）…", file=sys.stdout)
        try:
            from app.transcriber.whisper_models import resolve_whisper_model
            from faster_whisper import WhisperModel
            from app.utils.path_helper import get_model_dir

            WhisperModel(
                model_size_or_path=resolve_whisper_model(size),
                device="cpu", compute_type="int8",
                download_root=get_model_dir("whisper"),
            )
            print(f"✓ whisper-{size} 下载完成", file=sys.stdout)
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
