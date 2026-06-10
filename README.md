# 🎬 Video Tool Bot

A **production-ready** Telegram bot that lets users process videos directly from
Telegram through interactive inline buttons and **FFmpeg**. Send a video, pick a
tool, and get the result back with live progress updates.

Built with **Pyrogram + TgCrypto**, a fully asynchronous **FFmpeg** pipeline,
**MongoDB** for persistence, an async **task queue**, rate limiting and a full
**admin panel**. Ships with **Docker** support.

---

## ✨ Features

### Commands
| Command | Description |
|---------|-------------|
| `/start` | Welcome message & registration |
| `/help` | How to use the bot |
| `/about` | Bot/version info |
| `/settings` | Per-user preferences (codec, CRF, preset, format, upload mode) |
| `/ping` | Latency check |
| `/stats` | Usage statistics |

### Video Tool Menu
When you send a video, an inline keyboard appears with:

`Encode` · `Convert` · `Multi-Resolution` · `Video + Video` · `Video + Audio` ·
`Video + Subtitle` · `Video + Audio + Subtitle` · `IntroSub` · `HardSub` ·
`Remove Subs` · `Remove Audio` · `Remove Streams` · `Strip Metadata` ·
`Extract Subs` · `Extract Audio` · `Swap Audio` · `Watermark` · `Cancel`

| Tool | Details |
|------|---------|
| **Encode** | H264 / H265 / AV1 / VP9 with Low / Medium / High / Custom CRF presets |
| **Convert** | MP4 / MKV / AVI / MOV / WEBM |
| **Multi-Resolution** | Generate 240p / 360p / 480p / 720p / 1080p (returns all files) |
| **Video + Video** | Merge two videos into one |
| **Video + Audio** | Add/replace audio track (MP3/AAC/FLAC/M4A), with a language-select step that tags the muxed audio stream |
| **Video + Subtitle** | Soft-mux a subtitle (SRT/ASS/VTT), with a language-select step that tags the muxed subtitle stream |
| **Video + Audio + Subtitle** | Add both an audio and a subtitle track, each with its own language-select step |
| **IntroSub** | Insert an intro subtitle automatically |
| **HardSub** | Burn subtitles permanently (FFmpeg `subtitles` filter) |
| **Remove Subs / Audio** | Strip all subtitle or audio streams |
| **Remove Streams** | Choose which stream types to remove (audio/subtitle/data/attachment) |
| **Strip Metadata** | Remove all metadata (`-map_metadata -1`) |
| **Extract Audio** | MP3 / AAC / FLAC / WAV |
| **Extract Subs** | SRT / ASS / VTT |
| **Swap Audio** | Replace the existing audio track |
| **Watermark** | Image or text, with position (5 anchors) and opacity selection |

### Progress System
A single status message is edited in place showing the current **stage**
(Downloading → Processing → Encoding/Muxing → Uploading → Completed),
**percentage**, **speed** and **ETA**, throttled to avoid Telegram flood limits.

### Queue System
- Fully async global worker pool (`MAX_CONCURRENT_TASKS`)
- Per-user queue limit (`MAX_TASKS_PER_USER`)
- Live queue position, queue status and per-task **cancel** button

### Admin Panel
`/broadcast` (reply to a message) · `/users` · `/stats admin` · `/ban` ·
`/unban` · `/logs` · `/restart`. Admins are configured via `OWNER_ID` /
`ADMIN_IDS`.

### Security
File-size limits, sliding-window rate limiting / flood protection, per-task
FFmpeg timeout, automatic process termination on cancel/timeout, and cleanup of
all temporary files after every task.

---

## 🗂 Project Structure

```
bot/
├── config/        # Environment-based configuration
├── database/      # Async MongoDB layer (users, settings, tasks, stats)
├── ffmpeg/        # Probe, process runner, high-level operations
├── handlers/      # Task orchestration (download → process → upload)
├── helpers/       # Formatting, file management, progress reporting
├── keyboards/     # Inline keyboard factories
├── models/        # Dataclasses mirroring MongoDB documents
├── plugins/       # Pyrogram handlers (commands, admin, video, callbacks)
├── utils/         # Logger, async queue, rate limiter, conversation state
├── bot.py         # Application lifecycle (start/stop)
└── __main__.py    # `python -m bot`
main.py            # Root entry point
requirements.txt
Dockerfile
docker-compose.yml
.env.example
```

---

## 🚀 Getting Started

### Prerequisites
- Python **3.11+**
- **FFmpeg** (and `ffprobe`) available on `PATH`
- A running **MongoDB** instance
- Telegram **API_ID/API_HASH** (from <https://my.telegram.org>) and a
  **BOT_TOKEN** (from [@BotFather](https://t.me/BotFather))

### 1. Clone & configure
```bash
git clone https://github.com/cornsnaker/AD-VIDEO-TOOL-BOT.git
cd AD-VIDEO-TOOL-BOT
cp .env.example .env   # then fill in API_ID, API_HASH, BOT_TOKEN, MONGO_URI, OWNER_ID
```

### 2. Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py          # or: python -m bot
```

### 3. Run with Docker
```bash
# Uses the bundled MongoDB service from docker-compose.yml
cp .env.example .env    # fill in API_ID, API_HASH, BOT_TOKEN, OWNER_ID
docker compose up --build
```
Or build the image standalone (bring your own MongoDB via `MONGO_URI`):
```bash
docker build -t video-tool-bot .
docker run --env-file .env video-tool-bot
```

---

## ⚙️ Configuration

All configuration is read from environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `API_ID`, `API_HASH`, `BOT_TOKEN` | – | **Required** Telegram credentials |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB_NAME` | `video_tool_bot` | Database name |
| `OWNER_ID` | `0` | Owner Telegram user id |
| `ADMIN_IDS` | – | Extra admin ids (comma/space separated) |
| `DOWNLOAD_DIR` | `downloads` | Working directory for media |
| `MAX_FILE_SIZE` | `2147483648` | Max input size in bytes (2 GiB) |
| `TASK_TIMEOUT` | `7200` | Per-job FFmpeg timeout (seconds) |
| `MAX_CONCURRENT_TASKS` | `2` | Global concurrent FFmpeg jobs |
| `MAX_TASKS_PER_USER` | `5` | Per-user queued task limit |
| `RATE_LIMIT_WINDOW` / `RATE_LIMIT_MAX` | `60` / `20` | Flood protection window |
| `PROGRESS_UPDATE_INTERVAL` | `5` | Seconds between progress edits |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## 🧪 Development

```bash
pip install -r requirements-dev.txt
flake8 bot tests main.py     # lint
pytest -q                    # unit tests
```

CI (GitHub Actions) runs flake8 and the test suite on every push and PR.

---

## 📦 Tech Stack
Python 3.11+ · Pyrogram · TgCrypto · FFmpeg · asyncio · MongoDB (Motor) ·
python-dotenv · Docker

## 📝 License
Released under the MIT License.
