# Homunculus

A voice-first capture and reminder assistant for the boss.

**Design version:** 1.0 (relocked 2026-06-07; see
`~/.claude/projects/-Volumes-GIT-CLAUDE/memory/project_homunculus.md` for the
locked decisions).

The current architecture is **Mac-as-brain, phone-as-thin-client**:

- The Mac runs `brain/` — a Python FastAPI server backed by a local LLM
  (Ollama). It holds the markdown calendar, classifies and routes captures,
  and generates reminder schedules.
- The phone (not yet built) is the press-to-talk surface and runs
  `UNUserNotificationCenter` to fire the reminders the brain pushes to it
  over Tailscale.
- The Watch mirrors phone notifications. No native Watch app in v1.

## Layout

```
Homunculus/
├── README.md                — this file
├── brain/                   — Mac-side Python brain (FastAPI + Ollama)
├── vault/                   — markdown source of truth (calendar/, tools/, prompts/, inbox.md)
└── docs/                    — design notes and runbooks
```

## Current state

| Layer       | Status                                                                  |
| ----------- | ----------------------------------------------------------------------- |
| Mac brain   | Skeleton + core logic + tests. 44 unit tests pass. Real LLM not wired.  |
| Vault       | Layout exists; empty until first capture.                               |
| Phone app   | Not started. Will be a thin Swift client; Kit's job.                    |
| Watch       | Auto-mirrors phone notifications; no native app.                        |
| Reminders   | Schedule generation works; push to phone is a stub until the app exists.|

## Where to start

- Brain install + run: `brain/README.md`.
- Design source of truth: the memory entry at
  `~/.claude/projects/-Volumes-GIT-CLAUDE/memory/project_homunculus.md`.
- Versioning: `x.y` — `y` increments on small modifications, `x` on
  significant architectural changes. Bump in the memory entry whenever
  the design moves.
