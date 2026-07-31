# CHANGELOG

按关键节点记录项目变更（日期 + 做了什么 + 文档改了什么）。

## 维护（2026-07-31）

- 修复用户侧 MCP 注册：`--from` 需带 `git+` 前缀（`git+https://...`），且用 `claude mcp add --scope user` 注册到用户级。
- **整体重构 README.md**：章节顺序（前提→安装→配置→使用→工具→更新→安全→Skill）、CLI 命令统一简写 + 定义等价形式、key 配置收敛到「对话外 CLI」与安全红线一致、去重、新增安装方式对比表。
- **docs/04-使用手册.md 对齐 README 口径**：key 一律 CLI（`providers set`）、工具参考补 `update_provider`（15 个）、CLI 简写定义、安装方式表格、配置顺序（setup 向导 → LLM → 转写 → Cookie）、Skill 更新命令。
- **视频理解（画面切片）**：
  - 修复 `video_understanding=True` 时 `grid_size` 缺省为空 tuple 导致「视频处理失败」——改为自动默认 `[3,3]`（`screenshot` 模式 `[2,2]`）。
  - README / docs/04 新增「视频理解」章节（`video_understanding` / `video_interval` / `grid_size` 用法、需多模态模型）；docs/04 工具参考补全这些参数；SKILL.md 工作流加「用户想看画面」时的 agent 指引。
- **用户可配置笔记参数 + 图片插入便携笔记（Assets）**：
  - `generate_note` 新增 `notes_dir` 参数（便携笔记位置）；解析优先级：`notes_dir` → `BILINOTE_NOTES_DIR` env → `note_results/{task_id}/`。
  - `note.py`：`_insert_screenshots` 支持 `assets_dir`（截图写进 `Assets/`、markdown 用相对引用 `![...](Assets/xxx.jpg)`）；`generate()` 截图模式下写 `note.md` 与 `Assets/` 同层。
  - `server.py`：任务结果返回 `note_dir`。
  - SKILL.md：工作流新增「确认参数」步骤 —— 用户没指定时询问 LLM 模型/转写/风格/是否视频理解/是否插图片+保存位置。
  - README / docs/04：新增「图片插入（便携笔记）」章节。
  - 已单测 `_insert_screenshots` Assets 布局（相对引用 + 图片落盘）。
- **`bilinote-mcp transcriber` CLI**：终端直接管理语音转写引擎 —— `list` / `set <engine> [--size]` / `download <size>`（本地 whisper 模型下载）；README / docs/04 补命令行。
- README「更新」章节改为**分安装方式表格**，补上 `uv tool install` 装的 CLI 更新命令 `uv tool upgrade bilinote-mcp`（实测保留 `--with mlx-whisper`）。
- 修复误导提示：`transcriber_config_manager.is_model_ready` 的「请先在设置页下载」改为「请先执行 `bilinote-mcp transcriber download <size>`」。
- cli.py 本地 whisper 尺寸补上 `large-v3-turbo`（后端早已支持）；README / docs/04 明确转写引擎列表（含 mlx-whisper 仅 macOS）、设备说明（whisper 自动检测 CUDA、CLI download 用 cpu 只因下载不推理）。

## 发布后维护（2026-07-31）

- 首次推送到 GitHub（`HuangYincan/BiliNote-MCP`，PUBLIC）。
- README 补全「一键安装」：仓库地址、clone 步骤、`install.sh` 等价手动步骤。
- **修复打包 bug**：`.gitignore` 的 `models/`/`data/` 无锚点规则误伤 `app/models/`、`app/db/models/`（wheel 缺失，仅本地 editable 安装可用）→ 改为根锚定 `/models/` `/data/`；`pyproject` 加 `requires-python <3.14` 上界（av/faster-whisper 无 3.14 wheel）、wheel 改用 `include` glob。
- 支持 **`uvx --from git+URL` 一键安装**：`claude mcp add bilinote -- uvx --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp`（已验证，14 个工具全部可用）。
- README 增加「方式一：Claude 命令一行安装」。
- **修复安装后的数据目录 bug**：`bilinote_mcp/config.py` 区分「源码 checkout（用仓库 data/）」「已安装包（用 `~/.local/share/bilinote-mcp`，不写 site-packages）」；`path_helper.py` 的 `get_data_dir/get_model_dir/get_app_dir` 尊重 `BILINOTE_DATA_DIR/BILINOTE_MODEL_DIR` 环境变量，并修复上游 `get_data_dir` 返回 `data/data` 的 bug。
- **安装方式定稿**（实测耗时对比）：`uvx`（缓存命中 ~8s、新版 commit ~20s）**自动更新，推荐**；`uv tool install`（~1s 直接启动）固定版本、启动最快。README 以 `uvx` 为方式一。
- README 补充「使用说明」（agent 工作流 + 配置速查）与「Skill」章节（安装、触发方式）。
- **新增 plugin marketplace**：`.claude-plugin/marketplace.json`（Skill + MCP server 一起分发）。安装一条命令：
  `claude plugin marketplace add HuangYincan/BiliNote-MCP && claude plugin install bilinote@bilinote`。
  - Skill 移到 marketplace 规范路径 `skills/bilinote/SKILL.md`；
  - `plugin.json` 故意不写 version → 每次 commit 即新版本（自动更新）；
  - `install.sh` 改用 marketplace 优先、本地链接兜底；
  - `.claude/settings.json` 加入 gitignore（机器本地插件状态不入库）。
  - 修复：仓库根 `.mcp.json` 与 marketplace 的 mcpServers 声明冲突（插件安装时会加载插件根的 `.mcp.json`，注册出错误的 `uv run` server）→ 移到 `examples/mcp.example.json` 作为手动示例。
