# CHANGELOG

按关键节点记录项目变更（日期 + 做了什么 + 文档改了什么）。

## 维护（2026-08-01）

- **README/docs 增补「开发版（dev 分支尝鲜）」**：dev 版安装（MCP `@dev` 覆盖 + marketplace 指 dev）与 main↔dev 切换/恢复命令、CLI 用 dev、共用数据目录等注意事项。README 中英 / docs/04 同步。
- **修「第二个工具调用挂起」（stderr 管道死锁）+ 并发门禁放宽 + subagent 编排**：
  - **根因**：后台任务大量日志/vendored print 写 stderr，Claude Code 客户端未及时排空 → stderr 管道（~64KB）塞满 → 服务器 logging 持锁阻塞 → 事件循环停 → 后续调用挂起。**修复**：MCP server 启动早期把 stderr 重定向到 `data/logs/mcp_stderr.log`（`os.dup2` + `sys.stderr`），协议只用 stdin/stdout，stderr 进文件不影响；实测修复后 stderr 未排空时第二个调用 0.0s 返回。
  - **并发门禁放宽**：从「有进行中任务就拒绝（强制串行）」改为「最多 `BILINOTE_MAX_WORKERS`（默认 3）个进行中任务，超出拒绝」—— 允许 subagent 并行提交多视频。
  - **SKILL**：多视频 → 主 agent 对每个视频起一个 subagent（各自 generate_note + 轮询 + 汇报），主 agent 汇总；主 agent 自己不在同一回合连续调用多个 generate_note。
  - README（中英）/ docs/04 / reference 同步。
- **修 MCP 在笔记目录泄漏 config/logs**：三个 CWD 相对路径的创建者 —— ① `server.py` 的 `app.*` 导入在 `setup_environment()` 之前（logger 用 `./logs`）；② `ProxyConfigManager` 硬编码 `config/proxy.json`；③ `WhisperModelRegistry` 硬编码 `config/whisper_models.json`。全部改为尊重 `BILINOTE_CONFIG_DIR`/`BILINOTE_DATA_DIR`（`server.py` 导入顺序调整 + 两个 config 管理器默认路径改环境变量），任意 CWD 启动都不再在笔记目录/当前目录冒出空的 config/logs。
- **笔记文件夹结构（一篇一夹）+ 评论/弹幕可视化**：
  - 指定 `notes_dir` 时每篇笔记一个文件夹 `<notes_dir>/<笔记标题>/note.md`（标题取 LLM 生成的笔记 H1，回退视频标题；同名冲突加短 task_id 后缀）—— 多篇互不覆盖；`NoteResult.note_dir` 返回真实子文件夹，server 据此报告位置。
  - `include_comments=True` 时 prompt 强制笔记输出「观众观点」章节（总结弹幕/评论区反复出现的观点、补充、纠错；无可总结写「（无）」）—— 之前只是「仅供参考」喂 LLM，笔记里不可见。
  - README（中英）/ docs/04 / CHANGELOG 同步。
- **SKILL 重构（核心精简 + reference 文件夹）**：SKILL 过长导致 agent 注意力分散、跳过「必须先确认参数」。`skills/bilinote/SKILL.md` 重写为「⚡ 强制规则（违反=任务失败，含必须先确认参数）+ 紧凑工作流」；工具接口/配置挪到 `reference/tools.md`、故障排查/并发/B站细节挪到 `reference/troubleshooting.md`（agent 按需 Read）。强制「必须先问参数」放到正文最前。
- **MCP 取消任务 + 强制串行**：
  - 新增 `cancel_note(task_id)` 工具：取消进行中/排队任务（协作式 —— `threading.Event`，任务在各阶段边界 + LLM chunk 循环检查；排队任务可 `Future.cancel()` 释放 worker 槽）。`TaskStatus` 加 `CANCELLED`；`wait_for_note` 终止状态含 `CANCELLED`（不再空转超时）。
  - **`generate_note` 强制串行**：同一会话有进行中任务时**直接拒绝**新提交（并行提交多个 `generate_note` 会让 Claude Code 客户端挂起）—— 必须一次一个：提交 → 等到 SUCCESS/FAILED/CANCELLED → 再提交下一个；真正并行请开多个会话。
  - SKILL/README（中英）/docs/04 同步：串行 + cancel_note 说明。
  - 取消异常/助手独立到 `app/exceptions/task.py`（避免 note→gpt_factory→universal_gpt→note 循环导入）。

