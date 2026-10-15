# SETUP — Boundary Editor & Plaque Editor (standalone second machine)

## What this is

This repo runs the **Boundary Editor** and **Plaque Editor** as a single local
Flask web app on port **5051**. Each machine runs its own copy with its own
`db/workspace.db`. Course folders (`ItWentIn/GolfCourses/`) come with the
clone. There is no network mount, no cloud sync, no shared state. Writes on
your machine stay on your machine.

## Prerequisites

- **Python 3.13** — the pins in `requirements.txt` were resolved against 3.13
  wheels. See the "Install" step below for how to get by with 3.12 if you must.
  The cleanest path on macOS/Linux is `pyenv`:
  ```bash
  brew install pyenv       # macOS; use your package manager on Linux
  pyenv install 3.13.1
  pyenv local 3.13.1       # inside the repo root
  ```
- **git**
- **~3 GB free disk** for the clone (course folders are in the repo).
- **macOS or Linux**. The app assumes a POSIX shell (`run.sh`) and calls the
  macOS `open` command to hand `.3mf` files to Bambu Studio. On Linux `open`
  won't exist — the editor itself still works, but the "open in slicer"
  convenience button will report an error. Windows is unsupported out of
  the box (no `run.sh`, no `open`).

## Install

```bash
git clone <repo-url> CLAUDE
cd CLAUDE/SHARED_WORK_FOLDER
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**If you are stuck on Python 3.12**, two pins need loosening (both have 3.12
wheels, but not at the exact pinned version):

- `numpy==2.4.2` → `numpy>=2.1,<2.5`
- `pillow==12.1.1` → `pillow>=11,<13`

Edit `requirements.txt` locally (don't commit the change — it'll drift from
Thomas's machine) and re-run `pip install -r requirements.txt`. Everything
else in the file has 3.12 wheels at the pinned versions.

**Python 3.11 and older are not supported.** `numpy 2.x` dropped 3.10 support
and the pinned `shapely`/`trimesh` versions assume `numpy 2.x`.

## Workspace DB

The Flask app reads team/task/course rows from `db/workspace.db`. Standalone
users should **copy Thomas's current `workspace.db` once** as a starting
point:

```bash
scp thomas@<thomas-host>:/path/to/SHARED_WORK_FOLDER/db/workspace.db ./db/workspace.db
```

Heads-up: because each machine has its own copy, **writes you make on your
machine (new tasks, edits, closed rows) will not propagate back to Thomas**.
That's intentional and fine for standalone editor use. If you want to pull a
fresh copy later, overwrite the file (make a backup first).

## Run

```bash
cd app
./run.sh
```

Then open:

- Boundary Editor: <http://localhost:5051/editor>
- Plaque Editor:   <http://localhost:5051/plaque>

Port **5051** must be free. Logs stream to `app/logs/server.log`.

## Known limitations

- **Thomas-only helper scripts have hardcoded paths.** The following scripts
  in `app/` contain hardcoded `/Users/fourierflight/GIT/CLAUDE-GitHub/...`
  paths and will not run on your machine without further edits. **None of
  them are used by the Boundary Editor or Plaque Editor routes** — they are
  Thomas's one-shot utilities for unrelated projects (deck/patio mockups,
  Evernote migration, legacy flat-piece generators):
  - `clean_photo_lama.py`
  - `deck_mockup.py`
  - `evernote_migrate.py`
  - `generate_flat_pieces.py`
  - `generate_flat_pieces_checkpoint_a.py`
  - `generate_flat_pieces_hole9.py`
  - `hole9_boundaries.py`
  - `patio_mockup.py`
  - `patio_mockup_vera.py`
  - `patio_mockup_vera_porch.py`
  - `ridge_filter_test.py`

  You can ignore all of these. If you ever need one, swap its hardcoded
  constant for an `os.path.dirname(os.path.abspath(__file__))`-relative path.

- **Auto-start Login Item is Mac-only and boot-volume-only.** Thomas's setup
  starts the Flask app on login via a macOS Login Item that points at
  `~/.local/bin/start_web_servers.sh`. Don't try to replicate it — just run
  `./run.sh` manually in a terminal when you want the editor up.

- **`/Volumes/GIT/...` paths will not work on your machine.** Thomas's repo
  lives on an external volume. All editor code uses repo-relative paths
  (`os.path.dirname(__file__)` + `..`), so a plain `git clone` into any
  directory works fine. Just don't paste `/Volumes/GIT/CLAUDE/...` paths
  from Thomas's logs/screenshots into your shell.

- **"Open in slicer" button is macOS-only** (uses `/usr/bin/open`). On Linux
  the button will show an error but the 3MF is still written to disk — open
  it yourself.

## Troubleshooting

**Port 5051 already in use.**
```bash
lsof -i :5051           # find the PID
kill <pid>
```

**`ModuleNotFoundError: No module named 'flask'`** — you forgot to activate
the venv. `source .venv/bin/activate` from the repo root.

**`pip install` fails on numpy or pillow** — you're on Python 3.12 and need
the pin loosening described above. If `pip` claims no wheel is available on
3.13 either, your `pip` is stale: `pip install --upgrade pip` and retry.

**Editor loads but course dropdowns are empty** — `ItWentIn/GolfCourses/`
is missing; check you ran the app from the cloned `SHARED_WORK_FOLDER`.

**Editor loads but no team/task data on sidebar** — `db/workspace.db` is
missing. See the "Workspace DB" section above.
