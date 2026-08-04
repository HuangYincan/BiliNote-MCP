# VENDOR.md — 上游代码来源与移植说明

本仓库的 `app/` 目录是从上游 BiliNote 仓库**复制**而来（而非 pip 依赖），目的是让 MCP 完全自包含、可独立安装运行，不依赖 FastAPI 后端。

## 上游来源

- 上游仓库：https://github.com/JefferyHcool/BiliNote
- 移植来源 commit：`bebf2e8c6142e195a2b8a01525c4c7ba3cf993f8`
- 移植日期：2026-07-31
- 来源路径：`BiliNote/backend/app/`

## 复制了哪些模块

| 子包 | 内容 |
|------|------|
| `app/downloaders/` | base, common, bilibili_downloader, bilibili_dm_patch, bilibili_subtitle, youtube_downloader, youtube_subtitle, douyin_downloader, kuaishou_downloader, local_downloader, xiaoyuzhoufm_download |
| `app/transcriber/` | base, transcriber_provider, whisper, groq, bcut, kuaishou, mlx_whisper_transcriber, model_download_state, whisper_models |
| `app/gpt/` | base, gpt_factory, openai_gpt, deepseek_gpt, qwen_gpt, universal_gpt, prompt, prompt_builder, request_chunker, utils, tools（不含 test.py）+ `app/gpt/provider/OpenAI_compatible_provider.py`（gpt_factory 依赖） |
| `app/db/` | engine, init_db, sqlite_client, provider_dao, model_dao, video_task_dao + `app/db/models/`（models, providers, video_tasks） |
| `app/models/` | audio_model, gpt_model, model_config, notes_model, provide_model, transcriber_model, video_record |
| `app/enmus/` | exception, note_enums, task_status_enums |
| `app/exceptions/` | biz_exception, note, provider（**不含** exception_handlers —— 仅 FastAPI 用） |
| `app/decorators/` | timeit |
| `app/validators/` | video_url_validator |
| `app/services/` | note, constant, provider, cookie_manager, task_serial_executor, transcriber_config_manager, proxy_config_manager（**不含** chat_service / chat_tools / vector_store —— 本仓库不做 RAG；**不含** model / model_fallback —— 仅 routers 使用） |
| `app/utils/` | note_helper, video_helper, video_reader, screenshot_marker, status_code, logger, path_helper, url_parser, openai_client, env_checker + **本仓库新增** `model_status.py`（见下）（**不含** response / export / ppt_generator / minio_client） |
| `events/` | signals（blinker `transcription_finished`）、handlers（转写完成后临时文件清理）—— 顶层模块，供各转写器 `from events import transcription_finished` |

## 外科手术改动（相对上游）

为了剥离 FastAPI/Web 层，做了以下最小改动：

1. **`app/__init__.py`** — 删除 `from fastapi import FastAPI` 及 app 实例创建，改为空包标记。
2. **`app/services/provider.py`** — 用标准库 `import uuid` + `created_at.isoformat()` 替换 `from fastapi.encoders import jsonable_encoder` 和 `from kombu import uuid`（去掉了 celery/kombu 依赖）。
3. **`app/services/note.py`** — 删除未使用的 `from fastapi import HTTPException` 导入。
4. **`app/services/transcriber_config_manager.py`** — 把对 `app.routers.config` 的延迟 import 改为 `app.utils.model_status`；新增 **`app/utils/model_status.py`**（从 `routers/config.py` 抽取 `_check_whisper_model_exists` / `_check_mlx_whisper_model_exists` 两个纯函数，并补上「是否下载中」的查询）。
5. **`app/downloaders/local_downloader.py`** — 封面提取改为**非致命**（try/except 跳过）：上游对纯音频文件（mp3/wav）会因无法抽帧直接使任务失败，本仓库允许跳过封面继续生成笔记。
6. **`app/services/cookie_manager.py` / `app/services/transcriber_config_manager.py`** — 配置文件默认路径改为 `VIDEONOTE_CONFIG_DIR`（见 `videonote_mcp/config.py`），避免依赖 CWD。
5. **未移植** 的模块：`routers/`、`main.py`、`utils/response.py`、`utils/export.py`、`utils/ppt_generator.py`、`utils/minio_client.py`、`services/chat_*`、`services/vector_store.py`、`services/model.py`、`services/model_fallback.py`、`exceptions/exception_handlers.py` —— 均确认仅 Web 层（routers/main）使用，核心流水线不依赖。

## 如何同步上游更新

```bash
# 1. 记下当前 vendored 版本
git -C /path/to/BiliNote rev-parse HEAD

# 2. 用 diff 对比差异
diff -r app /path/to/BiliNote/backend/app --exclude=__pycache__ --exclude=routers --exclude=main.py

# 3. 复制需要更新的文件，重新应用上面的 4 处改动
# 4. 更新本文件的 commit 号与日期
# 5. 在 docs/CHANGELOG.md 记一条「同步上游」
```