- **内置供应商预置 + update_provider 工具**：空库启动自动 seed 7 个内置供应商（openai/deepseek/qwen/groq/ollama…，固定 id + 正确 base_url + 空 key），`update_provider(provider_id, api_key)` 填 key；groq 转写器按 id='groq' 找供应商，因此现在可直接用。工具增至 **15 个**。复制 `app/db/builtin_providers.json`（wheel 已确认包含）。
- README 新增「配置示例」：例一 LLM 供应商配置（update_provider + add_model），例二转写引擎切换（本地 whisper / 云端 groq）；docs/04 与 SKILL.md 同步更新。
- **安全修复**：
  1. `get_all_providers_safe` 上游 bug —— 误用 `serialize_provider`（非 safe）导致 `list_providers` 返回完整 api_key → 改为 `serialize_provider_safe`（掩码）。
  2. `update_provider` 日志打印 `filtered_data` 会带 api_key → 打码。
- README 增补：中转站/自建网关配置示例、「没有 LLM key」指南（Ollama 本地免费 / 免费额度注册）、「安全说明」章节（key 存本地 gitignored DB、MCP 响应掩码、明文存储提醒）。
- SKILL.md：前提补充「用户没有 key 优先用 Ollama」的 agent 处理路径。
- **API key 安全通道（对话外）**：新增 `bilinote-mcp providers` CLI 子命令（`list` / `set` / `add`），用户在终端直接写 key，**key 不经过 agent 对话**（对话会发送到 agent 的 LLM 上游）。README 安全说明改为「别在对话里发 key」指引；SKILL.md 加安全红线（让用户用终端 CLI 填 key）。
- 修复：`builtins.print` 重定向挪到 `import app.*` 之前（douyin_downloader 等模块导入时打印会污染 CLI stdout / MCP stdio）。
- README「更新」章节**修正**：MCP（uvx）确认为自动更新；Skill/插件**不会自动升级**，实测需 `claude plugin disable bilinote@bilinote` + `claude plugin install bilinote@bilinote`（`install` 单独执行会因「已安装」被跳过）。
- 前提补充：**uv 为必需**（一行安装命令）；无 uv 走方式四（install.sh 内置 pip 兜底）。
- CLI 命令补充 PATH 无关写法：有 uv 用 `uvx --from ... bilinote-mcp providers ...`；无 uv 用 `<仓库>/.venv/bin/bilinote-mcp providers ...`。
- install.sh：skill 安装仅在**有 uv** 时走 marketplace（插件内 MCP 走 uvx），无 uv 自动回退本地链接，避免注册出起不来的 MCP。
- **CLI 轻量化重构**：新增 `bilinote_mcp/cli.py`（console script 改指 `cli:main`）。`bilinote-mcp providers ...` 只导入 provider 相关模块（启动快、无下载器/转写器 import 噪音）；MCP 模式懒加载 `server.py`。修复 CLI 终端输出被导入噪音污染的问题。
- **交互式初始化向导**：新增 `bilinote-mcp setup` —— 隐藏输入 LLM API key（选内置/中转站供应商）、选语音转写引擎（本地 whisper / groq / bcut / mlx）、选模型尺寸、可选立即下载 whisper 模型。`install.sh` 装完后在交互终端自动唤起。

