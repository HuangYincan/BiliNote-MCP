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

init_db()
seed_default_providers()


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


def main() -> None:
    """入口：providers 子命令走轻量 CLI，其余进入 MCP server（stdio）。"""
    if len(sys.argv) > 1 and sys.argv[1] == "providers":
        _providers_cli(sys.argv[2:])
        return
    # MCP 模式：懒加载完整流水线（server.py）
    from bilinote_mcp.server import main as _server_main

    _server_main()


if __name__ == "__main__":
    main()
