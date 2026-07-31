# BiliNote-MCP

把 [BiliNote](https://github.com/JefferyHcool/BiliNote) 的核心能力 —— **视频链接 → AI Markdown 笔记** —— 封装成 MCP 工具与 Claude Code Skill，供 agent 直接调用。

📦 仓库：[HuangYincan/BiliNote-MCP](https://github.com/HuangYincan/BiliNote-MCP)

核心特点：

- **内嵌流水线**：下载（yt-dlp）→ 字幕/转写（faster-whisper 本地 或 groq/bcut 云端）→ LLM 总结 → Markdown 笔记，全部逻辑在本仓库内，**无需启动 BiliNote 的 FastAPI 后端与 Web UI**。
- **无 RAG**：agent 拿到 Markdown 后自己阅读、自己回答，不需要 ChromaDB/embedding。
- **自包含**：`app/` 目录复制自上游（见 [VENDOR.md](VENDOR.md)），pip/uv 一键安装。

## 快速开始

### 方式一：plugin marketplace —— 一键装 Skill + MCP（推荐）

```bash
claude plugin marketplace add HuangYincan/BiliNote-MCP
claude plugin install bilinote@bilinote
```

两条命令同时装好 **Skill + MCP server**（MCP 走 `uvx`，每次会话自动拉最新 commit）。装完重启会话（或 `/reload-plugins`）即可用。

### 方式二：只装 MCP（不装 Skill）

```bash
claude mcp add --scope user bilinote -- uvx --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp
```

MCP server 是**会话级常驻进程**（会话开始时启动一次，工具调用不重新拉起）；uvx 每次会话检查一次仓库，**有新 commit 就自动用最新版**。

### 方式三：`uv tool install` —— 固定版本、启动最快

```bash
uv tool install --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp
claude mcp add bilinote -- "$HOME/.local/bin/bilinote-mcp"
```

一次性安装后每次会话**直接启动进程（约 1s）**、不访问仓库；但版本被固定，更新需重跑上面的 `uv tool install`（或 `uv tool install --force ...`）。

### 方式四：克隆 + `install.sh`

```bash
git clone https://github.com/HuangYincan/BiliNote-MCP.git
cd BiliNote-MCP && ./install.sh
```

`install.sh`：创建 venv → 安装依赖 → 注册 MCP → 安装 Skill（同 marketplace 方式）。

> 运行数据（SQLite、笔记、截图、配置）统一存在 `~/.local/share/bilinote-mcp/`（源码运行时在仓库 `data/`），不会写进安装目录。

### 手动安装等价步骤（源码方式）

```bash
uv sync                          # 1. 安装依赖（自动创建 venv）
# 或 pip install -e .

# 2. 注册 MCP（二选一）
#    Claude Code 项目级：在项目根放 .mcp.json（见仓库示例）
#    用户级：claude mcp add bilinote -- .venv/bin/bilinote-mcp
```

## 前提

- Python ≥ 3.11，<3.14（推荐 3.12）
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

## 使用说明

### 给 agent 用（Claude Code 等）

装上 MCP 后，直接对 agent 说「**给这个视频做笔记**」+ 链接即可。标准流程：

1. `health_check` —— 确认 FFmpeg / 数据库就绪；
2. `list_providers` —— 找可用的 LLM 供应商（没有就 `add_provider`，再 `list_models` / `add_model` 配好模型）；
3. `generate_note(video_url=..., provider_id=..., model_name=...)` —— 拿 `task_id`；
4. `get_task_status(task_id)` 轮询（或 `wait_for_note`），等到 `SUCCESS`；
5. 拿到 `result.markdown` 后，**agent 自己阅读 Markdown 回答你的问题** —— 不需要额外 RAG。

### 手动配置速查

| 想做什么 | 用哪个工具 |
|----------|-----------|
| 看 / 加 LLM 供应商 | `list_providers` / `add_provider(name, api_key, base_url, type)` |
| 看 / 加模型 | `list_models(provider_id)` / `add_model(provider_id, "deepseek-chat")` |
| 本地转写 | `set_transcriber("fast-whisper", "small")` + `download_transcriber_model("small")` |
| 云端转写 | `set_transcriber("groq")`（需已有 id 为 `groq` 的供应商） |
| B 站需登录内容 | `set_downloader_cookie(platform="bilibili", cookie="SESSDATA=...")` |
| 本地文件 | `generate_note(video_url="/绝对/路径/a.mp4", platform="local", ...)` |

工具逐个说明、agent 工作流与故障排查见 [docs/04-使用手册.md](docs/04-使用手册.md)。

## Skill（Claude Code）

仓库自带 Claude Code Skill —— `skills/bilinote/SKILL.md`，它会教 agent 用上面的流程**一句话完成「视频 → 笔记」**（触发词：「生成视频笔记」「帮这个视频做笔记」「从 XX 链接做笔记」）。

通过 plugin marketplace 一键安装（同时装好 Skill 与 MCP server）：

```bash
claude plugin marketplace add HuangYincan/BiliNote-MCP
claude plugin install bilinote@bilinote
```

装好后重启会话（或 `/reload-plugins`），对 Claude 说「**帮我给这个视频做笔记**」+ 链接，Skill 自动触发并驱动 MCP 工具。

## 文档

详细中文文档见 [docs/](docs/)：

- [目的与背景](docs/01-目的与背景.md)
- [架构设计](docs/02-架构设计.md)
- [预期效果](docs/03-预期效果.md)
- [使用手册](docs/04-使用手册.md)
- [更新日志](docs/CHANGELOG.md)

## 相关

- 上游项目：https://github.com/JefferyHcool/BiliNote
