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
- README / docs/04「前提」补：本地 whisper 下载、GPU 加速（NVIDIA 用 `--with torch` 走 CUDA、macOS 用 `mlx-whisper`）。
- **setup 交互升级**：改用 InquirerPy —— 方向键选择 + 高亮、主菜单随时切换、可返回上一步，做成**随时可反复进入修改的配置入口**（① LLM 供应商 ② 转写引擎 ③ 其他/Cookie/笔记位置）。新增 `_download_whisper` 助手（transcriber download 也复用）；无 InquirerPy 时回退纯文本向导；非 TTY 优雅退出。
- **setup UX 打磨**：① 每步清屏 + 彩色/加粗标题（不留历史信息）；② **左键 = 返回上一级**（所有 select/text/secret 绑定 interrupt）；③ 平台 Cookie 改为下拉选择（bilibili/youtube/douyin/kuaishou/其他 + 返回）；④ **默认笔记位置持久化**（`config/app_config.json`，`generate_note` 读取：notes_dir → app_config → env → 默认）；⑤ 本地模型下载流程更清晰（已下载则跳过、未下载才确认）。
- **修复向导崩溃**：InquirerPy 左键绑定写错（缺 `key` 字段 + 用了不存在的 `cancel` action）导致 `KeyError: 'key'` —— 改为 `{"interrupt": [{"key": "left"}]}`（interrupt 是已注册 action，与 Ctrl-C 同效），select/text/secret/confirm 构造验证通过。
- **修复 B 站下载失败**：`bilibili_dm_patch` 未透传 yt-dlp 2026.07.04 新增的 `fatal` 参数导致 `TypeError` —— 已透传，实测用户视频 playinfo 正常。
- **SKILL 确认参数强化**：① LLM 模型 `list_models` 后**列出让用户选**（不悄悄自定）；② 本地转写模型未就绪时**必须问用户**下载或切云端（不静默切换）；③ 故障排查补 B 站 `fatal`/playurl 412 处理。
- **setup 补 mlx-whisper 下载入口**：之前 `_wizard_transcriber` 只在 fast-whisper 分支问下载，mlx 漏了；现本地引擎（fast-whisper/mlx）都检查已下载并询问。`bilinote-mcp transcriber download` 新增 `--engine mlx-whisper`（macOS）。
- **setup 下载 UX**：① 确认下载后进入**专门「下载 X」界面**（进度条 + 完成停留，按回车返回，不再立刻跳回）；② 下载改用 `snapshot_download` + 自定义 tqdm 进度条（已验证 faster-whisper 能从同一缓存加载）；③ 修「当前尺寸」显示位置（只在当前引擎上显示，不再误标到其它引擎）。
- **修两处向导问题**：① InquirerPy 选择项 `name` 里嵌 ANSI 转义码会原样显示（`^[[1;32m...`）—— 改为纯文本标记；② mlx-whisper 未安装时给出明确指引（`--with mlx-whisper` 装法）而非 `No module named 'mlx_whisper'`（向导检测 mlx 可用性 + `_download_mlx_model` 抛清晰错误）。
- **向导 mlx 缺失不再卡住**：选 mlx-whisper 但环境没装时，显示指引后**主动问「改用 fast-whisper？」**（默认是），确认即切换并继续下载流程，不再「选完引擎没反应」。
- **CLI 参数分发更严**：`bilinote-mcp` 收到未知参数（如 `--with` 放错位置）时**报错 + 用法提示**，不再静默启动 MCP server；只有**无参数**时才是 MCP server 模式（stdio 客户端启动）。
- **修向导选 mlx 后卡死**：mlx 路径会 `import mlx_whisper_transcriber` → `import mlx_whisper`（加载 MLX 框架很重、可能卡顿）。改为轻量：`check_mlx_whisper_model_exists` 用内联 repo 映射（不 import mlx_whisper，实测 0ms），mlx 可用性用 `find_spec` 判断；加「检查模型状态…」提示。
- **修 mlx 下载失败（numba 循环导入）**：`_download_mlx_model` 之前 import `mlx_whisper_transcriber`（其依赖链 numba 等有循环导入风险）。下载其实只需 `huggingface_hub.snapshot_download` —— 改为用内联 `MLX_REPO_MAP`，纯 HF 下载，不碰 mlx_whisper。
- **`notes_dir` 现在总是写 note.md**：之前只有截图模式才写便携笔记，用户指定 `notes_dir` 却不插图片时笔记不会写入该目录（agent 只能手动提取）。现在指定 `notes_dir`（或截图模式）都会把 `note.md` 写到目标目录，且 `result.note_dir` 总会返回（`_run_note_task` 按 notes_dir → 截图 顺序判断）。SKILL/README 同步。
- **B 站 AI 字幕说明 + 提示**：功能已实现（API 直拉支持 `ai_type`、yt-dlp 兜底 `writeautomaticsub`），但 B 站 AI 字幕需 **SESSDATA cookie**；无 cookie 时 API 返回空列表 → 只能走语音识别。`raw_info.subtitles={}` 只反映手动 CC（AI 字幕在 automatic_captions）。给 `download_subtitles`/`fetch_subtitles` 加了「配置 SESSDATA 即可用 AI 字幕跳过转写」的日志提示；SKILL 故障排查补对应项。
- **B 站扫码登录 `bilinote-mcp login bilibili`**：终端渲染 ASCII 二维码（qrcode 库）→ 用户 B 站 App 扫码 → 自动轮询 → 提取并保存 SESSDATA（`CookieConfigManager`）。setup 向导「③ 其他」加「B 站扫码登录」选项。SKILL：B 站视频优先 AI 字幕，引导用户扫码/手动；README/docs 补命令与说明。已验证二维码渲染 + SESSDATA 提取保存（mock 测试）。
- **修扫码登录两处**：① 状态码搞反 —— B 站 `86101` 是**未扫码**（安静等待）、`86090` 才是已扫码待确认；② 成功 URL 可能是 **crossDomain ticket**（不带 SESSDATA query）—— 改为用 session 跟随重定向、从 Set-Cookie 提取 SESSDATA。均已 mock 验证。
- **修 SESSDATA 多条 cookie 冲突**：跟随 crossDomain URL 时 B 站会给不同 domain/path 设多条同名 SESSDATA，`requests.cookies.get()` 抛 `CookieConflictError` —— 改为手动遍历取第一条（mock 验证多 cookie 场景）。
- **扫码登录成功/过期后暂留**：成功保存或二维码过期后显示结果并「（按回车返回）」，不再立刻跳回上级菜单（与下载流程一致）。

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
