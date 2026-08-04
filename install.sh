#!/usr/bin/env bash
# VideoNote-Mcp 一键安装：创建 venv → 安装 → 注册 MCP → 链接 Skill
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "==> 1/4 安装 Python 依赖"
if command -v uv >/dev/null 2>&1; then
  uv sync
else
  echo "（未找到 uv，改用 python3 venv + pip）"
  python3 -m venv .venv
  ./.venv/bin/pip install -e .
fi

BIN="$REPO_DIR/.venv/bin/videonote"
if [ ! -x "$BIN" ]; then
  BIN="$(command -v videonote || true)"
fi
if [ ! -x "$BIN" ]; then
  echo "安装失败：找不到 videonote 可执行文件" >&2
  exit 1
fi

echo "==> 2/4 注册 MCP（用户级）"
if command -v claude >/dev/null 2>&1; then
  claude mcp add videonote -- "$BIN" && echo "已注册：claude mcp add videonote -- $BIN"
else
  echo "未找到 claude CLI。请手动把下面的配置加入你的 MCP 配置："
  echo "  { \"mcpServers\": { \"videonote\": { \"command\": \"$BIN\" } } }"
fi

echo "==> 3/4 安装 Skill"
HAVE_UV="0"
command -v uv >/dev/null 2>&1 && HAVE_UV="1"
install_skill_local() {
  mkdir -p "$HOME/.claude/skills"
  ln -sfn "$REPO_DIR/skills/videonote" "$HOME/.claude/skills/videonote"
  echo "已本地链接：$HOME/.claude/skills/videonote"
}
if [ "$HAVE_UV" = "1" ] && command -v claude >/dev/null 2>&1; then
  # marketplace 方式（插件里的 MCP server 走 uvx，需要 uv）
  if claude plugin marketplace add HuangYincan/VideoNote-MCP >/dev/null 2>&1 \
     && claude plugin install videonote@videonote >/dev/null 2>&1; then
    echo "Skill 已通过 marketplace 安装（videonote@videonote）"
  else
    install_skill_local
  fi
else
  # 无 uv：跳过 marketplace（避免注册出无法启动的 uvx MCP），只用本地链接
  install_skill_local
fi

echo ""
echo "==> 4/4 初始化配置（LLM 供应商 + 语音转写引擎）"
if [ -t 0 ]; then
  "$BIN" setup
else
  echo "（非交互终端，跳过。可稍后执行：$BIN setup）"
fi

echo ""
echo "==> 安装完成。验证："
echo "  claude mcp list        # 应看到 videonote"
echo "  $BIN providers list    # 确认 LLM key 已填"
echo "  health_check           # ffmpeg / db / whisper 状态"
