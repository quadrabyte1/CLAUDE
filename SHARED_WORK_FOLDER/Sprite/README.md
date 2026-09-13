# Sprite v0.2 — Voice Memo Mac Pipeline

Sprite watches the iCloud Voice Memos sync folder on your Mac, transcribes
each new `.m4a` with whisper.cpp, parses intent with Ollama, and POSTs the
structured record to Herman's `/capture/parsed` endpoint.

```
iCloud Voice Memos → watchdog → whisper.cpp small.en → Ollama qwen2.5:7b-instruct → Herman /capture/parsed
```

## Architecture

| Module | Responsibility |
|---|---|
| `watcher.py` | Cold-boot sweep + watchdog event loop + pipeline orchestration |
| `icloud.py` | Placeholder detection, mtime-stable check, audio archive |
| `transcribe.py` | whisper.cpp subprocess wrapper, confidence from avg_logprob |
| `parse.py` | Preprocessor (regex criticality + verb hints) + Ollama JSON-constrained call |
| `herman.py` | httpx POST /capture/parsed with retry-with-backoff |
| `state.py` | `processed.jsonl` idempotency (no SQLite) |
| `inbox.py` | Atomic-append ambiguous-capture inbox (confidence < 0.6) |
| `config.py` | All paths and settings via env vars — no Mac-only names |

## Install

```bash
# 1. Install Sprite
bash deploy/install.sh

# 2. Install whisper-cpp
brew install whisper-cpp
mkdir -p ~/sprite/models
# Download model (choose one):
whisper-cpp-download-ggml-model small.en
mv ~/Library/Caches/whisper/ggml-small.en.bin ~/sprite/models/

# 3. Grant Full Disk Access (REQUIRED — see docs/FDA_SETUP.md)
# System Settings → Privacy & Security → Full Disk Access
# Add: ~/.local/lib/sprite/venv/bin/python

# 4. Load the launchd agent (AFTER granting FDA)
launchctl load ~/Library/LaunchAgents/com.sprite.watcher.plist
```

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `SPRITE_HERMAN_URL` | `http://localhost:8765` | Herman brain URL |
| `SPRITE_OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Ollama model (shared with Herman) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `SPRITE_RECORDINGS_DIR` | `~/Library/Group Containers/.../Recordings` | Voice Memos folder |
| `SPRITE_MODELS_DIR` | `~/sprite/models` | whisper.cpp model files |
| `SPRITE_MIN_CONFIDENCE` | `0.6` | Confidence floor; below → inbox |
| `SPRITE_DEBOUNCE_SECONDS` | `3.0` | mtime-stable window |
| `SPRITE_MIN_FILE_BYTES` | `10240` | Minimum file size to process |
| `SPRITE_LOG_LEVEL` | `INFO` | Logging level |

## Run tests

```bash
cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Sprite
pip install -e ".[dev]"
pytest -v
```

## Full Disk Access

The Voice Memos group container requires FDA. See `docs/FDA_SETUP.md`.

## First live run

See `docs/FIRST_RUN.md` for the smoke-test procedure after FDA is granted.
