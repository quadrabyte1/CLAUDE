# Sprite v0.3.0 — 2026-09-13 — Rune

## What shipped

Two bugs from the first live run on 2026-09-13, both fixed, both covered by
new regression tests. 99 tests pass (up from 91).

---

## Root causes

### Bug 1 — whisper-cli binary rename

Homebrew's `whisper-cpp` formula renamed the CLI binary from `main` to
`whisper-cli` upstream. Sprite's `_DEFAULT_WHISPER_BIN = "whisper-cpp"` in
`src/sprite/transcribe.py` pointed at a binary that no longer exists at that
name. Thomas worked around it with `SPRITE_WHISPER_BIN=/opt/homebrew/bin/whisper-cli`
in the plist. The constant is now corrected to `"whisper-cli"`.

### Bug 2 — whisper-cli cannot decode .m4a (the blocker)

Voice Memos writes AAC audio in an MP4 container (`.m4a`). whisper-cli's
bundled `miniaudio` decoder does not reliably handle Apple AAC-in-MP4; it
exits with:

```
read_audio_data: failed to read audio data
error: failed to read audio file '/tmp/test.m4a'
```

**Fix:** transcode M4A → 16 kHz mono PCM WAV via ffmpeg before passing the
file to whisper-cli. ffmpeg handles Apple AAC perfectly and is the industry
standard cross-platform tool for this. Rejected alternatives:

| Alternative | Rejection reason |
|---|---|
| pydub + ffmpeg | Just wraps ffmpeg; adds a dep with zero benefit |
| audioread / soundfile | Worse M4A coverage than ffmpeg |
| AVFoundation / pyobjc | Mac-only. Violates portability religion. Hard no. |
| afconvert (macOS built-in) | Mac-only. Same violation. Hard no. |

ffmpeg is not pip-installable but universally available (`brew install ffmpeg`
on macOS, `apt install ffmpeg` on Linux). Consistent with the portability
contract: the codebase runs unchanged on Linux once ffmpeg is installed there.

---

## What changed

### `src/sprite/transcribe.py`
- `_DEFAULT_WHISPER_BIN`: `"whisper-cpp"` → `"whisper-cli"`
- New `_transcode_to_wav(audio_path, tmpdir) -> Path` helper — calls
  `ffmpeg -y -loglevel error -i <in> -ar 16000 -ac 1 -c:a pcm_s16le <out.wav>`.
  Raises `WhisperError` (not raw `FileNotFoundError`) when ffmpeg is absent,
  with a message that names the install command.
- `transcribe()` now checks `audio_path.suffix.lower() != ".wav"` and calls
  `_transcode_to_wav` before invoking whisper-cli. WAV files are passed
  directly (symlinked into tmpdir as before). No change to the output contract.
- Module docstring and inline comments updated throughout.

### `src/sprite/watcher.py`
- Version string: `"Sprite watcher v0.2.0 starting"` → `"Sprite watcher v0.3.0 starting"`

### `pyproject.toml`
- `version = "0.2.0"` → `version = "0.3.0"`

### `deploy/com.sprite.watcher.plist` (repo template)
- Added `PATH` key: `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin` so
  ffmpeg and whisper-cli resolve under launchd's minimal environment.
- `SPRITE_WHISPER_BIN` moved to a commented-out example (the default now
  resolves via PATH). Future installs don't need the env var override.

### `/Users/fourierflight/Library/LaunchAgents/com.sprite.watcher.plist` (live)
- Added `PATH` key: `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin`
- Kept `SPRITE_WHISPER_BIN = /opt/homebrew/bin/whisper-cli` as
  belt-and-suspenders (absolute path + PATH both point at whisper-cli).

### `deploy/install.sh`
- Added ffmpeg presence check at end of install — prints install command if
  ffmpeg is missing.
- Updated whisper model-download instructions to reflect `whisper-cli` naming.

### `docs/FIRST_RUN.md`
- Added ffmpeg to prerequisites checklist.
- Updated expected log line: `running whisper-cpp` → transcoding + `running whisper-cli`.
- Updated troubleshooting table: `whisper-cpp not found` → `whisper-cli not found`,
  added ffmpeg row.
- Version string in expected output updated to v0.3.0.

### `README.md`
- Title, pipeline diagram, and install steps updated for v0.3.
- Added `brew install ffmpeg` as step 3.

---

## Red → green story

