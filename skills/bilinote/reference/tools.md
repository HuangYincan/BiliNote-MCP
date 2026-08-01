# 工具接口速查 + 配置要点

> 本文件是 SKILL 的参考（非核心）。需要具体工具参数/配置时用 Read 读取。工具签名也可直接从 MCP 工具 schema 获取。

## 生成笔记

### `generate_note(video_url, platform?, quality?, provider_id?, model_name?, format?, style?, screenshot?, link?, video_understanding?, video_interval?, grid_size?, notes_dir?, extras?, include_comments?, comments_limit?)`
- 提交视频，异步生成，返回 `{task_id, status: "PENDING", platform, model_name}`。
- `quality`: fast / medium / slow。
- `model_name` 省略：用 setup 默认模型，否则供应商第一个可用模型。
- `style`: 9 种（minimal/detailed/academic/tutorial/xiaohongshu/life_journal/task_oriented/business/meeting_minutes）；自定义用 `extras="笔记风格要求：<描述>"`。
- `video_understanding=True` + `video_interval`（默认 6）+ `grid_size`（默认 [3,3]）：视频理解，**需多模态模型**。
- `include_comments=True` + `comments_limit`（默认 20）：整合 B 站弹幕+评论（需 SESSDATA；失败不阻断）。
- `screenshot=True` + `format=["screenshot"]`：插单张截图，产出便携笔记 note.md + Assets/（相对引用）。
- `notes_dir`: 便携笔记目录（指定即写 note.md，即使不插图片）。
- **任务一次只发一个**：有进行中任务时 server 直接拒绝（先等上一个 SUCCESS/FAILED/CANCELLED）。

### `get_task_status(task_id)`
- 轻量快照轮询。返回 `{status, message, task_id, result?}`；`SUCCESS` 时 `result.markdown` / `result.transcript` / `result.note_dir`。

### `wait_for_note(task_id, timeout=120, poll_interval=3)`
- **阻塞**等 SUCCESS/FAILED/CANCELLED；**多任务/对话中勿用**（会卡住当前轮次）。等完成优先 `get_task_status` 轮询。

### `cancel_note(task_id)`
- 取消进行中/排队任务（协作式，下一阶段边界生效）；返回 `{ok, task_id, status}`。

## AGENT 直接生成（准备素材）

### `prepare_note_material(video_url, platform?, video_understanding?, video_interval?, grid_size?, include_comments?, comments_limit?)`
- **只准备素材、不调用配置 LLM**：跑下载 → 转写 →（可选）抽帧 →（可选）评论/弹幕，返回素材包（`kind: "material"`）。
- 参数与 `generate_note` 对应；不传 `video_understanding` / `video_interval` / `include_comments` / `comments_limit` 时套 setup 默认（视频理解默认关 / 6s，评论默认关 / 20 条）。
- 返回 `{task_id, status: "PENDING", platform}`；`get_task_status` 轮询到 `SUCCESS` 时 `result` 结构：
  ```json
  {
    "kind": "material",
    "title": "视频标题",
    "transcript": {
      "language": "zh",
      "full_text": "完整转写全文",
      "segments": [{"start": 0, "end": 5, "text": "..."}]
    },
    "frames": ["file:///绝对/路径/frame_0001.jpg"],
    "comments_danmaku": "【弹幕】…\n【热门评论】…",   // 字符串；无则 null
    "video_path": "/绝对/路径/video.mp4",
    "audio_path": "/绝对/路径/audio.mp3"
  }
  ```
- 用途：**AGENT 直接生成**（agent_direct）—— AGENT 自己读 `transcript.full_text`、用 Read 看 `frames` 图片、按 `comments_danmaku` 写「观众观点」章节，不经配置 LLM。

## 全自动 / 手动模式

- **任务开始必须先问用户**「全自动」还是「手动」。
- **全自动**：用 setup 默认参数（默认模型 / `default_style` 默认 detailed / 视频理解默认 / 评论默认 / 截图默认 / `agent_direct` 默认关），**不逐个问**；`generate_note` / `prepare_note_material` 不传 style / screenshot / video_understanding / include_comments / agent_direct 即套默认。
- **手动**：逐个确认参数（模型、风格、视频理解、评论/弹幕、截图、是否 AGENT 直接生成），用户明确指定或说「你定」前不调用生成类工具。
- 默认值都可由 setup ③ 覆盖；`agent_direct` 默认关（行为与之前一致，即普通 LLM 生成）。

## 清理与存储

任务产生的文件（下载的视频/音频、转写、截图、临时文件）会堆积占存储，AGENT 可自助清理。

