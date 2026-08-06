# Skillify Golf Pages for Claude Design — Research Plan

**Prepared by:** Pax (Senior Researcher)
**Date:** 2026-08-02
**Status:** DRAFT — awaiting Thomas's approval before implementation begins

---

## Target Platform Summary

Claude Design is an Anthropic Labs beta product (launched April 17, 2026) at `claude.ai/design`. It is a
conversational design tool — chat interface + live canvas — that accepts text prompts, images, codebases,
and design system files, then generates HTML/CSS prototypes, decks, and one-pagers using Claude Opus 4.7.
It is **not a general-purpose app platform**; it is a visual-output collaborator.

Sources consulted:
- https://claude.com/product/design
- https://support.claude.com/en/articles/14604416-get-started-with-claude-design
- https://www.anthropic.com/news/claude-design-anthropic-labs
- https://claude.com/plugins/design
- https://claude.com/plugins/frontend-design

---

## CRITICAL FINDING: Claude Design Does Not Have a Public Skill/Plugin Authoring SDK

This is the most important result of the research and must be understood before any steps are planned.

**What the docs actually say:**
- The "plugins" at `claude.com/plugins/design` and `claude.com/plugins/frontend-design` are
  **Anthropic-built marketplace plugins**, not a developer-extensible plugin SDK. They are installed
  by clicking "Add to Claude" and activate automatically in conversations. There is no manifest format,
  directory structure, or build toolchain documented publicly for creating your own.
- The only extension mechanism documented publicly is the **Claude Design MCP server**:
  `claude mcp add --scope user --transport http claude-design https://api.anthropic.com/v1/design/mcp`
  This connects Claude Code (terminal) to Claude Design so you can import/export designs between
  environments — it is not a skill authoring API.
- The announcement notes Anthropic plans to "make it easier to build integrations with Claude Design"
  but no third-party skill SDK exists yet as of August 2026 based on public documentation.
- The `claude.com/plugins/frontend-design` plugin (1.1M+ installs) is Anthropic-verified and
  activates automatically for frontend UI requests. Users cannot author equivalent plugins yet.

**What "skills" likely refers to in the task context:**
Thomas's request to "turn golf pages into skills that can be imported into Claude Design" most likely
refers to one or more of these interpretable paths:
  (A) Claude Code Skills (slash commands in `.claude/`) — these are the skills the team already uses,
      and they *can* be invoked from Claude Code sessions that are synced with Claude Design via
      `/design-sync`. This is a real, working integration path TODAY.
  (B) Design system import — uploading the golf app's HTML/CSS/Alpine components as a design system
      so Claude Design uses the real UI vocabulary when generating new pages.
  (C) Waiting for Anthropic's forthcoming third-party plugin SDK (no ETA known).

**Recommendation:** Pursue path (A) + (B) — they are achievable now and deliver real value.

---

## Golf Code Survey

### Entry points and file sizes

| File | Lines | What it does |
|------|-------|-------------|
| `app/templates/plaque.html` | 186 | Alpine-driven UI for plaque text entry; calls `/api/generate_plate` |
| `app/templates/editor.html` | 2,163 | Full Boundary Editor — Alpine + Tailwind canvas UI; calls 6+ `/api/*` routes |
| `app/plate_text.py` | 949 | Core 3MF generator: renders font glyphs to trimesh meshes, builds oval plate, writes 3MF |
| `app/generate_stl_3mf.py` | 1,156 | EGM path helpers, Catmull-Rom spline, flat mesh builders, hole-in-one piece generator |
| `app/generate_flat_pieces_v2.py` | 923 | Segmentation pipeline: green/fringe/trap mask detection, flat STL generation |
| `app/generate_flat_pieces_hole9.py` | 850 | Hole-9-specific flat piece variant |
| `app/gradient_surface_diagnostic.py` | 5,857 | Full gradient surface pipeline: arrow detection, Poisson height solve, 3MF output via `run_pipeline()` |
| `app/app.py` | 2,313 | Flask monolith: routes `/editor`, `/plaque`, `/api/generate_models`, `/api/generate_plate`, etc. |

### Dependency chains

**Plaque flow:**
`plaque.html` → `POST /api/generate_plate` (app.py:2155) → `plate_text.generate_plate_3mf()` → trimesh + shapely + numpy → writes `.3mf` to disk → SMTP email + optional `open` subprocess (Bambu Studio)

**Boundary Editor / Hole Renderer flow:**
`editor.html` → multiple `/api/*` calls (detect_boundaries, find_contours, generate_models) → `gradient_surface_diagnostic.run_pipeline()` → `generate_stl_3mf.*` → trimesh + scipy + cv2 + shapely + skimage → writes `.3mf` to `EliteGolfMoments/GolfCourses/<Course>/3MFs/`

