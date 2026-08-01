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
| 视频理解默认（setup ③） | 用户说「用默认」时不传 `video_understanding`/`video_interval` 即套用（默认关/6s） |
| 评论/弹幕整合默认（setup ③） | 用户说「用默认」时不传 `include_comments`/`comments_limit` 即套用（默认关/20 条） |