- **setup 向导 LLM 配置：连通性检测 + 默认模型**：
  - 供应商改为「管理」子菜单：✏ 编辑 key/base_url / 🔌 检测连接 → 列出可用模型 → 设默认 / ← 返回（选中供应商进入，非再点即编辑）。
  - 检测 = OpenAI 兼容 `GET /v1/models`（一次验证 key/base_url 并拿到模型列表，超时 15s）；`/v1/models` 不可用（部分中转站/自建网关）时降级「最小对话请求」chat 探测。
  - **默认模型**持久化到 `config/app_config.json`（`default_model:{provider_id}`，同时 dedup 写回 models 表）；`generate_note` **未指定 `model_name` 时优先用配置的默认模型**，再退 DB 第一条。
  - 新增非交互 `bilinote-mcp providers test <id> [--default MODEL]`；`providers list` 显示 `默认=` 列。
  - 纯文本兜底向导（无 InquirerPy）同步支持「检测连接 + 选默认」。
  - 新增 `bilinote_mcp/provider_probe.py`（`probe_models` / `probe_chat` 唯一 probe 源）；server 的 `_fetch_live_models` 改为委托它（Ollama 等无 key 供应商现在也能实时列模型）。
  - 坑位处理：选择项 name 不含 ANSI（原样显示）；探测用未掩码 key（`get_provider_by_id`）；子菜单左键只退一级；空 key 归一化只影响探测不影响生成。
  - README（配置①/`providers test`/速查表）、docs/04（子菜单 + 默认模型）、SKILL.md（默认模型一行）同步。
- **setup ③ 其他新增「视频理解默认」+ SKILL 强制问参数**：
  - setup ③ 可配**视频理解默认**（开/关 + 帧间隔秒数），持久化 `app_config.json`（`video_understanding` / `video_interval`）。
  - `generate_note` 的 `video_understanding` / `video_interval` 改为 `Optional`：**不传时**自动套用 setup 默认（默认关 / 0→6s）；**显式传入始终覆盖**（向后兼容）。
  - SKILL「确认参数」强化：**没有明确信息前必须问**用户 —— 是否启用视频理解 + 帧间隔秒数都要问；**即使配了默认，本次也要先问**，只有用户说「你定/用默认」才用默认值。
  - 纯文本兜底向导补「③ 其他（视频理解默认）」。
  - README / docs/04（③ 描述 + 视频理解章节）、SKILL.md 同步。
- **SKILL「后续优化」步骤**：生成成功后 agent **必须问用户**是否要根据已生成笔记 + 提取的字幕（`result.transcript` 完整转写）做后续优化（补齐细节/修正不一致/增强结构）；agent 侧精修、**不新增 MCP 工具**；转写过长时如实告知限制并按章节精修；不写回 `note_dir` 原始产物。
- **SKILL 强制问清单扩展 + `extras` 自定义风格**：
  - **笔记风格改为强制提问**：把**真实 9 种风格**（从 `app/gpt/prompt_builder.py` `note_styles` 核对）呈现给用户选 —— `minimal` 精简 / `detailed` 详细 / `academic` 学术 / `tutorial` 教程 / `xiaohongshu` 小红书 / `life_journal` 生活向 / `task_oriented` 任务导向 / `business` 商业风格 / `meeting_minutes` 会议纪要；没有明确信息前不得自行默认 `detailed`。
  - **支持自定义风格**：`generate_note` 新增 `extras` 参数（追加到 prompt 末尾的自定义指令，note.py 本已支持、之前未暴露）—— 用户自定义风格时把描述经 `extras` 传入。
  - **后续优化提前到步骤 4**（与模型/视频理解等并列强制问「生成后要不要基于字幕优化」），步骤 9 强化为「**必须处理，不能跳过**」（已答过则直接执行，没问过则呈现后必须补问）。
  - README / docs/04（工具参考补 `extras`）同步。