### Coupling assessment

| Component | Flask coupling | Portability |
|-----------|---------------|------------|
| `plate_text.py` | None — pure library | HIGH — clean function signatures, no Flask imports |
| `generate_stl_3mf.py` | Low — only `EGM_BASE` path constant | MEDIUM — needs EGM_BASE re-pointed |
| `gradient_surface_diagnostic.py` | None — pure pipeline | MEDIUM-LOW — 5,857 lines, scipy/cv2/numpy heavy; not browser-runnable |
| `editor.html` | Heavy — 6+ `fetch('/api/...')` calls to Flask routes | LOW — tightly bound to live Flask server |
| `plaque.html` | Light — 1 `fetch('/api/generate_plate')` | MEDIUM — small template, easy to extract |
| `app.py` routes | Flask-native | NOT PORTABLE as-is — must be rewrapped |

### Output destinations (current)

- Plaques: `.3mf` file emailed via SMTP + optional local slicer open (`subprocess` → `open` command, macOS-only)
- Hole renders: `.3mf` saved to `EliteGolfMoments/GolfCourses/<Course>/3MFs/` on Thomas's local disk

Neither output mechanism works inside Claude Design's sandboxed browser environment. Any skillification
must handle output differently (downloadable file via HTTP response, or push to external storage).

---

## Skill-Slicing Decision

**Decision: Two Claude Code Skills + one Design System import. Do NOT try to build a Claude Design plugin.**

**Reasoning:**
1. There is no public third-party plugin SDK for Claude Design. Building to a non-existent spec is risky.
2. The heavy computation (scipy, cv2, trimesh, numpy) cannot run in a browser; it must stay server-side.
3. Claude Code Skills (`.claude/commands/`) are already the team's established pattern and integrate
   with Claude Design via `/design-sync` and the MCP bridge.
4. The plaque generator (`plate_text.py`) is already nearly a standalone library — one skill wraps it trivially.
5. The Boundary Editor is too complex to "import" — it is a full app. The right move is to expose its
   core pipeline as a callable skill that Claude Code can invoke.

**Proposed skills:**

| Skill | Name | What it does |
|-------|------|-------------|
| Skill 1 | `/golf-plaque` | Claude Code slash command: takes 3 text lines + font, calls `plate_text.generate_plate_3mf()`, returns download link or file path |
| Skill 2 | `/golf-render` | Claude Code slash command: takes EGM file path or course name, calls `gradient_surface_diagnostic.run_pipeline()`, returns 3MF path |
| Design System | Golf UI components | Export `editor.html` + `plaque.html` Alpine/Tailwind components as a design-system ZIP for Claude Design to reference when generating new golf-related pages |

---

## Numbered Step List

Steps are ordered: validate platform → extract core libraries → wrap as skills → add design system → wire to Claude Design.

### Phase 0: Platform validation (do this before any code changes)

1. **Sign in to claude.ai/design** and create a test project. Confirm you can see the interface and that the MCP server step below is possible from your account tier.

2. **Add the Claude Design MCP server to Claude Code:** run `claude mcp add --scope user --transport http claude-design https://api.anthropic.com/v1/design/mcp` in your terminal. Confirm it appears in `/mcp` within Claude Code. This is the official bridge between Claude Code Skills and Claude Design.

3. **Install the Frontend Design plugin** (`claude.com/plugins/frontend-design`) in your Claude account. Load a new Claude Design project and ask it to "build a simple dashboard with a canvas and a sidebar." Observe what it generates — this tells you what the design system import format looks like in practice before you build your own.

### Phase 1: Extract `plate_text.py` as a standalone library (low risk)

4. **Audit `plate_text.py` for hidden Flask dependencies.** (`grep -n "flask\|request\|session\|current_app" app/plate_text.py`) Confirm it has none. Current survey says it is clean.

5. **Create `app/golf_plaque_skill.py`** — a thin wrapper that: (a) imports `generate_plate_3mf` from `plate_text`, (b) accepts args as CLI flags or a JSON payload, (c) writes the 3MF to a temp directory and prints the path. This becomes the skill's execution target.

6. **Write `.claude/commands/golf-plaque.md`** — the Claude Code skill definition. Front-matter declares the skill name; body instructs Claude to call `golf_plaque_skill.py` with the user's three text lines and font choice, then report the output path.

7. **Smoke-test `/golf-plaque`** in a Claude Code session: `"Generate a plaque for John Smith / Hole in One / Pebble Beach"`. Confirm a `.3mf` is created at the expected path.

### Phase 2: Wrap the Boundary Editor pipeline as a skill (medium complexity)

