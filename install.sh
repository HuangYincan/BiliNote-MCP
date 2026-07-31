#!/usr/bin/env bash
# BiliNote-Mcp 一键安装：创建 venv → 安装 → 注册 MCP → 链接 Skill
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

BIN="$REPO_DIR/.venv/bin/bilinote-mcp"
if [ ! -x "$BIN" ]; then
  BIN="$(command -v bilinote-mcp || true)"
fi
if [ ! -x "$BIN" ]; then
  echo "安装失败：找不到 bilinote-mcp 可执行文件" >&2
  exit 1
fi

echo "==> 2/4 注册 MCP（用户级）"
if command -v claude >/dev/null 2>&1; then
  claude mcp add bilinote -- "$BIN" && echo "已注册：claude mcp add bilinote -- $BIN"
else
  echo "未找到 claude CLI。请手动把下面的配置加入你的 MCP 配置："
  echo "  { \"mcpServers\": { \"bilinote\": { \"command\": \"$BIN\" } } }"
fi

echo "==> 3/4 安装 Skill（优先 marketplace，失败回退本地链接）"
if command -v claude >/dev/null 2>&1; then
  if claude plugin marketplace add HuangYincan/BiliNote-MCP >/dev/null 2>&1 \
     && claude plugin install bilinote@bilinote >/dev/null 2>&1; then
    echo "Skill 已通过 marketplace 安装（bilinote@bilinote）"
  else
    mkdir -p "$HOME/.claude/skills"
    ln -sfn "$REPO_DIR/skills/bilinote" "$HOME/.claude/skills/bilinote"
    echo "已本地链接：$HOME/.claude/skills/bilinote"
  fi
else
  mkdir -p "$HOME/.claude/skills"
  ln -sfn "$REPO_DIR/skills/bilinote" "$HOME/.claude/skills/bilinote"
  echo "已本地链接：$HOME/.claude/skills/bilinote"
fi

echo ""
echo "==> 4/4 完成。使用前检查："
echo "  1) FFmpeg：brew install ffmpeg（缺失时 health_check 会报告）"
echo "  2) LLM 供应商：list_providers / add_provider（DeepSeek/OpenAI/…）"
echo "  3) 转写引擎：本地 download_transcriber_model('tiny')，或云端 set_transcriber('groq')"
echo ""
echo "  验证：claude mcp list && health_check"