- **SKILL 并发流程修正（一次发一个，服务端并发）**：实测证明 MCP server 对并行 `generate_note` 全部 0.01s 返回（3 个并行毫秒级完成），**卡的是 Claude Code 客户端** —— 同一条消息塞多个并行 MCP 工具调用时，最后一个调用的响应收不到、任务也未提交（用户实测 3 集只提交成功 2 集）。修正：**一次发一个 `generate_note`**（拿 task_id 再发下一个），任务照常在服务端并发执行（`BILINOTE_MAX_WORKERS=3`）；多任务轮询用轻量 `get_task_status` 快照轮询，不用阻塞的 `wait_for_note`。提交前先告诉用户要依次提交哪些任务。README / docs/04 同步。
- **SKILL 后续优化强调「挖细节、讲透」**：优化执行改为以字幕/转写为权威源 —— **从里面挖出笔记没覆盖的细节、把每个要点展开讲透**（补充背景/原因/步骤/例子/关键数据与结论）；同时**保留原有的「补齐遗漏、修正不一致、增强结构」**三元组。
- **CI + 分支保护 + 版本发布**：
  - 新增 `.github/workflows/ci.yml`：push `main`/`dev` 或 PR 时跑冒烟（`uv sync` + server import + MCP tools/list + CLI），防止坏 commit 上线（`uvx --from git+` 安装直接拉 main，CI 是门禁）。
  - 新增 `.github/workflows/release.yml`：push `v*` tag 自动建 GitHub Release（**tag 驱动发布**）。
  - 新增 `dev` 分支：日常开发走 dev（功能分支 → PR → dev），dev 稳定后 PR → main 发布。
  - `main` 分支保护：要求 PR + CI 绿 + 1 个 review，直接 push 被拒 → **main 永远可用**。
  - 发布 `v0.1.0`（首个稳定版；稳定安装：`uvx --from git+https://github.com/HuangYincan/BiliNote-MCP@v0.1.0 bilinote-mcp`）。
- **「评论/弹幕整合」配套（setup CLI / SKILL / docs）**：
  - 契约：`generate_note` 新增 `include_comments`（是否整合弹幕+评论区观点）/ `comments_limit`（评论条数，默认 20）；`app_config` 新键 `include_comments`(bool, 默认 False) / `comments_limit`(int, 默认 20)；新增独立工具 `fetch_comments(video_url, limit=20)` / `fetch_danmaku(video_url)`（需 B 站 SESSDATA；抓取失败不阻断笔记）。
  - setup ③ 新增「评论/弹幕整合默认」（开/关 + 评论条数，`max(1,int)` 异常兜底 20），持久化 `app_config.json`；主菜单 ③ 文案、纯文本兜底向导同步补上。
  - SKILL「确认参数」新增**必须问**条目：是否整合弹幕、评论区观点 —— 默认否，要则问条数；需 SESSDATA，没配引导 `bilinote-mcp login bilibili` 扫码；**即使 setup 配了默认本次也先问**，只有用户说「你定/用默认」才用默认值；配置要点 / 故障排查表补对应行。
  - README / README_EN / docs/04（③ 描述、新增「整合弹幕+评论区观点」章节、工具参考补 `fetch_comments`/`fetch_danmaku` 与 `include_comments`/`comments_limit` 参数）同步。

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
- **模型管理 UX**：本地模型「已下载」和「下载完成」两种情况都**暂留**，显示模型位置 + 询问是否卸载（新增 `_show_uninstall_option` 助手、`_model_dir` 定位目录），不再一闪而过。
- **并发/多会话说明**：README 新增「环境变量（可选）」表（含 `BILINOTE_MAX_WORKERS`）与「多会话并行」说明；SKILL 新增「并发与多会话」章节（任务按 task_id 隔离、每会话默认 3 并发、资源注意）。
- **修 `ready: true` 误报**：`is_model_ready` 只查模型文件、没查环境是否装了对应包（mlx_whisper 可选）→ 文件在但包没装时误报就绪、任务才失败。现在用 `importlib.util.find_spec`（轻量、不 import）检查包可用性，mlx 缺包时 `ready=false` + 清晰原因；`transcriber_provider` 的误导文案（指向不存在的设置页）也改成 CLI 指引。
- **README 快速开始**：方式一下补「插件默认 MCP 不含 mlx-whisper」说明 + 手动覆盖命令（`claude mcp add bilinote -- uvx --from ... --with mlx-whisper ...`）及冲突处理（`claude mcp remove` 或改用 `~/.local/bin/bilinote-mcp`）。
- **修「笔记生成但任务 FAILED」**：`note.py` 的 `_note_dir` 未初始化 —— 未插图片且未指定 `notes_dir` 时，`if _note_dir is not None` 引用未赋值变量 → UnboundLocalError → 生成产物已落盘但任务标记 FAILED。补 `_note_dir = None` 初始化。

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
