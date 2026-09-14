# Sprite — First Live Run (iCloud Voice Memos → Herman)

This doc covers the smoke test to run after granting FDA and loading the launchd agent.

## Prerequisites

- [ ] Full Disk Access granted to `~/.local/lib/sprite/venv/bin/python` (see FDA_SETUP.md)
- [ ] Herman brain running on port 8765 (`homunculus-brain` or `uvicorn`)
- [ ] Ollama running with `qwen2.5:7b` resident (`ollama run qwen2.5:7b`)
- [ ] whisper-cli installed (`brew install whisper-cpp` installs the `whisper-cli` binary) and model at `~/sprite/models/ggml-small.en.bin`
- [ ] ffmpeg installed (`brew install ffmpeg`) — required to decode Voice Memos .m4a files
- [ ] iCloud sync enabled for Voice Memos on your iPhone (Settings → [Your Name] → iCloud → Voice Memos: On)

## Step 1: Load the agent

```bash
launchctl load ~/Library/LaunchAgents/com.sprite.watcher.plist
launchctl list | grep sprite
# Expect: PID   0   com.sprite.watcher
```

## Step 2: Tail the log

Open a terminal and tail the watcher log:

```bash
tail -f /tmp/sprite_watcher.log
```

Expected cold-boot output:
```
INFO sprite.watcher Sprite watcher v0.5.0 starting
INFO sprite.watcher   recordings:  ~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings
INFO sprite.watcher cold-boot: scanning ...
INFO sprite.watcher cold-boot: dispatched 0 / 0 files
INFO sprite.watcher watcher: watching ...
```

If you see:
```
ERROR sprite.icloud FDA required: cannot read Voice Memos at ...
```
→ FDA was not granted correctly. Re-check FDA_SETUP.md step 3.

## Step 3: Record a test memo on your iPhone

Say exactly: **"Sprite test one two three, schedule a meeting with myself on Monday at nine."**

Wait for the Voice Memos app to show the recording has synced to iCloud (the cloud icon disappears).

## Step 4: Watch the pipeline fire

Within 60 seconds of sync completing, the watcher log should show:

```
INFO sprite.watcher watcher: new file seen: <uuid>.m4a
INFO sprite.icloud  archive: <uuid>.m4a → ~/sprite/audio/2026/09/<uuid>.m4a
INFO sprite.transcribe transcribe: transcoding <uuid>.m4a → WAV (16 kHz mono) via ffmpeg
INFO sprite.transcribe transcribe: running whisper-cli on <uuid>.m4a
INFO sprite.transcribe transcribe: "Sprite test one two three ..." conf=0.87 saved ...
INFO sprite.parse   [Preprocessor hint: verb is likely 'schedule']
INFO sprite.watcher process: verb=schedule subject='meeting with myself' conf=0.82 ambiguous=[]
INFO sprite.herman  herman: accepted record_id=<...> event_id=<...>
INFO sprite.watcher process: done — record_id=<...> event_id=<...> written_path=calendar/...
```

## Step 5: Verify Herman wrote the event

```bash
# Check the vault calendar dir for the new event:
ls ~/homunculus/vault/calendar/ | sort -r | head -5

# Check the state log for the processed record:
tail -5 ~/sprite/state/processed.jsonl | python3 -m json.tool
```

## Step 6: Check the morning summary (optional)

If Herman is running and it's before 7 AM:

```bash
curl -s http://localhost:8765/reminders/upcoming?window_hours=24 | python3 -m json.tool | head -40
```

The event should appear in the schedule.

## Troubleshooting

| Symptom | Check |
|---|---|
| FDA error in log | Re-grant FDA to the Python binary (not just the shell script) |
| whisper-cli not found | `brew install whisper-cpp` (installs `whisper-cli`) and verify: `which whisper-cli` |
| ffmpeg not found | `brew install ffmpeg` — required to decode .m4a Voice Memos |
| model not found | Download: `whisper-cpp-download-ggml-model small.en`, move to `~/sprite/models/` |
| Ollama unreachable | `curl http://localhost:11434/api/tags` — Ollama must be running |
| Herman unreachable | `curl http://localhost:8765/health` — brain must be running |
| Low confidence → inbox | Check `~/sprite/inbox/YYYY-MM-DD.md` — transcript may be garbled |
| No sync in 90s | Check iCloud status: Settings → [Name] → iCloud → Voice Memos |

## Verifying the iCloud path exists (reality check)

```bash
# Before FDA: should return "Operation not permitted"
ls ~/Library/Group\ Containers/group.com.apple.VoiceMemos.shared/Recordings/ 2>&1
# After FDA: should list .m4a files or be empty
```
