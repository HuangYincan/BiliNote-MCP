---
name: bilinote
description: 使用 BiliNote-Mcp 的 MCP 工具把视频链接（B站/YouTube/抖音/快手/本地文件）生成 AI Markdown 笔记。触发词：「生成视频笔记」「视频 → 笔记」「帮我给这个视频做笔记」「从 XX 链接做笔记」。当用户给出视频链接/本地视频并希望得到结构化笔记或总结时使用。
---

# BiliNote-Mcp —— 视频链接 → AI Markdown 笔记

把 [BiliNote](https://github.com/JefferyHcool/BiliNote) 的核心能力（下载 → 转写 → LLM 总结）封装成了 MCP 工具。**无需启动任何后端服务** —— 流水线完全在 MCP server 进程内运行。

## 前提

1. **MCP server 已注册**（`claude mcp list` 应能看到 `bilinote`，或项目 `.mcp.json` 已配置）。
2. **FFmpeg 已安装**（`ffmpeg -version`）。缺失时先让用户安装，再调用 `health_check` 确认。
3. **至少一个 LLM 供应商可用**（内置已预置：`list_providers` 查看；空 key 用 `update_provider` 填；自建用 `add_provider`）。
   - **安全红线：绝不要让用户在对话里发 API key** —— 对话会发到你的 LLM 上游。让用户在 **Claude Code 之外的独立终端**执行 `bilinote-mcp providers set <id> --api-key '...'`。填好后 `list_providers` 显示 `key=已填`，你直接用它，**不需要也不应该看到明文 key**。
   - 用户没有 key？**优先用 Ollama**（本地免费、无需 key）：`list_models("ollama")` 有模型就直接 `generate_note(provider_id="ollama", model_name=...)`；
   - 否则引导用户注册免费额度（Groq/DeepSeek 等）后按上面方式在终端填 key。
4. 转写引擎二选一：
   - 本地 `fast-whisper`：需先 `download_transcriber_model("tiny")`（或更大尺寸）下载模型；
   - 云端 `groq` / `bcut`：`set_transcriber("groq")`（需要对应 API key 配置为 id 为 `groq` 的供应商）。

## 标准工作流（给视频做笔记）

1. **`health_check`** —— 确认 ffmpeg/db 就绪；若 `ffmpeg: missing` 先让用户装 FFmpeg。
2. **`validate_url(url)`** —— 确认链接受支持、识别平台。不支持就明确告诉用户。B 站视频**优先用平台字幕（含 AI 字幕）跳过语音识别**；AI 字幕需 B 站 SESSDATA cookie —— 没配时任务会走语音识别，告诉用户可 `bilinote-mcp login bilibili` 扫码自动获取（或手动填 SESSDATA），之后就能直接用 AI 字幕。
3. **`list_providers()`** —— 找一个启用的 LLM 供应商（内置已预置，key 为空）。空 key 让用户用 CLI 填（`bilinote-mcp providers set <id> --api-key '...'`，**agent 不碰 key**）；再 `list_models(provider_id)` / `add_model` 确认模型可用。
4. **确认参数（用户没指定时逐项询问，给出默认值）**：
   - **LLM 模型**：先 `list_models(provider_id)` 拿可用模型，**列出给用户选**（如 `gemini-2.5-flash` / `deepseek-chat`），**不要悄悄自己定**；
   - **语音转写引擎**：默认本地 fast-whisper（问是否要云端 groq/bcut）。**若所选引擎的本地模型未下载就绪**（`get_transcriber_config` 显示 `ready=false`），**必须问用户**：`bilinote-mcp transcriber download <size>` 下载，还是切云端 —— **不要静默切换**；
   - **笔记风格**：默认 `detailed`（可选 minimal / academic / tutorial / xiaohongshu…）；
   - **是否视频理解**（看画面）：默认否；要则配多模态模型 + `video_understanding=True, video_interval=6, grid_size=[3,3]`；
   - **是否插入图片**：默认否；要则 `screenshot=True` + `format=["screenshot"]`，并问**笔记保存位置**（`notes_dir`，不指定用默认）；
   - 用户说「你定」就跳过追问，用默认值。
5. **`generate_note(video_url=url, provider_id=..., model_name=..., style=..., quality="medium", ...)`** —— 提交任务，拿到 `task_id`。
   - **用户指定了保存目录**：加 `notes_dir="/用户/给的/路径"` —— note.md 会直接写到那里（即使不插图片）；
   - 图片插入：加 `screenshot=True, format=["screenshot"]`（产出便携笔记 `note_dir/note.md` + `Assets/`，相对引用）；
   - 视频理解：加 `video_understanding=True, video_interval=6, grid_size=[3,3]`（**必须多模态模型**，如 `qwen-vl-plus` / `gpt-4o`；deepseek-chat 等纯文本模型不支持）。
6. **轮询**：`get_task_status(task_id)` 直到 `SUCCESS`（长视频可能要几分钟；也可 `wait_for_note(task_id, timeout=120)` 一次等 120 秒，超时再续）。
7. **拿到结果后**：`result.markdown` 就是笔记本体。若 `result.note_dir` 存在（用户指定目录或图片模式）：笔记文件在 `{note_dir}/note.md`，图片模式另有 `{note_dir}/Assets/`，**读图以 note_dir 为基准**。若用户指定了 `notes_dir` 但 `note_dir` 缺失，说明没写成文件，告诉用户。**直接阅读 Markdown 回答用户的所有问题** —— 不需要额外检索；若用户追问视频细节，可再读 `result.transcript`（完整转写）定位。
8. 把笔记呈现给用户（要点总结 + 关键章节 + 原文链接；图片模式告知 note_dir 位置）。

## 配置要点

| 场景 | 操作 |
|------|------|
| 给内置供应商填 key（DeepSeek/OpenAI/Qwen/Groq…已预置） | `update_provider(provider_id="deepseek", api_key="sk-...")` |
| 自建/新增供应商 | `add_provider(name, api_key, base_url, type)` |
| 查看供应商 | `list_providers()`（api_key 已掩码） |
| 查看/添加模型 | `list_models(provider_id)`；不可用则 `add_model(provider_id, "deepseek-chat")` |
| 切本地转写 | `set_transcriber("fast-whisper", "small")` + `download_transcriber_model("small")` |
| 切云端转写 | `update_provider("groq", api_key=...)` 后 `set_transcriber("groq")` |
| B站等需登录内容 | `set_downloader_cookie(platform="bilibili", cookie="SESSDATA=...")` |
| 本地文件 | `generate_note(video_url="/绝对/路径/xxx.mp4", platform="local", ...)` |

## 并发与多会话

- 每个会话独立起一个 MCP server 进程，笔记任务按 `task_id` 隔离，**多个会话可并行生成不同视频的笔记**，互不干扰。
- 本会话内最多 `BILINOTE_MAX_WORKERS`（默认 3）个并发笔记任务。
- 若用户想同时生成多个视频：可逐个 `generate_note` 提交（各自 task_id）后并行轮询；也可提示用户开多个会话。
- 注意资源：whisper / MLX 转写吃 CPU/内存，太多会话并行会卡顿；所有会话共用同一个数据库，极端并发偶发写冲突。

## 故障排查

| 现象 | 处理 |
|------|------|
| `health_check` 显示 `ffmpeg: missing` | 让用户 `brew install ffmpeg`（Linux: `apt install ffmpeg`），装完再跑 |
| `generate_note` 报「需要 provider_id」 | 先 `list_providers` 看内置供应商；空 key 用 `update_provider` 填，自建用 `add_provider` |
| 报「供应商还没有可用模型」 | `list_models(provider_id)` 实时拉取，或 `add_model` 手动加模型名 |
| 转写一直失败、提示模型未下载 | 问用户：`bilinote-mcp transcriber download <size>` 下载，或切云端（`set_transcriber("bcut"/"groq")`）—— 不要静默切换 |
| 任务卡在 `INITIALIZING` | 首次使用 fast-whisper 正在下载模型，耐心等；模型很大时可改用云端转写 |
| B 站下载报 `fatal` / playurl 412 | 已修复（yt-dlp fatal 透传）；仍失败则 `set_downloader_cookie(platform="bilibili", cookie=...)` 配置 Cookie 后重试 |
| 想用 B 站 **AI 字幕**跳过语音识别 | 引导用户跑 **`bilinote-mcp login bilibili`**（终端扫码自动获取并保存 SESSDATA），或手动 `set_downloader_cookie(platform="bilibili", cookie="SESSDATA=...")`。AI 字幕需登录态；`raw_info.subtitles={}` 只反映手动 CC，AI 字幕在 automatic_captions，关键是 cookie |
| 链接不支持 | 只支持 bilibili / youtube / douyin / tiktok / kuaishou / 本地文件路径 |
| 视频下载 403 / 需会员 | `set_downloader_cookie` 配置平台 Cookie |
