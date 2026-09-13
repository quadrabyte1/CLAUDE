# Sprite v0.4 — Voice Memo Mac Pipeline

Sprite watches the iCloud Voice Memos sync folder on your Mac, transcribes
each new `.m4a` with whisper-cli, parses intent with Ollama, and POSTs the
structured record to Herman's `/capture/parsed` endpoint.

```
iCloud Voice Memos → watchdog → ffmpeg (M4A→WAV) → whisper-cli small.en → Ollama qwen2.5:7b → Herman /capture/parsed
```

## Architecture

| Module | Responsibility |
|---|---|
| `watcher.py` | Cold-boot sweep + watchdog event loop + pipeline orchestration |
| `icloud.py` | Placeholder detection, mtime-stable check, audio archive |
| `transcribe.py` | whisper.cpp subprocess wrapper, confidence from token `p` values (--output-json-full) |
| `parse.py` | Preprocessor (regex criticality + verb hints) + Ollama JSON-constrained call |
| `herman.py` | httpx POST /capture/parsed with retry-with-backoff |
| `state.py` | `processed.jsonl` idempotency (no SQLite) |
| `inbox.py` | Atomic-append ambiguous-capture inbox (confidence < 0.6) |
| `config.py` | All paths and settings via env vars — no Mac-only names |

## Install

```bash
# 1. Install Sprite
bash deploy/install.sh

# 2. Install whisper-cli (Homebrew formula is still called whisper-cpp;
#    it installs the binary as whisper-cli since the upstream rename)
brew install whisper-cpp
mkdir -p ~/sprite/models
# Download model:
whisper-cpp-download-ggml-model small.en
mv ~/Library/Caches/whisper/ggml-small.en.bin ~/sprite/models/

# 3. Install ffmpeg (required to decode Voice Memos .m4a files)
brew install ffmpeg

# 4. Grant Full Disk Access (REQUIRED — see docs/FDA_SETUP.md)
# System Settings → Privacy & Security → Full Disk Access
# Add: ~/.local/lib/sprite/venv/bin/python

# 5. Load the launchd agent (AFTER granting FDA)
launchctl load ~/Library/LaunchAgents/com.sprite.watcher.plist
```

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `SPRITE_HERMAN_URL` | `http://localhost:8765` | Herman brain URL |
| `SPRITE_OLLAMA_MODEL` | `qwen2.5:7b` | Ollama model (shared with Herman) |
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