8. **Create `app/golf_render_skill.py`** — a thin CLI wrapper around `gradient_surface_diagnostic.run_pipeline()`. Accepts `--egm <path>` and optional `--course <name>` (resolves via `generate_stl_3mf.course_paths()`). Prints the output `.3mf` path on completion.

9. **Write `.claude/commands/golf-render.md`** — the Claude Code skill definition. Instructs Claude to resolve the course name to an EGM file, invoke `golf_render_skill.py`, and report the output path.

10. **Smoke-test `/golf-render`** in a Claude Code session with an existing EGM file. Confirm the 3MF is generated at `EliteGolfMoments/GolfCourses/<Course>/3MFs/`.

11. **DECISION POINT — open question #1 (see below).** The pipeline currently opens the file in Bambu Studio via `subprocess`. Decide whether the skill should do this automatically or just report the path and let Thomas open it. Recommendation: report path only; keep the slicer-open as an optional `--open-slicer` flag.

### Phase 3: Design system import into Claude Design (low complexity, high value)

12. **Extract the golf UI component vocabulary.** Copy the Alpine/Tailwind markup from `editor.html` (canvas toolbar, boundary overlay, course selector) and `plaque.html` (3-line input form, font picker) into a standalone `golf-design-system/` folder with a single `index.html` that renders all components together.

13. **Add a `design-tokens.json`** file (or equivalent CSS custom properties) listing the color palette, font stacks (Orbitron + fallback), and spacing values currently hardcoded in the templates.

14. **Import the design system into Claude Design** via the "attach design system" flow (GitHub repo or ZIP upload per the getting-started docs). Verify Claude Design can reference "golf canvas panel" or "plaque input form" as named components when generating new pages.

15. **Test a generation request** in Claude Design: "Add a new tab to the golf plaque page that shows recent plaque history." Confirm it uses your design system tokens, not generic defaults.

### Phase 4: Wire Claude Code Skills to Claude Design (requires MCP bridge from Step 2)

16. **Use `/design-sync` in Claude Code** to import the current Claude Design canvas into the codebase. Verify the round-trip works (Design → Code → back to Design).

17. **In a Claude Design session, invoke `/golf-plaque`** via the Claude Code MCP bridge. Document whether Claude Design can trigger Claude Code Skills directly or whether you must switch to a Claude Code session. This is an OPEN QUESTION (see below).

18. **Write a `SKILLS.md`** in `.claude/` documenting the two golf skills, their args, and the expected output paths. This doubles as the "handoff doc" for future team members or for Jim.

### Phase 5: Hardening (after validation)

19. **Add error handling to both skill wrappers:** missing EGM file, missing font, SMTP not configured. Skills should emit a clear one-line error message Claude can relay to the user.

20. **Add output confirmation to `/golf-plaque`:** after generating, print a summary line: `"Plaque saved to <path>. Email delivery: <yes/no>."` Skills should not silently succeed.

21. **Update `.gitignore`** to exclude any temp 3MF files written by the skills (if they write outside the existing `EliteGolfMoments/` tree).

---

## Open Questions (Thomas must resolve before Phase 5)

| # | Question | Why it blocks |
|---|----------|--------------|
| 1 | **Does your Claude plan (Pro/Max/Team/Enterprise) give you access to claude.ai/design?** It launched in beta for Pro+. If not, Phase 0 is blocked. | Steps 1–3 |
| 2 | **Can Claude Design sessions invoke Claude Code Skills directly via the MCP bridge, or does that require a separate Claude Code session?** The docs describe MCP as a terminal integration, not an in-Design trigger. | Steps 16–17 |
| 3 | **Where should skill-generated 3MFs land?** Currently `EliteGolfMoments/GolfCourses/<Course>/3MFs/`. For the plaque skill, there's no course folder — should plaques go to `owner_inbox/_plaques/` or a new `EliteGolfMoments/Plaques/` folder? | Step 5–6 |
| 4 | **Is there an Anthropic third-party plugin SDK in private beta** that Thomas could apply for? The launch announcement says more integrations are coming. If so, skip path A and go straight to a proper plugin. | Changes entire plan |
| 5 | **Should `/golf-render` support multi-hole batch rendering,** or one EGM at a time? The current pipeline is one EGM → one 3MF. | Step 9 |

---

## Suggested First Move

The smallest thing Thomas can do today to validate the approach:

> **Sign in to claude.ai/design, add the MCP server** (`claude mcp add --scope user --transport http claude-design https://api.anthropic.com/v1/design/mcp`), then in Claude Code run `/golf-plaque` after writing the stub skill in Step 6. If the plaque generates successfully from a slash command, the whole architecture is validated before any further investment.

This takes under 30 minutes and answers whether the Claude Code → plate_text pipeline works as a skill today, independent of any Claude Design uncertainty.

---

*Full research notes are contained in this file. Journal entry logged in `db/workspace.db`.*
