"""One-shot: mark every .m4a currently in the Voice Memos folder as already
processed, so Sprite's cold-boot sweep won't try to whisper+parse pre-existing
recordings on first live run.

Run once, before enabling the watcher live. Idempotent — safe to re-run.
"""

from pathlib import Path

from sprite.state import file_key, mark_processed


def main() -> None:
    recdir = (
        Path.home()
        / "Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"
    )
    state = Path.home() / "sprite/state/processed.jsonl"

    n = 0
    for p in sorted(recdir.glob("*.m4a")):
        mark_processed(
            state,
            file_key(p),
            audio_path=str(p),
            disposition="pre-seed",
            details={"reason": "seeded on first live run to skip pre-existing memos"},
        )
        n += 1
    print(f"seeded {n} existing memos as processed")


if __name__ == "__main__":
    main()
