---
name: bilinote
description: 用 BiliNote-Mcp 的 MCP 工具把视频链接/本地视频（B站/YouTube/抖音/快手）生成 AI Markdown 笔记。触发词：「生成视频笔记」「视频 → 笔记」「帮我给这个视频做笔记」「从 XX 链接做笔记」。⚠️ 必须先确认参数（LLM 模型/风格/视频理解/弹幕评论/截图）再调用 generate_note。
---

# BiliNote-Mcp —— 视频 → AI 笔记

## ⚡ 强制规则（违反 = 任务失败，不可跳过）

1. **必须用 MCP 工具**（`generate_note` / `get_task_status` / `list_providers` / `cancel_note` 等），**不要用 Bash/curl 手工调后端**。唯一例外：让用户在独立终端跑 `bilinote-mcp providers set`（填 key）、`bilinote-mcp login bilibili`（B站扫码）—— 这些本就该在终端做。
2. **必须先确认参数；用户明确指定（或说「你定」）之前，禁止调用 `generate_note`**。必须问：
   - **LLM 模型**：`list_models(provider_id)` 拿到列表 → 呈现给用户选一个；
   - **笔记风格**：列出真实 9 种让用户选 —— `minimal` 精简 / `detailed` 详细 / `academic` 学术 / `tutorial` 教程 / `xiaohongshu` 小红书 / `life_journal` 生活向 / `task_oriented` 任务导向 / `business` 商业风格 / `meeting_minutes` 会议纪要，或自定义（描述经 `extras` 传入）；
   - **是否视频理解** + 帧间隔秒数（默认 6，需多模态模型）；
   - **是否整合弹幕+评论区观点** + 评论条数（默认 20，需 B 站 SESSDATA，没配引导用户 `bilinote-mcp login bilibili`）；
   - **是否插图片** + 笔记保存位置（`notes_dir`）。
   - 即使用户在 setup 配了默认，本次也要先问；用户说「你定/用默认」才用默认值。
3. **单视频一回合一个；多视频用 subagent 并行**：
   - 单视频：一次 `generate_note` → 轮询完成 → 呈现。
   - **多视频（>1 个）：主 agent 对每个视频起一个 subagent**，每个 subagent 独立负责「`generate_note` → `get_task_status` 轮询到 SUCCESS → 汇报」；主 agent 汇总呈现。**主 agent 自己绝不在同一回合连续调用多个 `generate_note`**。
   - 并发上限：最多 `BILINOTE_MAX_WORKERS`（默认 3）个进行中任务，超出 server 会拒绝。
4. **生成后必须问是否后续优化**：基于笔记 + 完整字幕精修（从字幕挖更多细节、展开讲透；补齐遗漏、修正不一致、增强结构）。

## 工作流

1. **`health_check`** —— ffmpeg/db 就绪；缺失先让用户装 FFmpeg。
2. **`validate_url(url)`** —— 平台识别；B 站优先用平台字幕（AI 字幕需 SESSDATA）。
3. **`list_providers`** —— 有 key=已填的供应商；没有则让用户在终端配。
4. **确认参数**（见「强制规则 2」，问完再继续）。
5. **`generate_note(video_url, provider_id, model_name=<用户选>, style=<用户选>, ...)`** → `task_id`。
   - 视频理解：`video_understanding=True, video_interval=<秒>`（需多模态模型）；
   - 弹幕评论：`include_comments=True, comments_limit=<条>`；
   - 插图片：`screenshot=True, format=["screenshot"]` + `notes_dir="/用户/给的/路径"`。
6. **轮询**：`get_task_status(task_id)` 轻量快照，直到 `SUCCESS`（长视频可能几分钟；**不要**用阻塞的 `wait_for_note`）。
7. **拿到 `result.markdown`** → 直接阅读，用它回答用户的所有问题（无 RAG）；`result.note_dir` 指向笔记文件（读图以它为基准）；追问细节可读 `result.transcript`。
8. **呈现笔记**（要点 + 关键章节 + 原文链接）→ **问是否后续优化**（见强制规则 4，要则读 markdown+transcript 精修，原笔记保留对比）→ 若有多个视频，其余由 subagent 各自处理（见强制规则 3），主 agent 收集结果统一呈现。

## 参考

需要工具参数/配置/故障排查时，用 **Read** 读取同目录 reference/ 下的文件：
- [`reference/tools.md`](reference/tools.md) —— 工具接口速查 + 配置要点
- [`reference/troubleshooting.md`](reference/troubleshooting.md) —— 故障排查 + 并发/多会话 + B 站细节