### `get_task_files(task_id)`
- **先查后清**：列出该任务在磁盘上相关的文件/目录，返回 `{task_id, manifest_paths, existing}`。
- `manifest_paths` 来自 `note_results/{task_id}.manifest.json`（流水线尽力而为记录）；`existing` 是真实存在的文件/目录（含 `dl_{task_id}/`、便携笔记目录等）。

### `cleanup_note(task_id, include_note=False)`
- 删某任务生成的**中间产物**（下载视频/音频、转写、截图、`dl_{task_id}/`、`{task_id}/Assets` 等）。
- `include_note=False`（默认）：**保留最终笔记** `note.md` / `note_dir`；
- `include_note=True`：连最终笔记一起删（含 manifest）。
- 只删 manifest 记录 / `note_results/{task_id}*` / `dl_{task_id}` 前缀的文件，`resolve()` 校验在数据目录内（防路径穿越）。返回 `{deleted, missing, errors, note_kept}`。

### `cleanup_all(include_config=False, include_models=False)`
- **全局清理**（恢复出厂）：清空 `note_results/*`、`static/screenshots/*`、`logs/*` 的所有任务产物。
- `include_config=False`（默认）：**保留** `config/`（LLM key / cookie / 转写设置）；`include_config=True` 才清。
- `include_models=False`（默认）：**保留** `models/`（已下载模型可复用，重下成本高）；`include_models=True` 才清。
- 数据库记录（`bili_note.db`）不动。

## 供应商 / 模型

- `list_providers()` —— 供应商列表（key 掩码）。空 key 让用户在终端 `bilinote-mcp providers set <id> --api-key '...'`。
- `add_provider(name, api_key, base_url, type)` / `update_provider(provider_id, ...)` —— 新增/更新（**填 key 建议走 CLI，不进对话**）。
- `list_models(provider_id)` —— 实时 /v1/models，回退本地 DB。
- `add_model(provider_id, model_name)` —— 手动加模型名（接口不可用时）。

## 转写

- `get_transcriber_config()` —— 当前引擎/尺寸/就绪（`ready=false` 时先下载或切云端）。
- `set_transcriber(transcriber_type, whisper_model_size?)` —— 切引擎（fast-whisper/groq/bcut/kuaishou/mlx-whisper）。
- `list_transcriber_models()` / `download_transcriber_model(model_size, transcriber_type?)` —— 模型管理（下载为后台任务）。

## 其它

- `health_check()` —— ffmpeg/db/whisper 就绪状态。
- `validate_url(url)` —— 识别平台（bilibili/youtube/douyin/tiktok/kuaishou/local）。
- `set_downloader_cookie(platform, cookie)` —— 设置平台 Cookie（如 B 站 `SESSDATA=...`）。
- `fetch_comments(video_url, limit=20)` —— B 站热门评论（供生成前预览）。
- `fetch_danmaku(video_url)` —— B 站弹幕汇总（高密度时段 + 高频词）。

## 配置要点

| 场景 | 操作 |
|------|------|
| 给内置供应商填 key | 用户在终端 `bilinote-mcp providers set <id> --api-key 'sk-...'`（agent 不碰 key） |
| 自建/新增供应商 | `add_provider(name, api_key, base_url, type)` |
| 查看供应商 / 模型 | `list_providers()`（掩码）/ `list_models(provider_id)` |
| 切本地转写 | `set_transcriber("fast-whisper", "small")` + `download_transcriber_model("small")` |
| 切云端转写 | `set_transcriber("groq")`（groq key 用 CLI 填） |
| B 站登录/AI 字幕/评论 | 用户在终端 `bilinote-mcp login bilibili` 扫码（存 SESSDATA）；或 `set_downloader_cookie(platform="bilibili", cookie="SESSDATA=...")` |
| 本地文件 | `generate_note(video_url="/绝对/路径/x.mp4", platform="local", ...)` |
| 视频理解默认（setup ③） | 用户说「用默认」/ 全自动模式时不传 `video_understanding`/`video_interval` 即套用（默认关/6s） |
| 评论/弹幕整合默认（setup ③） | 用户说「用默认」/ 全自动模式时不传 `include_comments`/`comments_limit` 即套用（默认关/20 条） |
| 笔记默认（setup ③ 新增） | `default_style`（默认 detailed）/ `default_screenshot`（默认关）/ `agent_direct`（默认关，行为与之前一致）；全自动模式不传即套用 |
| AGENT 直接生成 | `prepare_note_material(video_url, ...)` → 轮询 SUCCESS → 读素材包 → **AGENT 自己写笔记**（不调用配置 LLM） |
