# 故障排查 + 并发/多会话 + B 站细节

> 本文件是 SKILL 的参考（非核心）。遇到问题时用 Read 读取。

## 故障排查

| 现象 | 处理 |
|------|------|
| `health_check` 显示 `ffmpeg: missing` | 让用户 `brew install ffmpeg`（Linux: `apt install ffmpeg`），装完再跑 |
| `generate_note` 报「需要 provider_id」 | 先 `list_providers` 看内置供应商；空 key 用 `update_provider` 填，自建用 `add_provider` |
| 报「供应商还没有可用模型」 | `list_models(provider_id)` 实时拉取，或 `add_model` 手动加模型名 |
| 转写一直失败、提示模型未下载 | 问用户：`bilinote-mcp transcriber download <size>` 下载，或切云端（`set_transcriber("bcut"/"groq")`）—— 不要静默切换 |
| 任务卡在 `INITIALIZING` | 首次使用 fast-whisper 正在下载模型，耐心等；模型大可改用云端转写 |
| B 站下载报 `fatal` / playurl 412 | 已修复（yt-dlp fatal 透传）；仍失败则 `set_downloader_cookie(platform="bilibili", cookie=...)` 后重试 |
| 想用 B 站 **AI 字幕**跳过语音识别 | 引导用户跑 `bilinote-mcp login bilibili`（扫码自动存 SESSDATA），或手动 `set_downloader_cookie(...)`。AI 字幕需登录态；`raw_info.subtitles={}` 只反映手动 CC，AI 字幕在 automatic_captions |
| 整合评论/弹幕时评论拿不到 | 未配 B 站 SESSDATA —— 引导用户 `bilinote-mcp login bilibili`；抓取失败**不阻断**笔记生成（跳过该部分） |
| 链接不支持 | 只支持 bilibili / youtube / douyin / tiktok / kuaishou / 本地文件路径 |
| 视频下载 403 / 需会员 | `set_downloader_cookie` 配置平台 Cookie |
| `generate_note` 报「已有进行中的任务」 | 正常 —— 任务一次只发一个：先 `get_task_status`/`wait_for_note` 等上一个完成（或 `cancel_note` 取消）再提交 |

## 并发与多会话

- 每个会话独立起一个 MCP server 进程，任务按 `task_id` 隔离 —— **多个会话可并行生成不同视频的笔记**。
- **本会话内任务强制串行**：`generate_note` 有进行中任务时**直接拒绝** —— 必须一次一个：提交 → 等到 `SUCCESS`/`FAILED`/`CANCELLED` → 再提交下一个。**不要在同一消息里并行塞多个 `generate_note`**（Claude Code 客户端会挂起、最后一个响应收不到）。
- **真正并行**：开多个会话。
- **轮询**：用轻量 `get_task_status(task_id)` 快照轮询；**不要**用阻塞的 `wait_for_note`（会卡住当前轮次，看起来像挂起）。
- 提交前把计划告诉用户（如「我会依次提交 p10/p11/p12，每个完成后提交下一个」）。
- 资源：whisper/MLX 转写吃 CPU/内存，太多会话并行会卡顿；所有会话共用同一 SQLite，极端并发偶发写冲突。

## B 站细节

- **SESSDATA**：AI 字幕、评论、弹幕的高质量抓取需要登录态。让用户在终端 `bilinote-mcp login bilibili` 扫码自动获取保存；或手动 `set_downloader_cookie(platform="bilibili", cookie="SESSDATA=...")`。
- **字幕优先级**：平台字幕（人工 > AI）> 语音转写。AI 字幕需登录态。
- **弹幕**：`fetch_danmaku` 返回高密度时段 + 高频词（时间窗聚类），注入 `include_comments=True` 时作为参考。
- **评论**：`fetch_comments` 返回热门评论（likes 排序、翻页去重）。评论抓取失败不阻断笔记生成。
