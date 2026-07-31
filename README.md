# BiliNote-Mcp

把 [BiliNote](https://github.com/JefferyHcool/BiliNote) 的核心能力 —— **视频链接 → AI Markdown 笔记** —— 封装成 MCP 工具与 Claude Code Skill，供 agent 直接调用。

📦 仓库：<https://github.com/HuangYincan/BiliNote-MCP>

核心特点：

- **内嵌流水线**：下载（yt-dlp）→ 字幕/转写（faster-whisper 本地 或 groq/bcut 云端）→ LLM 总结 → Markdown 笔记，全部逻辑在本仓库内，**无需启动 BiliNote 的 FastAPI 后端与 Web UI**。
- **无 RAG**：agent 拿到 Markdown 后自己阅读、自己回答，不需要 ChromaDB/embedding。
- **自包含**：`app/` 目录复制自上游（见 [VENDOR.md](VENDOR.md)），pip/uv 一键安装。

## 快速开始

```bash
# 0. 克隆仓库
git clone https://github.com/HuangYincan/BiliNote-MCP.git
cd BiliNote-MCP

# 1. 一键安装（venv + 注册 MCP + 链接 Skill）
./install.sh
```

`install.sh` 会依次：创建虚拟环境并安装依赖 → 注册 MCP（`claude mcp add bilinote -- .venv/bin/bilinote-mcp`）→ 把 Skill 链接到 `~/.claude/skills/bilinote`。

手动安装等价步骤：

```bash
uv sync                          # 1. 安装依赖（自动创建 venv）
# 或 pip install -e .

# 2. 注册 MCP（二选一）
#    Claude Code 项目级：在项目根放 .mcp.json（见仓库示例）
#    用户级：claude mcp add bilinote -- .venv/bin/bilinote-mcp

# 3. 安装 Skill（供 agent 使用）
#    ln -sf "$(pwd)/.claude/skills/bilinote" ~/.claude/skills/bilinote
```

## 前提

- Python ≥ 3.11（推荐 3.12）
- **FFmpeg**（音频/视频处理必需）：`brew install ffmpeg`
- LLM 供应商 API Key（通过 `add_provider` 工具或复用已有 BiliNote 数据库配置）
- 本地转写需下载 whisper 模型（`download_transcriber_model`），或改用云端 groq

## 工具一览

| 工具 | 说明 |
|------|------|
| `generate_note` | 提交视频 URL，异步生成笔记，返回 task_id |
| `get_task_status` / `wait_for_note` | 轮询任务进度 / 阻塞等待最终 Markdown |
| `list_providers` / `add_provider` | 查看 / 新增 LLM 供应商 |
| `list_models` / `add_model` | 查看（实时/回退本地） / 手动添加模型 |
| `get_transcriber_config` / `set_transcriber` | 查看 / 切换转写引擎（本地 whisper ↔ 云端 groq） |
| `list_transcriber_models` / `download_transcriber_model` | whisper 模型管理 |
| `health_check` | FFmpeg / 数据库 / whisper 就绪状态 |
| `validate_url` | 判断视频链接属于哪个平台 |
| `set_downloader_cookie` | 设置平台 Cookie（如 B 站） |

## 文档

详细中文文档见 [docs/](docs/)：

- [目的与背景](docs/01-目的与背景.md)
- [架构设计](docs/02-架构设计.md)
- [预期效果](docs/03-预期效果.md)
- [使用手册](docs/04-使用手册.md)
- [更新日志](docs/CHANGELOG.md)

## 相关

- 上游项目：https://github.com/JefferyHcool/BiliNote