**Before patch — collection error (tests in `test_transcribe.py` fail to import):**
```
ImportError: cannot import name '_transcode_to_wav' from 'sprite.transcribe'
```

**After patch — all 8 new tests pass, 91 prior tests unchanged:**
```
tests/test_transcribe.py::test_default_whisper_bin_is_whisper_cli PASSED
tests/test_transcribe.py::test_transcribe_m4a_returns_nonempty_text PASSED
tests/test_transcribe.py::test_transcribe_wav_skips_transcode PASSED
tests/test_transcribe.py::test_transcribe_m4a_missing_ffmpeg_raises_clear_error PASSED
tests/test_transcribe.py::test_transcode_to_wav_calls_ffmpeg_correctly PASSED
tests/test_transcribe.py::test_transcode_to_wav_missing_ffmpeg PASSED
tests/test_transcribe.py::test_transcode_to_wav_ffmpeg_failure PASSED
tests/test_transcribe.py::test_transcribe_confidence_from_logprob PASSED

99 passed in 0.12s
```

The four originally-required guards are covered:
1. `test_default_whisper_bin_is_whisper_cli` — bug-1 binary rename guard
2. `test_transcribe_m4a_returns_nonempty_text` — bug-2 M4A transcode path
3. `test_transcribe_wav_skips_transcode` — WAV regression guard
4. `test_transcribe_m4a_missing_ffmpeg_raises_clear_error` — missing-dep guard

---

## What Thomas needs to do next

1. **Install ffmpeg** (the one new hard dependency):
   ```bash
   brew install ffmpeg
   ```

2. **Reload the launchd agent** to pick up the plist change (new PATH key):
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.sprite.watcher.plist
   launchctl load  ~/Library/LaunchAgents/com.sprite.watcher.plist
   ```

3. **Remove the error entry for the failing memo** so the watcher reprocesses
   it on next cold-boot. The state log entry for
   `e4ddd82879e2a311df69dfa83a6b178a.m4a` (or its archived copy) is marked
   `"disposition": "error"`. Use the seed helper:
   ```bash
   # Option A: delete the specific error line from state
   # Find the key for the file:
   python3 -c "
   from sprite.state import file_key
   from pathlib import Path
   p = Path('$HOME/sprite/audio/2026/09/e4ddd82879e2a311df69dfa83a6b178a.m4a')
   print(file_key(p))
   "
   # Then remove that line from ~/sprite/state/processed.jsonl
   # (or just delete the file to reprocess everything)

   # Option B: delete the whole state file and let cold-boot reprocess all memos:
   rm ~/sprite/state/processed.jsonl
   ```

4. **Verify the pipeline fires** by tailing the log after load:
   ```bash
   tail -f /tmp/sprite_watcher.log
   ```
   Expected new lines:
   ```
   INFO sprite.watcher Sprite watcher v0.3.0 starting
   INFO sprite.transcribe transcribe: transcoding <uuid>.m4a → WAV (16 kHz mono) via ffmpeg
   INFO sprite.transcribe transcribe: running whisper-cli on <uuid>.m4a
   INFO sprite.transcribe transcribe: "..." conf=0.8x saved ...
   ```

5. **Confirm `SPRITE_WHISPER_BIN` env var is no longer required.** The live
   plist keeps the absolute-path override as belt-and-suspenders (safe), but
   future installs resolve via PATH and don't need it.

---

## Recommendation for M4 (next milestone)

- **WAV fixture in `tests/fixtures/`** — add a real 16 kHz mono WAV fixture
  so integration tests can exercise the WAV path end-to-end without mocking.
  `say "sprite test" | sox - -r 16000 -c 1 tests/fixtures/hello.wav` works.

- **Integration smoke test** — a `pytest -m integration` marker that calls
  real whisper-cli + ffmpeg on the fixture M4A and asserts non-empty transcript.
  Skipped in CI unless `SPRITE_INTEGRATION=1` is set. Prevents the binary
  mismatch class of bug from hiding in mocks.

- **ffmpeg version floor** — the ffmpeg AAC decoder has been stable since v3.
  Consider adding a version check in `_transcode_to_wav` (`ffmpeg -version`)
  to surface ancient system ffmpeg installs on Linux.

- **Processed-entry reuse** — the current state log uses `disposition: error`
  for both transient errors (ffmpeg missing) and permanent failures (bad file).
  A `disposition: transient_error` distinction would let a future `--retry`
  flag replay only the recoverable failures without reprocessing everything.