## 节点 1：仓库脚手架（2026-07-31）

- 新建独立仓库 `BiliNote-Mcp`（git init，分支 main）。
- 初始化目录结构：`bilinote_mcp/`（占位）、`app/`（待移植）、`docs/`、`.claude/skills/bilinote/`（待建）、`data/`。
- 写入 `pyproject.toml`（基础依赖，待 Phase 5 定稿）、`.gitignore`、`.python-version`(3.12)、`.mcp.json` 示例、`README.md` 骨架、`VENDOR.md`（记录上游 commit `bebf2e8c`）。
- 文档：创建 `docs/00`~`docs/04` 全部中文文档骨架（目的、架构、预期效果、使用手册、索引）。

## 节点 2：核心代码移植（2026-07-31）

- 从上游 `BiliNote/backend/app/` 复制核心流水线模块到 `app/`：downloaders / transcriber / gpt(含 provider) / db(含 models) / models / enmus / exceptions / decorators / validators / services(去 chat/vector_store/model/model_fallback) / utils(去 response/export/minio/ppt) + 顶层 `events/`（转写后清理信号）。
- 应用外科手术改动剥离 FastAPI/Web：`__init__.py` 置空、`services/provider.py`（jsonable_encoder + kombu.uuid → stdlib）、`services/note.py`（删 HTTPException）、`services/transcriber_config_manager.py`（routers.config → 新增 `utils/model_status.py`）。
- 所有文件 `py_compile` 语法通过。
- 文档：更新 `docs/02-架构设计.md`（vendored 边界与改动）、`VENDOR.md`（模块清单 + 同步步骤）。

## 节点 3：MCP 服务（2026-07-31）

- 编写 `bilinote_mcp/config.py`（环境/数据目录初始化，先于 `app.*` import）与 `bilinote_mcp/server.py`（FastMCP，14 个工具 + 后台任务线程）。
- 补齐遗漏子包：`app/downloaders/douyin_helper/`（ABogus 签名）、`app/downloaders/kuaishou_helper/`；补依赖 `gmssl`、`blinker`。
- 文档：更新 `docs/02`（MCP 层设计与运行时约定）、`docs/04`（工具参考表）、`docs/03`（能力清单对齐）。

## 节点 4：Skill（2026-07-31）

- 编写 `.claude/skills/bilinote/SKILL.md`（agent 工作流、安装、配置、故障排查）。
- 文档：更新 `docs/04`（Skill 章节与安装方式）。

## 节点 5：打包与安装（2026-07-31）

- 依据 vendored 模块实际 import 定稿 `pyproject.toml` 运行时依赖（裁剪自 backend/requirements.txt：去掉 FastAPI/uvicorn/chromadb/celery/导出栈等；补 gmssl、blinker、fastmcp）。
- 编写 `install.sh`（venv + 安装 + `claude mcp add` 注册 + 链接 skill）、`bilinote-mcp` console script、`.mcp.json` 示例。
- 修复 MCP stdio 关键问题：`app/utils/logger.py` 控制台日志改走 **stderr**（stdout 必须只承载 JSON-RPC）；进程级把 vendored 代码里的裸 `print()` 重定向到 stderr。
- 修复 `list_models`/`generate_note` 对 `get_models_by_provider`（返回 dict）的字段访问。
- 文档：更新 `docs/04`（安装/注册/配置/故障排查全流程）、`docs/03`（验收标准收尾）。

## 节点 6：验证（2026-07-31）

- **安装**：`uv sync` 干净安装（Python 3.12），生成 `bilinote-mcp` console script。
- **MCP stdio**：initialize 握手成功，`tools/list` 返回 14 个工具；日志全部走 stderr，不污染协议。
- **健康检查**：ffmpeg ok、db ok。
- **转写**：`download_transcriber_model("tiny")` 下载成功，whisper tiny 将测试语音正确识别为中文（语言=zh）。
- **端到端**：`generate_note(本地 wav)` 完整跑通 下载→转写→**LLM 步骤**，用假 key 在 SUMMARIZING 干净失败（401 鉴权错误）——证明流水线到 LLM 边界全部可用；因无真实 API key，最终 Markdown 生成未实跑（上游已验证代码）。
- **工具矩阵**：9 项检查全 PASS（health_check / validate_url×4 / set-get_transcriber / 14 工具 / tiny 已下载）。
- **遗留**：`local_downloader` 封面提取对纯音频文件非致命化（改进）；`list_models` 字段访问修复。
- 文档：核对 `docs/` 与实现一致。
