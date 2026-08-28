---
name: golf-plaque
description: Generate a custom Bambu Studio 3MF plaque with three lines of engraved text. Use when the operator asks to create a plaque, generate a hole-in-one plate, or make a custom 3MF award.
---

# Golf Plaque Generator

This skill produces a Bambu Studio-compatible `.3mf` file for a three-line engraved plaque, ready to slice and print.

## Inputs to collect

Before invoking the generator, make sure you have all three of the following. If any are missing, ask the user for them (one clarifying question, all at once):

1. **Line 1** — usually the honoree's name (e.g. `Thomas Gagne`).
2. **Line 2** — the achievement (e.g. `Hole in One` or `Ace`).
3. **Line 3** — the venue / date / context (e.g. `Pebble Beach, 4th hole` or `2026-08-27`).

Also determine the **output path**:

- If the user specifies a path (`/tmp/...`, `~/Desktop/foo.3mf`, etc.), use it verbatim.
- If they don't, default to `~/Downloads/plaque.3mf`. Expand `~` before passing to the CLI.

## How to invoke

Run the CLI from this skill's directory so the packaged template resolves correctly:

```bash
cd "$CLAUDE_PLUGIN_ROOT"  # or the absolute path to this skill folder
python generate.py "Line 1" "Line 2" "Line 3" --out /absolute/path/to/plaque.3mf
```

On success, `generate.py` prints the absolute output path on stdout and exits 0. On failure, it prints a one-line error to stderr and exits 1.

## Reporting back

Once the file is written, tell the user:

- The absolute output path.
- One-line confirmation the file was created (you may check the size with `ls -l` if useful).
- A short next-step hint: "Open this in Bambu Studio to slice and print."

## Troubleshooting

- **`Template not found`** — the `Frames/Mike Kallbrier.3mf` file next to `generate.py` is missing. Reinstall the skill folder.
- **`Font 'Helvetica' not found`** — on Linux, install a Helvetica-equivalent (e.g. `sudo apt install fonts-liberation`). On macOS this should never happen.
- **`ModuleNotFoundError`** — the operator hasn't installed dependencies. Run `pip install -r requirements.txt` from this skill's directory.
