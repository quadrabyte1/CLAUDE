# golf-plaque — Claude Code Skill

Generate a Bambu Studio-compatible `.3mf` plaque with three lines of engraved text, ready to slice and print.

## Install

```bash
cp -r golf-plaque-skill ~/.claude/skills/golf-plaque
pip install -r ~/.claude/skills/golf-plaque/requirements.txt
```

## Use from Claude Code

Ask Claude something like:

> `/golf-plaque` Make a plaque for Thomas Gagne — Hole in One — Pebble Beach, 4th hole. Save it to `~/Desktop/thomas_plaque.3mf`.

Claude will collect the three text lines (asking if any are missing), pick an output path (defaulting to `~/Downloads/plaque.3mf`), invoke `generate.py`, and report the finished file path. Drop the resulting `.3mf` into Bambu Studio to slice and print.

## Use from the shell

```bash
cd ~/.claude/skills/golf-plaque
python generate.py "Thomas Gagne" "Hole in One" "Pebble Beach, 4th" --out ~/Desktop/plaque.3mf
```

On success it prints the absolute output path. On failure it prints a one-line error to stderr and exits 1.

## Contents

- `SKILL.md` — Claude Code skill definition (invoked as `/golf-plaque`).
- `generate.py` — thin CLI wrapper around the plate library.
- `plate_text.py` — plaque geometry + 3MF assembly library (copied from the source Flask app).
- `Frames/Mike Kallbrier.3mf` — Bambu Studio template that defines plate size, tilt, and print settings. Every generated plaque is patched on top of this.
- `requirements.txt` — Python dependencies (`trimesh`, `numpy`, `matplotlib`, `shapely`).

## Troubleshooting

- **Template not found** — verify `Frames/Mike Kallbrier.3mf` is present next to `generate.py`. If missing, restore from the original handoff folder.
- **Font not found** — the plaque renders in Helvetica. On macOS Helvetica is installed by default. On Linux install a Liberation/Helvetica equivalent, e.g. `sudo apt install fonts-liberation`.
