# BiliNote-MCP

**中文** · [English](README_EN.md)

> 视频链接 → AI Markdown 笔记。基于 [BiliNote](https://github.com/JefferyHcool/BiliNote) 核心能力封装成的 **MCP Server（Model Context Protocol）+ Claude Code Skill**：给 agent 一个链接，它下载、转写、总结，交回一份结构化笔记 —— 全程无需启动后端。

<div align="center">

[![GitHub stars](https://img.shields.io/github/stars/HuangYincan/BiliNote-MCP?logo=github)](https://github.com/HuangYincan/BiliNote-MCP)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)]()
[![MCP](https://img.shields.io/badge/MCP-Server-6C5CE7)]()
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-D97757)]()
[![BiliNote-MCP MCP server](https://glama.ai/mcp/servers/HuangYincan/BiliNote-MCP/badges/score.svg)](https://glama.ai/mcp/servers/HuangYincan/BiliNote-MCP)

</div>

<p align="center"><a href="https://glama.ai/mcp/servers/HuangYincan/BiliNote-MCP"><img src="https://glama.ai/mcp/servers/HuangYincan/BiliNote-MCP/badges/card.svg" alt="BiliNote-MCP MCP server" width="600"></a></p>

📦 仓库：[HuangYincan/BiliNote-MCP](https://github.com/HuangYincan/BiliNote-MCP)

## ✨ 特性

- **🗜️ 内嵌流水线** —— 下载（yt-dlp）→ 字幕/转写（本地 faster-whisper 或云端 groq/bcut）→ **视频理解（按间隔抽帧，多模态 LLM 看画面）** → LLM 总结 → Markdown 笔记。全部逻辑在本仓库内，**无需启动 BiliNote 的 FastAPI 后端与 Web UI**。
- **🧠 无 RAG** —— agent 拿到 Markdown 后自己阅读、自己回答，不需要 ChromaDB / embedding，轻量即用。
- **📦 自包含** —— `app/` 目录复制自上游（见 [VENDOR.md](VENDOR.md)），pip / uv 一键安装。

## 快速开始（TL;DR）

```bash
# 装：一条命令装好 Skill + MCP
claude plugin marketplace add HuangYincan/BiliNote-MCP
claude plugin install bilinote@bilinote

# 配：LLM key + 语音转写引擎（隐藏输入 key）
bilinote-mcp setup

# 用：重启会话，对 agent 说「帮我给这个视频做笔记」+ 链接
```

> `bilinote-mcp` 是 CLI 简写，未在 PATH 时用 `uvx --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp ...`（见 [前提条件](#前提条件)）。

| 安装方式 | 内容 | 适合 |
|----------|------|------|
| **一 · 插件 marketplace**（推荐） | Skill + MCP（uvx 自动更新） | 大多数用户 |
| 二 · 只装 MCP（uvx） | 仅 MCP | 不想装 Skill |
| 三 · uv tool install | 仅 MCP（固定版本，启动最快 ~1s） | 要稳定版本 |
| 四 · 克隆 + install.sh | MCP + Skill + 自动 setup，无 uv 兜底 | 没装 uv / 想跑源码 |

## 安装

### 前提条件

- **uv**（Python 包管理器，必需 —— uvx / uv tool 方式装 MCP 和 CLI 都靠它）：
  `curl -LsSf https://astral.sh/uv/install.sh | sh` 或 `brew install uv`
  > 没有 uv？走「[方式四](#方式四克隆--installsh)」，脚本内置 pip 兜底。
- **Python ≥ 3.11，<3.14**（推荐 3.12，`.python-version` 已锁定）
- **FFmpeg**（音频/视频处理必需）：`brew install ffmpeg`（Linux：`apt install ffmpeg`）
- **LLM 供应商 API Key**（见[配置](#配置装完必做)）
- **本地转写**：本地 whisper 需先下载模型 `bilinote-mcp transcriber download <size>`（tiny/base/small/medium/large-v3/large-v3-turbo），或改用云端 `groq` / `bcut`（免下载）
- **GPU 加速（可选）**：
  - **NVIDIA / Linux**：whisper 默认 CPU；想用 CUDA，装工具时带 `--with torch`（CUDA 版 torch），推理时自动检测 GPU，否则回退 CPU
  - **macOS Apple Silicon**：用 `mlx-whisper` 走 GPU —— 装工具时 `--with mlx-whisper`，切引擎 `bilinote-mcp transcriber set mlx-whisper --size small`
- **CLI 命令可用形式**：正文里的 `bilinote-mcp ...` 是简写，等价于：
  - 有 uv：`uvx --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp ...`（`--from` 必须带 `git+` 前缀）
  - 方式四（pip 装的 venv）：`<仓库路径>/.venv/bin/bilinote-mcp ...`
  - 想让 `bilinote-mcp` 直接可用：`uv tool install --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp` + `uv tool update-shell` 加入 PATH

### 方式一：插件 marketplace —— Skill + MCP（推荐）

```bash
claude plugin marketplace add HuangYincan/BiliNote-MCP
claude plugin install bilinote@bilinote
```

两条命令同时装好 **Skill + MCP server**（MCP 走 `uvx`，每次会话自动拉最新 commit）。装完重启会话（或 `/reload-plugins`）。运行数据统一在 `~/.local/share/bilinote-mcp/`。

> **插件默认的 MCP 不含 `mlx-whisper`**（可选依赖，仅 macOS；默认加会让 Linux/Windows 装不上）。想在 MCP 里用 mlx-whisper，手动覆盖 MCP 命令：
>
> ```bash
> claude mcp add bilinote -- uvx --from git+https://github.com/HuangYincan/BiliNote-MCP --with mlx-whisper bilinote-mcp
> ```
>
> 手动注册后会话用的是这份（`claude mcp list` 显示它即生效）。若与插件同名 `bilinote` 冲突/不生效，先 `claude mcp remove bilinote` 再重加，或改用 `~/.local/bin/bilinote-mcp`（`uv tool install --with mlx-whisper` 装的那个）作为 MCP 命令。

### 方式二：只装 MCP（不装 Skill）

```bash
claude mcp add --scope user bilinote -- uvx --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp
```

即方式一的 MCP 部分。MCP server 是**会话级常驻进程**（会话开始启动一次，工具调用不重新拉起）。

### 方式三：uv tool install —— 固定版本、启动最快

```bash
uv tool install --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp
claude mcp add bilinote -- "$HOME/.local/bin/bilinote-mcp"
```

每次会话**直接启动进程（约 1s）**、不访问仓库；版本被固定，更新需重跑上面的 `uv tool install --force`。

> macOS Apple Silicon 想用 **MLX Whisper**（更快的本地转写，可选依赖）：安装时带上
> `uv tool install --force --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp --with mlx-whisper`

### 方式四：克隆 + install.sh

```bash
git clone https://github.com/HuangYincan/BiliNote-MCP.git
cd BiliNote-MCP && ./install.sh
```

无 uv 也能用（脚本用 pip 建 `.venv`）。install.sh：创建 venv → 注册 MCP → 安装 Skill → **自动弹出 `bilinote-mcp setup` 向导**。非交互终端会跳过，可稍后手动跑。

## 配置（装完必做）

> 安装只让 MCP / Skill 跑起来；**LLM API key 和语音转写引擎需单独配置**（key 是你的、模型要选）。所有方式共用同一数据目录（`~/.local/share/bilinote-mcp/`），配好即会话内生效。

### 交互向导 `setup`（推荐，随时可反复进入修改）

```bash
bilinote-mcp setup        # 未在 PATH 时：uvx --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp setup
```

**方向键选择 + 高亮**、**左键返回上一级**、每步自动清屏不留历史；**不是一次性程序**，随时重跑即可改配置：

- **① LLM 供应商**：选一个填/改 key、改 base_url、新增中转站；**每供应商可检测连接（验证 key/base_url）、列出可用模型并选默认模型**（默认模型持久化，生成笔记未指定模型时自动使用）；
- **② 语音转写引擎**：选引擎 + 模型尺寸，本地模型未下载会提示下载；
- **③ 其他**：平台 Cookie（平台下拉选择）、默认笔记位置（**持久化保存**）、**视频理解默认**（开/关 + 帧间隔秒数，**持久化保存**）、**评论/弹幕整合默认**（开/关 + 评论条数，**持久化保存**，需 B 站 SESSDATA）。

### 手动 CLI（key 不进对话）

```bash
# LLM 供应商
bilinote-mcp providers list                                    # 查看（key 掩码）
bilinote-mcp providers set deepseek --api-key 'sk-你的key'      # 给内置供应商填 key
bilinote-mcp providers add --name 中转站 --api-key 'sk-...' --base-url 'https://relay...'   # 新增中转站
bilinote-mcp providers test deepseek                            # 检测连接 + 列出可用模型
bilinote-mcp providers test deepseek --default deepseek-chat    # 检测并设为默认模型

# 语音转写引擎
bilinote-mcp transcriber list                                  # 查看当前引擎与就绪状态
bilinote-mcp transcriber set fast-whisper --size small          # 切本地 whisper
bilinote-mcp transcriber set groq                               # 切云端
bilinote-mcp transcriber download small                          # 下载 fast-whisper 模型
bilinote-mcp transcriber download small --engine mlx-whisper     # 下载 mlx-whisper（macOS）

# B 站（用 AI 字幕跳过语音识别）
bilinote-mcp login bilibili     # 扫码登录，自动获取并保存 SESSDATA（AI 字幕需登录态）
```

**转写引擎**：`fast-whisper`（本地）/ `groq` / `bcut` / `kuaishou`（云端）/ `mlx-whisper`（**仅 macOS Apple Silicon**，GPU 加速）。

**本地 whisper 尺寸**：`tiny` / `base` / `small` / `medium` / `large-v3` / **`large-v3-turbo`**（turbo 更快、精度略低于 large-v3）。

**设备**：whisper 会自动检测 CUDA（装了 torch+CUDA 就用 GPU，否则回退 CPU）；macOS 的 GPU 用 `mlx-whisper`。CLI `transcriber download` 用 CPU 只是因为它**只下载权重、不推理**（device 参数不影响下载结果）。

### 没有 LLM API key？

- **本地免费**：装 [Ollama](https://ollama.com) 并 `ollama pull llama3`。内置 `ollama` 供应商已预置（`http://127.0.0.1:11434/v1`，**无需 key**），`list_models("ollama")` 有模型即可用。
- **免费额度**：Groq / DeepSeek 等有免费 tier，注册后 `providers set` 填 key。
- 对 agent 说「我没有 LLM key」，它会先查 Ollama 是否可用，再引导你注册。

## 使用

### 给 agent 用（Claude Code 等）

对 agent 说「**给这个视频做笔记**」+ 链接即可，标准流程：

1. `health_check` —— 确认 FFmpeg / 数据库就绪；
2. `list_providers` —— 确认供应商 key=已填（看不到明文）；没有就先用 CLI 配；
3. `generate_note(video_url=..., provider_id=..., model_name=...)` —— 拿 `task_id`；
4. `get_task_status(task_id)` **轻量快照轮询**，等到 `SUCCESS`/`FAILED`/`CANCELLED`（**任务一次只发一个**，server 有进行中任务时会拒绝新提交；不要并行塞多个 `generate_note`）；
5. 拿到 `result.markdown` 后，**agent 自己阅读 Markdown 回答你的问题** —— 不需要额外 RAG；
6. **问你是否要根据笔记 + 提取的字幕（`result.transcript`）做后续优化**（补齐细节/修正不一致/增强结构）—— agent 侧精修，不新增工具。

### 手动工具速查（非敏感配置）

| 想做什么 | 用哪个工具 |
|----------|-----------|
| 看供应商 / 给内置填 key | `list_providers`（key 掩码） / **CLI** `providers set` |
| 看 / 加模型 | `list_models(provider_id)` / `add_model(provider_id, "deepseek-chat")` |
| 检测连接 / 设默认模型 | `bilinote-mcp providers test <id> [--default MODEL]`（非交互；向导内走「管理 → 检测连接」） |
| 本地转写 | `set_transcriber("fast-whisper", "small")` + `download_transcriber_model("small")` |
| 云端转写 | `set_transcriber("groq")`（groq 的 key 用 CLI 填） |
| B 站需登录内容 | `set_downloader_cookie(platform="bilibili", cookie="SESSDATA=...")` |
| 本地文件 | `generate_note(video_url="/绝对/路径/a.mp4", platform="local", ...)` |

> 涉及 **key 的操作一律走 CLI（对话外）**，工具只做非敏感配置 —— 见[安全说明](#安全api-key)。

### 进阶：视频理解（画面切片）

想让 agent 按时间间隔抽**视频画面**发给多模态 LLM（如 qwen-vl / gpt-4o）做「看画面」的理解，`generate_note` 直接支持：

```text
generate_note(video_url=..., provider_id="qwen", model_name="qwen-vl-plus",
              video_understanding=True, video_interval=6, grid_size=[3, 3])
```

- 每 `video_interval` 秒抽一帧，按 `grid_size` 拼成网格图，以 base64 内嵌发给 LLM；
- **需多模态（vision）模型**，deepseek-chat 等纯文本模型不支持；
- `grid_size` 缺省自动 `[3, 3]`（`format=["screenshot"]` 截图模式为 `[2, 2]`）；
- **默认值可在 setup ③ 配置**（默认关 / 6s）：agent 未显式传 `video_understanding` / `video_interval` 时自动套用（SKILL 仍要求**每次先问用户**本次是否启用 + 间隔，只有用户说「你定/用默认」才用默认值）；
- 想在 markdown 里按 `*Screenshot-mm:ss` 标记插**单张**截图，用 `format=["screenshot"]`（区别于整片帧网格）。

### 进阶：整合弹幕+评论区观点

想让笔记把 B 站**弹幕**和**评论区**的高频观点也整理进去（哪些弹幕刷屏、评论区在聊什么），`generate_note` 加：

```text
generate_note(video_url=..., ..., include_comments=True, comments_limit=20)
```

- 整合弹幕+评论区观点，让笔记不仅来自音轨，还能反映观众讨论；
- `comments_limit` 控制抓取的评论条数（默认 20）；
- **需 B 站 SESSDATA**（登录态）：没配则评论拿不到 —— 先 `bilinote-mcp login bilibili` 扫码（或 `set_downloader_cookie(platform="bilibili", cookie="SESSDATA=...")`）；
- **抓取失败不阻断任务**：拿不到评论/弹幕时笔记照常生成，跳过该部分即可；
- 只想单独拉数据看，用 `fetch_comments(video_url, limit=20)` / `fetch_danmaku(video_url)` 两个工具；
- **默认值可在 setup ③ 配置**（默认关 / 20条）：agent 未显式传 `include_comments` / `comments_limit` 时自动套用（SKILL 仍要求**每次先问用户**本次是否整合，只有用户说「你定/用默认」才用默认值）。

### 进阶：图片插入（便携笔记）

想让笔记带截图、且能整体搬迁，`generate_note` 加：

```text
generate_note(video_url=..., provider_id=..., model_name=..., screenshot=True, format=["screenshot"])
```

- 产出**便携笔记**：`note_dir/note.md` + `note_dir/Assets/*.jpg`，markdown 里用**相对引用** `![...](Assets/xxx.jpg)`；
- 任务结果里 `result.note_dir` 指向该目录（agent 会告诉你笔记和图片在哪）；
- **保存位置**优先级：`generate_note(..., notes_dir="/你/指定/的目录")` → `BILINOTE_NOTES_DIR` 环境变量 → 默认 `note_results/{task_id}/`；
- **指定了 `notes_dir` 时，即使不插图片也会把 `note.md` 写到该目录**（适合「生成笔记到某文件夹」）；
- 前提：`screenshot=True` 让 LLM 在笔记里生成 `*Screenshot-[mm:ss]` 标记，`format=["screenshot"]` 负责替换成图片；配视频理解（`video_understanding=True`）时画面理解与截图更自然。

## 工具参考

| 工具 | 说明 |
|------|------|
| `generate_note` | 提交视频 URL，异步生成笔记，返回 task_id（支持视频理解 + 图片插入便携笔记 + `extras` 自定义风格，见[使用说明](#进阶视频理解画面切片)） |
| `get_task_status` / `wait_for_note` | 轮询任务进度 / 阻塞等待最终 Markdown |
| `cancel_note` | 取消进行中/排队的任务（协作式，下一阶段边界生效） |
| `list_providers` / `add_provider` / `update_provider` | 查看（掩码）/ 新增 / 更新供应商（填 key 建议走 CLI） |
| `list_models` / `add_model` | 查看（实时/回退本地）/ 手动添加模型 |
| `get_transcriber_config` / `set_transcriber` | 查看 / 切换转写引擎（本地 whisper ↔ 云端 groq） |
| `list_transcriber_models` / `download_transcriber_model` | whisper 模型管理 |
| `health_check` | FFmpeg / 数据库 / whisper 就绪状态 |
| `validate_url` | 判断视频链接属于哪个平台 |
| `set_downloader_cookie` | 设置平台 Cookie（如 B 站） |
| `fetch_comments` / `fetch_danmaku` | 抓取 B 站视频评论 / 弹幕（`fetch_comments(video_url, limit=20)` / `fetch_danmaku(video_url)`，需 SESSDATA） |

## 环境变量（可选）

| 变量 | 作用 | 默认 |
|------|------|------|
| `BILINOTE_DATA_DIR` | 数据根目录（SQLite / 笔记 / 截图 / 配置） | 安装模式 `~/.local/share/bilinote-mcp`，源码 `仓库/data` |
| `BILINOTE_NOTES_DIR` | 默认笔记输出目录（指定 `notes_dir` 时的兜底） | `note_results/{task_id}/` |
| `BILINOTE_CONFIG_DIR` | 配置文件目录（转写/cookie/app 配置） | `<数据目录>/config` |
| `BILINOTE_MODEL_DIR` | whisper / mlx 模型目录 | `<数据目录>/models`（源码 `仓库/models`） |
| `BILINOTE_MAX_WORKERS` | 单个 MCP 会话内**并发笔记任务数** | 3 |
| `HF_ENDPOINT` | HuggingFace 镜像（国内下载慢/卡时用） | 官方 `https://huggingface.co`；国内可 `https://hf-mirror.com` |

**会话内串行 + 多会话并行**：每个 Claude Code 会话独立起一个 MCP server 进程。**本会话内任务强制串行** —— `generate_note` 在已有进行中任务时会**直接拒绝**（必须一次一个：提交 → 等到 `SUCCESS`/`FAILED`/`CANCELLED` → 再提交下一个）；**多个会话**可各自并行生成不同视频的笔记（互不干扰）。**注意**：Claude Code 客户端对「同一条消息里多个并行 MCP 工具调用」处理不稳（最后一个响应会卡死、任务也未提交）—— 所以即使跨任务，也**不要在同一消息里并行塞多个 `generate_note`**。**多任务轮询请用轻量 `get_task_status(task_id)` 快照轮询**；`wait_for_note` 是阻塞调用，会卡住当前轮次。需要取消进行中任务用 `cancel_note(task_id)`。注意：whisper / MLX 转写吃 CPU/内存，太多会话并行会拉满机器；所有会话共用同一个 SQLite，极端并发下可能偶发写冲突。

## 更新

各安装方式的更新命令：

| 装的什么 | 更新命令 |
|----------|----------|
| **MCP server**（uvx / 插件） | ✅ 自动更新（每次会话查最新 commit），无需手动 |
| **Skill / 插件** | `claude plugin marketplace update bilinote` + `claude plugin disable bilinote@bilinote` + `claude plugin install bilinote@bilinote` |
| **`uv tool install` 装的 CLI**（`bilinote-mcp`） | `uv tool upgrade bilinote-mcp`（保留 `--with mlx-whisper` 等附加依赖） |
| **源码 / `install.sh`** | `git pull && ./install.sh` |

> **Skill/插件三步各有用**：① `marketplace update` 拉最新 commit；② `disable` 让 `install` 不跳过；③ `install` 重装到最新。缺任一步都可能用旧版（`install` 单独会被「已安装」跳过）。

## 安全（API Key）

**红线：不要在对话里把 key 发给 agent。** agent 的对话内容会发送到它的 LLM 上游，key 一旦出现在对话里就等于交给了上游。**key 一律在独立终端走 CLI**（`!` 前缀的命令文本也在对话里，同样不行）：

```bash
bilinote-mcp providers set deepseek --api-key 'sk-你的key'      # 独立终端执行
bilinote-mcp providers list                                     # 查看（key 掩码）
```

- **agent 只需要知道「key 填没填」**：`list_providers` 返回掩码（`sk-S***cdef`），add/update 工具不回显 key，相关日志已打码。
- **存哪**：key 只存在本地 SQLite（`~/.local/share/bilinote-mcp/bili_note.db` 或源码 `data/`），已 gitignore，**不会进 GitHub**。
- **提醒**：key 以明文存在本地数据库（与上游 BiliNote 一致）。若机器可能被他人使用，建议后续用系统 keychain 加密存储。

## Skill

仓库自带 Claude Code Skill —— `skills/bilinote/SKILL.md`，它教 agent 用上面的流程**一句话完成「视频 → 笔记」**（触发词：「生成视频笔记」「帮这个视频做笔记」「从 XX 链接做笔记」）。

通过插件 marketplace 安装（同时装好 Skill 与 MCP server）：

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

## 开发流程

- **日常开发在 `dev` 分支**：功能分支 → PR → `dev`（CI 必须绿）；
- **发布**：`dev` 稳定后 → PR `dev` → `main`（CI + review 通过才合）→ 打 `vX.Y.Z` tag → [Release workflow](.github/workflows/release.yml) 自动发 GitHub Release；
- **`main` 有分支保护**：直接 push 被拒，只接受 PR 合入 —— 保证 `main` 永远可用（`uvx --from git+` 安装直接拉 main）；
- 稳定安装用 tag：`uvx --from git+https://github.com/HuangYincan/BiliNote-MCP@v0.1.0 bilinote-mcp`（追新去掉 `@v0.1.0`）。

## 开发版（dev 分支尝鲜）

`dev` 分支有未发布的新功能（尝鲜/测试用）。想提前用 dev：

**MCP 工具指 dev**（覆盖插件的 main MCP）：

```bash
claude mcp add --scope user bilinote -- uvx --from git+https://github.com/HuangYincan/BiliNote-MCP@dev bilinote-mcp
```

**SKILL 也指 dev**（marketplace 指到 dev 分支）：

```bash
claude plugin marketplace add HuangYincan/BiliNote-MCP@dev
claude plugin disable bilinote@bilinote
claude plugin install bilinote@bilinote
```

重启会话（或 `/reload-plugins`）生效。

**切回 main（稳定版）**：

```bash
claude mcp remove bilinote                                   # MCP 恢复插件默认（main）
claude plugin marketplace add HuangYincan/BiliNote-MCP       # marketplace 回 main
claude plugin disable bilinote@bilinote
claude plugin install bilinote@bilinote
# /reload-plugins
```

**CLI 用 dev**（PATH 上的 `bilinote-mcp` 若是 main 固定版）：`uvx --from git+https://github.com/HuangYincan/BiliNote-MCP@dev bilinote-mcp setup`

> **注意**：
> - dev 与 main **共用数据目录** `~/.local/share/bilinote-mcp/`：LLM key / SESSDATA / 转写配置自动带过来，**不用重配**；但共用同一 SQLite，别两个同时跑任务。
> - marketplace 指 dev 会**替换**生产 marketplace（不并存），测完记得切回 main。
> - `git+...@dev` 是 uv/uvx 的分支 ref 语法；不带 ref 的默认安装拉的是 **main**（稳定）。
> - marketplace 指 dev 只换 **SKILL**；MCP 工具要手动 `@dev` 覆盖（marketplace.json 里的 uvx 无 ref，仍拉 main）。
> - dev 分支功能未发布，仅尝鲜/测试。

## 相关

- 上游项目：https://github.com/JefferyHcool/BiliNote
