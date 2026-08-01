# BiliNote-MCP

**English** · [中文](README.md)

> Video link → AI Markdown notes. A **MCP Server (Model Context Protocol) + Claude Code Skill** built on [BiliNote](https://github.com/JefferyHcool/BiliNote)'s core pipeline: hand an agent a link, it downloads, transcribes, and summarizes the video into structured Markdown notes — no backend required.

<div align="center">

[![GitHub stars](https://img.shields.io/github/stars/HuangYincan/BiliNote-MCP?logo=github)](https://github.com/HuangYincan/BiliNote-MCP)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)]()
[![MCP](https://img.shields.io/badge/MCP-Server-6C5CE7)]()
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-D97757)]()
[![BiliNote-MCP MCP server](https://glama.ai/mcp/servers/HuangYincan/BiliNote-MCP/badges/score.svg)](https://glama.ai/mcp/servers/HuangYincan/BiliNote-MCP)

</div>

<p align="center"><a href="https://glama.ai/mcp/servers/HuangYincan/BiliNote-MCP"><img src="https://glama.ai/mcp/servers/HuangYincan/BiliNote-MCP/badges/card.svg" alt="BiliNote-MCP MCP server" width="600"></a></p>

📦 Repository: [HuangYincan/BiliNote-MCP](https://github.com/HuangYincan/BiliNote-MCP)

## ✨ Features

- **🗜️ Self-contained pipeline** — download (yt-dlp) → subtitles/transcription (local faster-whisper or cloud groq/bcut) → **video understanding (frame sampling at intervals, multimodal LLM "sees" the video)** → LLM summary → Markdown notes. All logic lives in this repo — **no BiliNote FastAPI backend or Web UI needed**.
- **🧠 No RAG** — the agent reads the returned Markdown itself and answers your questions; no ChromaDB / embedding, lightweight.
- **📦 Self-contained** — `app/` is vendored from upstream (see [VENDOR.md](VENDOR.md)); install in one command via pip/uv.

## Quick Start (TL;DR)

```bash
# Install: one command sets up both Skill + MCP
claude plugin marketplace add HuangYincan/BiliNote-MCP
claude plugin install bilinote@bilinote

# Configure: LLM key + transcription engine (hidden key input)
bilinote-mcp setup

# Use: restart your session, tell the agent "make notes for this video" + link
```

> `bilinote-mcp` is a CLI shorthand. If it's not on your PATH, use `uvx --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp ...` (see [Prerequisites](#prerequisites)).

| Install method | What you get | Best for |
|----------|------|------|
| **1 · Plugin marketplace** (recommended) | Skill + MCP (uvx auto-updates) | Most users |
| 2 · MCP only (uvx) | MCP only | Don't want the Skill |
| 3 · uv tool install | MCP only (pinned version, ~1s startup) | Want a stable version |
| 4 · Clone + install.sh | MCP + Skill + auto setup, pip fallback (no uv) | No uv / want to run from source |

## Installation

### Prerequisites

- **uv** (Python package manager, required — used by uvx / uv tool to install the MCP and CLI):
  `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`
  > No uv? Use "[Method 4](#method-4-clone--installsh)", which has a built-in pip fallback.
- **Python ≥ 3.11, <3.14** (3.12 recommended, locked in `.python-version`)
- **FFmpeg** (required for audio/video processing): `brew install ffmpeg` (Linux: `apt install ffmpeg`)
- **LLM provider API key** (see [Configuration](#configuration-required-after-install))
- **Local transcription**: download a local whisper model first with `bilinote-mcp transcriber download <size>` (tiny/base/small/medium/large-v3/large-v3-turbo), or use cloud `groq` / `bcut` (no download)
- **GPU acceleration (optional)**:
  - **NVIDIA / Linux**: whisper uses CPU by default; for CUDA, install the tool with `--with torch` (CUDA build) — it auto-detects GPU at inference time, otherwise falls back to CPU
  - **macOS Apple Silicon**: use `mlx-whisper` on GPU — install with `--with mlx-whisper`, switch engine via `bilinote-mcp transcriber set mlx-whisper --size small`
- **CLI command forms**: `bilinote-mcp ...` in this doc is shorthand for:
  - With uv: `uvx --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp ...` (`--from` must include the `git+` prefix)
  - Method 4 (pip-installed venv): `<repo>/.venv/bin/bilinote-mcp ...`
  - To make `bilinote-mcp` directly available: `uv tool install --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp` + `uv tool update-shell` to add to PATH

### Method 1: Plugin marketplace — Skill + MCP (recommended)

```bash
claude plugin marketplace add HuangYincan/BiliNote-MCP
claude plugin install bilinote@bilinote
```

Both commands install **Skill + MCP server** (MCP runs via `uvx`, pulling the latest commit each session). Restart the session (or `/reload-plugins`) after installing. Runtime data lives in `~/.local/share/bilinote-mcp/`.

> **The plugin's default MCP does NOT include `mlx-whisper`** (optional dependency, macOS-only; including it by default would break Linux/Windows installs). To use mlx-whisper inside the MCP, override the MCP command manually:
>
> ```bash
> claude mcp add bilinote -- uvx --from git+https://github.com/HuangYincan/BiliNote-MCP --with mlx-whisper bilinote-mcp
> ```
>
> After manual registration the session uses this one (visible via `claude mcp list`). If it conflicts / doesn't take effect with the plugin's `bilinote` name, run `claude mcp remove bilinote` and re-add, or use `~/.local/bin/bilinote-mcp` (the `uv tool install --with mlx-whisper` one) as the MCP command.

### Method 2: MCP only (no Skill)

```bash
claude mcp add --scope user bilinote -- uvx --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp
```

Same MCP part as Method 1. The MCP server is a **session-level persistent process** (started once when the session begins; tool calls don't relaunch it).

### Method 3: uv tool install — pinned version, fastest startup

```bash
uv tool install --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp
claude mcp add bilinote -- "$HOME/.local/bin/bilinote-mcp"
```

Starts the process directly (~1s) each session, no repo access; version is pinned — update by re-running `uv tool install --force` above.

> Want **MLX Whisper** on macOS Apple Silicon (faster local transcription, optional dep)? Install with
> `uv tool install --force --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp --with mlx-whisper`

### Method 4: Clone + install.sh

```bash
git clone https://github.com/HuangYincan/BiliNote-MCP.git
cd BiliNote-MCP && ./install.sh
```

Works without uv (the script builds a `.venv` with pip). install.sh: create venv → register MCP → install Skill → **auto-open the `bilinote-mcp setup` wizard**. Non-interactive terminals skip it; run it manually later.

## Configuration (required after install)

> Installing only gets MCP/Skill running; **the LLM API key and transcription engine must be configured separately** (the key is yours, the model needs choosing). All methods share one data directory (`~/.local/share/bilinote-mcp/`); config takes effect in-session.

### Interactive wizard `setup` (recommended, re-runnable anytime)

```bash
bilinote-mcp setup        # not on PATH: uvx --from git+https://github.com/HuangYincan/BiliNote-MCP bilinote-mcp setup
```

**Arrow-key selection + highlighting**, **left-arrow to go back one level**, auto-clear between steps; **not a one-shot program** — re-run anytime:

- **① LLM providers**: fill/change a key, change base_url, add a relay/gateway; **per-provider connectivity test (verifies key/base_url), list models, and set a default model** (persisted; used automatically when a note is generated without specifying a model);
- **② Transcription engine**: pick engine + model size, prompts to download if the local model isn't ready;
- **③ Other**: platform cookies (dropdown), default notes location (**persisted**), **video understanding defaults** (on/off + frame interval seconds, **persisted**), **comments/danmaku integration defaults** (on/off + comment count, **persisted**; needs a Bilibili SESSDATA), **note defaults** (`default_style` detailed / `default_screenshot` off / `agent_direct` off, **persisted**) — full-auto mode applies these (it first lists the full parameter set for your confirmation).

### Manual CLI (keys never enter the conversation)

```bash
# LLM providers
bilinote-mcp providers list                                    # view (keys masked)
bilinote-mcp providers set deepseek --api-key 'sk-YourKey'      # fill a key for a built-in provider
bilinote-mcp providers add --name relay --api-key 'sk-...' --base-url 'https://relay...'   # add a relay
bilinote-mcp providers test deepseek                            # connectivity test + list models
bilinote-mcp providers test deepseek --default deepseek-chat    # test and set as default model

# Transcription engine
bilinote-mcp transcriber list                                  # current engine + readiness
bilinote-mcp transcriber set fast-whisper --size small          # switch to local whisper
bilinote-mcp transcriber set groq                               # switch to cloud
bilinote-mcp transcriber download small                          # download fast-whisper model
bilinote-mcp transcriber download small --engine mlx-whisper     # download mlx-whisper (macOS)

# Bilibili (use AI subtitles to skip speech-to-text)
bilinote-mcp login bilibili     # QR login, auto-fetch & save SESSDATA (AI subtitles need login)
```

**Transcription engines**: `fast-whisper` (local) / `groq` / `bcut` / `kuaishou` (cloud) / `mlx-whisper` (**macOS Apple Silicon only**, GPU).

**Local whisper sizes**: `tiny` / `base` / `small` / `medium` / `large-v3` / **`large-v3-turbo`** (turbo is faster, slightly less accurate).

**Devices**: whisper auto-detects CUDA (uses GPU if torch+CUDA is installed, otherwise CPU); macOS uses `mlx-whisper` for GPU. CLI `transcriber download` uses CPU only because it **downloads weights, no inference** (the device param doesn't affect the download).

### No LLM API key?

- **Local & free**: install [Ollama](https://ollama.com) and `ollama pull llama3`. The built-in `ollama` provider is pre-seeded (`http://127.0.0.1:11434/v1`, **no key needed**); usable once `list_models("ollama")` returns models.
- **Free tiers**: Groq / DeepSeek etc. offer free tiers; register and fill the key with `providers set`.
- Tell the agent "I have no LLM key" — it checks Ollama first, then guides you to register.

## Usage

### With an agent (Claude Code, etc.)

Tell the agent "**make notes for this video**" + a link. Standard flow:

1. `health_check` — confirms FFmpeg / DB are ready;
2. `list_providers` — confirms a provider with key=set (masked); if none, configure via CLI first;
3. `generate_note(video_url=..., provider_id=..., model_name=...)` — get `task_id`;
4. `get_task_status(task_id)` **lightweight snapshot polling** until `SUCCESS`/`FAILED`/`CANCELLED` (**submit one task at a time** — the server rejects new submissions while a task is running; don't batch multiple `generate_note` calls);
5. Once you have `result.markdown`, **the agent reads the Markdown itself and answers your questions** — no extra RAG needed;
6. **Ask whether to do a follow-up optimization** based on the note + extracted subtitles (`result.transcript`) — agent-side refinement, no new tool.

### Full-auto / Manual mode + AGENT direct generation

At the start of a task the agent **asks "Full-auto" or "Manual"**:

- **Full-auto**: resolves the **full parameter set** from the setup ③ defaults (generation method / LLM model (or choose AGENT direct generation) / `default_style` (detailed) / video-understanding default / comments default / screenshot default / **whether to do post-generation optimization**) and **lists it once for your confirmation** instead of asking one by one; if you want to change anything it re-asks that item as a question. Once confirmed, not passing style / screenshot / video_understanding / include_comments / agent_direct to `generate_note` applies those defaults. AGENT direct generation is offered at the LLM-model selection step (defaults to the configured LLM).
- **Manual**: confirms each parameter (LLM model, note style, video understanding, comments/danmaku, screenshots, whether to use AGENT direct generation), then generates.

**AGENT direct generation (`agent_direct`)**: offered at the **LLM-model selection step** — manual mode asks "which model, or AGENT direct generation?"; full-auto mode defaults to the configured LLM and you can switch it in the parameter list. When enabled, the note is **written by the agent itself, not by the configured LLM**:

1. `prepare_note_material(video_url, video_understanding?, video_interval?, include_comments?, comments_limit?)` → `task_id`;
2. Poll `get_task_status(task_id)` to `SUCCESS` → get the material package (`result.transcript.full_text` full transcript, `result.frames` sampled frames, `result.comments_danmaku` comments/danmaku);
3. The agent reads the transcript / uses Read to look at the frames → **writes the Markdown itself** (asks for style, defaults to detailed; adds an "观众观点" (Audience viewpoints) section when comments/danmaku are present) → presents.

If the transcript is very long (e.g. a 2h video), refine section by section or let the user pick a focus. The rest (health_check / validate_url / polling / follow-up optimization) stays the same.

### Real end-to-end usage example

From just "3 Bilibili links + an output directory", a full run auto-generated three refined notes (parameter confirmation → parallel multi-video → video-understanding screenshots → danmaku/comments integration → transcript-based refinement):
see [`examples/note-generation-example/`](examples/note-generation-example/README.md) (includes the three finished notes and a transcript of the run).

### Manual tool quick reference (non-sensitive config)

| What you want | Which tool |
|----------|-----------|
| View providers / fill a key | `list_providers` (masked) / **CLI** `providers set` |
| View / add models | `list_models(provider_id)` / `add_model(provider_id, "deepseek-chat")` |
| Connectivity test / set default model | `bilinote-mcp providers test <id> [--default MODEL]` (non-interactive; in the wizard: "Manage → Test") |
| Local transcription | `set_transcriber("fast-whisper", "small")` + `download_transcriber_model("small")` |
| Cloud transcription | `set_transcriber("groq")` (fill groq key via CLI) |
| Login-gated Bilibili content | `set_downloader_cookie(platform="bilibili", cookie="SESSDATA=...")` |
| Local files | `generate_note(video_url="/abs/path/a.mp4", platform="local", ...)` |

> Anything involving a **key goes through the CLI (outside the conversation)**; tools only do non-sensitive config — see [Security](#security-api-keys).

### Advanced: video understanding (frame sampling)

Have the agent sample **video frames** at an interval and send them to a multimodal LLM (e.g. qwen-vl / gpt-4o) to "see" the visuals. `generate_note` supports it directly:

```text
generate_note(video_url=..., provider_id="qwen", model_name="qwen-vl-plus",
              video_understanding=True, video_interval=6, grid_size=[3, 3])
```

- Samples one frame every `video_interval` seconds, stitches them into a grid, and sends it to the LLM as an inline base64 image;
- **Requires a multimodal (vision) model**; text-only models like deepseek-chat aren't supported;
- `grid_size` defaults to `[3, 3]` (`[2, 2]` for `format=["screenshot"]` mode);
- **Defaults are configurable in setup ③** (default off / 6s): applied automatically when the agent doesn't pass `video_understanding` / `video_interval` (in **manual mode** the Skill still asks you first; defaults only apply on "your call"; in **full-auto mode** it applies defaults (listing the resolved parameter set for confirmation first));
- To insert **single screenshots** at `*Screenshot-mm:ss` markers, use `format=["screenshot"]` (distinct from the full-frame grid).

### Advanced: comments & danmaku integration

Want the note to also fold in high-frequency **danmaku** and **comment-section** viewpoints from Bilibili (what's trending in the barrage, what the comments are discussing)? Add to `generate_note`:

```text
generate_note(video_url=..., ..., include_comments=True, comments_limit=20)
```

- Folds danmaku + comment-section viewpoints into the note, so it reflects viewer discussion, not just the audio track;
- **The note gains an "Audience viewpoints" (观众观点) section** summarizing recurring comment/danmaku opinions, additions and corrections (quoting actual content, no fabrication); writes "（无）" when there's nothing to summarize;
- `comments_limit` controls how many comments to fetch (default 20);
- **Needs a Bilibili SESSDATA** (logged-in state): without it the comments won't be available — run `bilinote-mcp login bilibili` to scan a QR code (or `set_downloader_cookie(platform="bilibili", cookie="SESSDATA=...")`);
- **A fetch failure does not block the task**: if comments/danmaku can't be retrieved, the note is still generated normally and simply skips that part;
- To just pull the raw data, use the `fetch_comments(video_url, limit=20)` / `fetch_danmaku(video_url)` tools;
- **Defaults are configurable in setup ③** (default off / 20 comments): applied automatically when the agent doesn't pass `include_comments` / `comments_limit` (in **manual mode** the Skill still asks you first; defaults only apply on "your call"; in **full-auto mode** it applies defaults (listing the resolved parameter set for confirmation first)).

### Advanced: screenshots (portable notes)

To include screenshots and keep the note portable, add:

```text
generate_note(video_url=..., provider_id=..., model_name=..., screenshot=True, format=["screenshot"])
```

- Produces a **portable note**: `note_dir/note.md` + `note_dir/Assets/*.jpg`, with **relative references** `![...](Assets/xxx.jpg)` in the Markdown;
- `result.note_dir` in the task result points to that directory (the agent tells you where the note and images are);
- **Save location priority**: `generate_note(..., notes_dir="/your/dir")` → `BILINOTE_NOTES_DIR` env var → default `note_results/{task_id}/`;
- **When `notes_dir` is set, each note gets its own folder**: `<notes_dir>/<note-title>/note.md` (title taken from the LLM-generated note's H1, falling back to the video title; conflicts get a short task-id suffix) — written even without screenshots, so multiple notes never overwrite each other;
- How it works: `screenshot=True` makes the LLM emit `*Screenshot-[mm:ss]` markers, and `format=["screenshot"]` replaces them with images; pairing with video understanding (`video_understanding=True`) gives more natural results.

### Advanced: cleanup & storage

Task artifacts (downloaded video/audio, transcripts, screenshots, temp files) pile up and eat disk. Agents can clean them up self-service:

- **Inspect first**: `get_task_files(task_id)` — lists the files/dirs a task created on disk (manifest records + `{task_id}*` prefix scan); returns `{task_id, manifest_paths, existing}`.
- **Per-task cleanup**: `cleanup_note(task_id, include_note=False)` — deletes that task's intermediates (video/audio/transcript/screenshots/`dl_{task_id}/`), **keeping the final note** `note.md` by default; `include_note=True` also deletes the note.
- **Global cleanup (factory reset)**: `cleanup_all(include_config=False, include_models=False)` — empties `note_results/*`, `static/screenshots/*`, `logs/*`; **keeps** `config/` (LLM keys / cookies / transcriber settings) and `models/` (models are reusable, re-downloading is expensive) by default, and only clears them with `include_config=True` / `include_models=True`. The database (`bili_note.db`) is untouched.

Safety: only manifest-recorded / explicit-prefix paths are deleted, `resolve()`-validated to stay inside the data directory (path-traversal safe); failures are skipped one-by-one and reported.

## Tool reference

| Tool | Description |
|------|------|
| `generate_note` | Submit a video URL, async note generation, returns task_id (supports video understanding + screenshot portable notes + `extras` custom style) |
| `prepare_note_material` | Download/transcribe/frame-sample/comments only, **does NOT call the configured LLM**; returns a material package (`transcript.full_text` / `frames` / `comments_danmaku`) for AGENT direct generation (see [Full-auto / Manual mode + AGENT direct generation](#full-auto--manual-mode--agent-direct-generation)) |
| `get_task_status` / `wait_for_note` | Poll task progress / blocking wait for the final Markdown |
| `cancel_note` | Cancel a running/queued task (cooperative; takes effect at the next phase boundary) |
| `list_providers` / `add_provider` / `update_provider` | View (masked) / add / update providers (fill keys via CLI) |
| `list_models` / `add_model` | View (live/DB fallback) / manually add models |
| `get_transcriber_config` / `set_transcriber` | View / switch transcription engine (local whisper ↔ cloud groq) |
| `list_transcriber_models` / `download_transcriber_model` | Whisper model management |
| `health_check` | FFmpeg / DB / whisper readiness |
| `validate_url` | Detect which platform a video link belongs to |
| `set_downloader_cookie` | Set a platform cookie (e.g. Bilibili) |
| `fetch_comments` / `fetch_danmaku` | Fetch Bilibili video comments / danmaku (`fetch_comments(video_url, limit=20)` / `fetch_danmaku(video_url)`; needs SESSDATA) |
| `get_task_files` / `cleanup_note` / `cleanup_all` | Inspect a task's files / clean one task (keeps the final note by default) / global cleanup (factory reset; keeps config & models by default), see [cleanup & storage](#advanced-cleanup--storage) |

## Environment variables (optional)

| Variable | Effect | Default |
|------|------|------|
| `BILINOTE_DATA_DIR` | Data root (SQLite / notes / screenshots / config) | Installed: `~/.local/share/bilinote-mcp`; source: `<repo>/data` |
| `BILINOTE_NOTES_DIR` | Default notes output dir (fallback when `notes_dir` not given) | `note_results/{task_id}/` |
| `BILINOTE_CONFIG_DIR` | Config file dir (transcriber/cookie/app config) | `<data>/config` |
| `BILINOTE_MODEL_DIR` | whisper / mlx model dir | `<data>/models` (source: `<repo>/models`) |
| `BILINOTE_MAX_WORKERS` | **Concurrent note tasks** per MCP session | 3 |
| `HF_ENDPOINT` | HuggingFace mirror (for slow downloads in China) | Official `https://huggingface.co`; use `https://hf-mirror.com` in China |

**Serialized per session + parallel across sessions**: each Claude Code session runs its own MCP server process. **Within a session, note tasks are force-serialized** — `generate_note` **rejects** new submissions while a task is running (submit one → poll `get_task_status`/`wait_for_note` to `SUCCESS`/`FAILED`/`CANCELLED` → submit the next); **multiple sessions** can each generate notes for different videos in parallel. **Note**: the Claude Code client handles "multiple parallel MCP tool calls in one message" unreliably (the last response can hang) — so don't batch multiple `generate_note` calls in one message even across tasks. **Poll with lightweight `get_task_status(task_id)` snapshot polling**; `wait_for_note` is blocking and can make the conversation look stuck. Cancel a running task with `cancel_note(task_id)`. Also: whisper/MLX transcription is CPU/memory heavy; too many parallel sessions can saturate the machine; all sessions share one SQLite DB, so extreme concurrency can occasionally cause write conflicts.

## Updating

Update commands per install method:

| What was installed | Update command |
|----------|----------|
| **MCP server** (uvx / plugin) | ✅ Auto-updates (checks the latest commit each session) |
| **Skill / plugin** | `claude plugin marketplace update bilinote` + `claude plugin disable bilinote@bilinote` + `claude plugin install bilinote@bilinote` |
| **CLI installed via `uv tool install`** | `uv tool upgrade bilinote-mcp` (keeps `--with mlx-whisper` etc.) |
| **Source / `install.sh`** | `git pull && ./install.sh` |

> **The Skill/plugin three steps each matter**: ① `marketplace update` pulls the latest commit; ② `disable` lets `install` not skip; ③ `install` reinstalls to the latest. Skipping any can leave you on an old version (`install` alone is skipped as "already installed").

## Security (API keys)

**Hard rule: never send your key to the agent in the conversation.** Agent conversation content goes to its LLM upstream — a key in the conversation is effectively handed to the upstream. **Keys go through the CLI in a separate terminal only** (text typed after a `!` prefix is also part of the conversation, so that's off-limits too):

```bash
bilinote-mcp providers set deepseek --api-key 'sk-YourKey'      # run in a separate terminal
bilinote-mcp providers list                                     # view (keys masked)
```

- **The agent only needs to know whether a key is set**: `list_providers` returns a mask (`sk-S***cdef`); add/update tools don't echo keys; related logs are redacted.
- **Storage**: keys live only in the local SQLite (`~/.local/share/bilinote-mcp/bili_note.db` or source `data/`), gitignored, **never on GitHub**.
- **Note**: keys are stored in plaintext in the local DB (same as upstream BiliNote). If the machine may be shared, consider encrypting via the system keychain later.

## Skill

The repo ships a Claude Code Skill — `skills/bilinote/SKILL.md` — teaching the agent to go "video → notes" in one sentence. The core Skill is kept lean (mandatory rules + workflow); tool interfaces / config / troubleshooting live in `skills/bilinote/reference/` (read on demand).

Install via the plugin marketplace (installs both the Skill and the MCP server):

```bash
claude plugin marketplace add HuangYincan/BiliNote-MCP
claude plugin install bilinote@bilinote
```

After installing, restart the session (or `/reload-plugins`) and tell Claude "**make notes for this video**" + a link — the Skill auto-triggers and drives the MCP tools.

## Docs

Detailed documentation (Chinese) in [docs/](docs/):

- [Purpose & Background](docs/01-目的与背景.md)
- [Architecture](docs/02-架构设计.md)
- [Expected Results](docs/03-预期效果.md)
- [User Manual](docs/04-使用手册.md)
- [Changelog](docs/CHANGELOG.md)

## Development build (dev branch)

The `dev` branch has unreleased features (for early access / testing). To use dev early:

**Point the MCP tools at dev** (overrides the plugin's main MCP):

```bash
claude mcp remove bilinote                                 # if previously on main: remove the plugin's default main MCP first, so the same-named add below takes effect
claude mcp add --scope user bilinote -- uvx --from git+https://github.com/HuangYincan/BiliNote-MCP@dev bilinote-mcp
```

**Point the Skill at dev too** (pin the marketplace to the dev branch):

```bash
claude plugin marketplace add HuangYincan/BiliNote-MCP@dev
claude plugin disable bilinote@bilinote
claude plugin install bilinote@bilinote
```

Restart the session (or `/reload-plugins`) for it to take effect.

> **Already pinned to dev and the code changed?** Just run `claude plugin marketplace update bilinote` (pulls the latest dev commit; the `ref: dev` is preserved), then `disable` + `install` — no need to re-run `add @dev`. Only re-run `add ...@dev` if the marketplace was switched back to main.

**Switch back to main (stable)**:

```bash
claude mcp remove bilinote                                   # MCP reverts to the plugin default (main)
claude plugin marketplace add HuangYincan/BiliNote-MCP       # marketplace back to main
claude plugin disable bilinote@bilinote
claude plugin install bilinote@bilinote
# /reload-plugins
```

**CLI on dev** (if the `bilinote-mcp` on PATH is the pinned main build): `uvx --from git+https://github.com/HuangYincan/BiliNote-MCP@dev bilinote-mcp setup`

> **Note**:
> - dev and main **share the same data directory** `~/.local/share/bilinote-mcp/`: your LLM keys / SESSDATA / transcriber config carry over automatically — **no need to reconfigure**; but they share the same SQLite, so don't run tasks from both at once.
> - Pointing the marketplace at dev **replaces** your production marketplace (not coexisting) — remember to switch back to main after testing.
> - `git+...@dev` is the uv/uvx branch-ref syntax; the default install (no ref) pulls **main** (stable).
> - A dev-pinned marketplace only changes the **Skill**; the MCP tools need the manual `@dev` override (the marketplace.json `uvx` URL has no ref and still pulls main).
> - dev-branch features are unreleased — for early access / testing only.

## Related

- Upstream: https://github.com/JefferyHcool/BiliNote
