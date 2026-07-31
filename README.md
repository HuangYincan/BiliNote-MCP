# BiliNote-MCP

把 [BiliNote](https://github.com/JefferyHcool/BiliNote) 的核心能力 —— **视频链接 → AI Markdown 笔记** —— 封装成 MCP 工具与 Claude Code Skill，供 agent 直接调用。

📦 仓库：[HuangYincan/BiliNote-MCP](https://github.com/HuangYincan/BiliNote-MCP)

## 特性

- **内嵌流水线**：下载（yt-dlp）→ 字幕/转写（faster-whisper 本地 或 groq/bcut 云端）→ LLM 总结 → Markdown 笔记，全部逻辑在本仓库内，**无需启动 BiliNote 的 FastAPI 后端与 Web UI**。
- **无 RAG**：agent 拿到 Markdown 后自己阅读、自己回答，不需要 ChromaDB/embedding。
- **自包含**：`app/` 目录复制自上游（见 [VENDOR.md](VENDOR.md)），pip/uv 一键安装。

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

- **① LLM 供应商**：选一个填/改 key、改 base_url，或新增中转站；
- **② 语音转写引擎**：选引擎 + 模型尺寸，本地模型未下载会提示下载；
- **③ 其他**：平台 Cookie（平台下拉选择）、默认笔记位置（**持久化保存**）。

### 手动 CLI（key 不进对话）

```bash
# LLM 供应商
bilinote-mcp providers list                                    # 查看（key 掩码）
bilinote-mcp providers set deepseek --api-key 'sk-你的key'      # 给内置供应商填 key
bilinote-mcp providers add --name 中转站 --api-key 'sk-...' --base-url 'https://relay...'   # 新增中转站

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
4. `get_task_status(task_id)` 轮询（或 `wait_for_note`），等到 `SUCCESS`；
5. 拿到 `result.markdown` 后，**agent 自己阅读 Markdown 回答你的问题** —— 不需要额外 RAG。

### 手动工具速查（非敏感配置）

| 想做什么 | 用哪个工具 |
|----------|-----------|
| 看供应商 / 给内置填 key | `list_providers`（key 掩码） / **CLI** `providers set` |
| 看 / 加模型 | `list_models(provider_id)` / `add_model(provider_id, "deepseek-chat")` |
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
- 想在 markdown 里按 `*Screenshot-mm:ss` 标记插**单张**截图，用 `format=["screenshot"]`（区别于整片帧网格）。

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
| `generate_note` | 提交视频 URL，异步生成笔记，返回 task_id（支持视频理解 + 图片插入便携笔记，见[使用说明](#进阶视频理解画面切片)） |
| `get_task_status` / `wait_for_note` | 轮询任务进度 / 阻塞等待最终 Markdown |
| `list_providers` / `add_provider` / `update_provider` | 查看（掩码）/ 新增 / 更新供应商（填 key 建议走 CLI） |
| `list_models` / `add_model` | 查看（实时/回退本地）/ 手动添加模型 |
| `get_transcriber_config` / `set_transcriber` | 查看 / 切换转写引擎（本地 whisper ↔ 云端 groq） |
| `list_transcriber_models` / `download_transcriber_model` | whisper 模型管理 |
| `health_check` | FFmpeg / 数据库 / whisper 就绪状态 |
| `validate_url` | 判断视频链接属于哪个平台 |
| `set_downloader_cookie` | 设置平台 Cookie（如 B 站） |

## 更新

各安装方式的更新命令：

| 装的什么 | 更新命令 |
|----------|----------|
| **MCP server**（uvx / 插件） | ✅ 自动更新（每次会话查最新 commit），无需手动 |
| **Skill / 插件** | `claude plugin disable bilinote@bilinote` + `claude plugin install bilinote@bilinote` |
| **`uv tool install` 装的 CLI**（`bilinote-mcp`） | `uv tool upgrade bilinote-mcp`（保留 `--with mlx-whisper` 等附加依赖） |
| **源码 / `install.sh`** | `git pull && ./install.sh` |

> 注意：插件 `install` 单独执行会被当作「已安装」跳过，必须先 `disable` 再 `install` 才重装到最新。

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

## 相关

- 上游项目：https://github.com/JefferyHcool/BiliNote
