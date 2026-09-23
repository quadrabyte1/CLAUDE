# v0.4 · Dashboard Visual Redesign

**Rune — 2026-09-22**

---

## Design Direction

Replaced the dark `#111` theme with a modern productivity-app light theme. Reference aesthetic: GitHub, Linear — neutral, high-contrast, readable at a glance. No CDN dependencies; vanilla HTML/CSS/JS only.

The three complaints Thomas raised are all addressed:

| Complaint | Fix |
|---|---|
| Dark background is ugly | Light theme: `#f7f7f8` main bg, `#ffffff` feed rows |
| Everything scrolls off | Sticky layout: header + timers panel are pinned; only the feed scrolls |
| General clutter / polish | Better typography (15px base, 500-weight summaries), clear hierarchy, card borders, readable badges |

---

## Sticky Layout Structure

```
┌────────────────────────────────────────────────────┐
│  v0.4  Homunculus        3 events · Auto-refresh  │  ← header (sticky, z:20)
│                                                    │     white bg, 1px shadow
├────────────────────────────────────────────────────┤
│  ⏱ Running Timers  │  Project Totals              │  ← timers-panel (sticky, z:10)
│    gym  RUNNING 1h 23m 17s │ gym  RUNNING  4h 12m │     #eef2f7 blue-tinted bg
│    deck RUNNING   47m 12s  │ coding        18h 5m │
├────────────────────────────────────────────────────┤
│  Activity Feed                            ↑ fixed  │
│  📝 deck project            note   just now       │  ← #feed (flex:1, overflow-y:auto)
│  📅 meeting on Monday    schedule   3 min ago     │     only this region scrolls
│  ✔️  acked — strike_0   event_ack  12 min ago     │
│  ...                                              │
└────────────────────────────────────────────────────┘
```

Implementation is a CSS flex-column body at `height: 100vh; overflow: hidden`. Header uses `position: sticky; top: 0`, timers panel uses `position: sticky; top: 45px` (just below header). Feed gets `flex: 1; overflow-y: auto`. No JavaScript needed for the pinning.

---

## Color Choices

| Role | Value | Rationale |
|---|---|---|
| Main background | `#f7f7f8` | Off-white — warmer than pure white, less eye strain |
| Header / row background | `#ffffff` | Clean white for interactive surfaces |
| Timers panel background | `#eef2f7` | Subtle blue tint — visually separates the "status" zone from the "history" feed |
| Primary text | `#1a1a1a` | Near-black — high contrast, easier on the eye than pure black |
| Secondary / meta text | `#6b7280` / `#9ca3af` | Tailwind gray-500 / 400 — clear hierarchy without being invisible |
| Borders | `#e5e7eb` | Tailwind gray-200 — subtle but present |
| RUNNING badge | `#15803d` on `#dcfce7` | Green-700 on green-100 — readable, unambiguous status |
| Confidence OK pill | Same green pair | Consistent semantic colour for "good" signals |
| Confidence WARN pill | `#b45309` on `#fef3c7` | Amber-700 on amber-100 — muted warning, not alarming |
| Disconnected badge | `#b45309` on `#fef3c7` + amber border | Same amber family — appropriate urgency level |
| Version badge | `#ffffff` on `#4b5563` | Dark pill, white text — readable at small size, not distracting |
| New-row highlight animation | `#fef9c3` → `#ffffff` | Yellow flash — light-theme equivalent of the old amber glow |
| Expand panel bg | `#f8fafc` | Slightly cooler than main bg — clearly "nested" context |
| Expand JSON bg | `#f1f5f9` + `#e2e8f0` border | Slate-100 — code block, clearly distinct |

---

## Typography Changes

- Base font size: 14px → **15px**
- Row summary: 13px → **14px**, weight 400 → **500** (medium) — primary content, deserves prominence
- Row meta / time / pills: unchanged at 11–12px but colour adjusted for light bg
- Expand panel labels: added `text-transform: uppercase; letter-spacing: 0.05em` — clearer field headings
- Line height: default → **1.5** globally — more breathing room

---

## ASCII Sketch (before/after)

**Before (v0.3):**
```
██████████████████████ ← black body, everything flows from top
  v0.3 badge (fixed, dim on dark)
  header (not sticky)
  timers (scrolls away)
  feed (scrolls away)
```

**After (v0.4):**
```
░░░░░░░░░░░░░░░░░░░░░░ ← #f7f7f8 off-white body
┌──────────────────────┐  ← STICKY header (white, shadow)
│ v0.4  Homunculus    │
├──────────────────────┤  ← STICKY timers (#eef2f7)
│ Running │ Totals    │
├──────────────────────┤
│ feed row 1           │  ← scrollable area starts here
│ feed row 2           │
│ ...                  │
└──────────────────────┘
```

---

## Files Changed

| File | Change |
|---|---|
| `Homunculus/brain/homunculus_brain/dashboard.py` | `DASHBOARD_VERSION` v0.3 → v0.4; full `_DASHBOARD_HTML` rewrite (CSS + HTML structure); JS updated to target `#feed-inner` |
| `Homunculus/brain/homunculus_brain/__init__.py` | `VERSION` 2.1.0 → 2.1.1 |
| `Homunculus/brain/pyproject.toml` | `version` 2.1.0 → 2.1.1 |
| `Homunculus/brain/tests/test_dashboard.py` | Added 6 new structural tests (tests 8.1–8.6) |

---

## Red → Green Table

| # | Test | Before (v0.3) | After (v0.4) |
|---|---|---|---|
| 8.1 | `test_v04_version_badge` — DASHBOARD_VERSION == "v0.4" | FAIL | PASS |
| 8.2 | `test_v04_sticky_header` — header has position:sticky | FAIL | PASS |
| 8.3 | `test_v04_sticky_timers_panel` — #timers-panel has position:sticky | FAIL | PASS |
| 8.4 | `test_v04_light_theme_body_background` — body bg not dark | FAIL | PASS |
| 8.5 | `test_v04_feed_scrollable` — #feed has overflow-y:auto | FAIL | PASS |
| 8.6 | `test_v04_version_badge_readable_contrast` — badge not color:#aaa | FAIL | PASS |
| 1–7 | All 10 existing regression tests | PASS | PASS |

**Total: 16/16 PASS**

---

## Migration Steps for Thomas

1. **Bounce Herman** (picks up the new module):
   ```
   launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
   launchctl load  ~/Library/LaunchAgents/com.homunculus.brain.plist
   ```
2. **Hard-refresh the dashboard tab** — Cmd+Shift+R in the browser. The old dark stylesheet is inlined in the HTML response, so a hard refresh (not just reload) is needed to flush the browser's cached version.
3. You should see the light theme immediately. The `v0.4` badge is in the upper-left of the header.

---

## Design Questions for v0.5

These are flagged as candidates, not commitments:

- **Compact vs comfortable spacing** — current padding is moderate (10px rows). A density toggle (compact/default) would let Thomas choose based on how many events he typically has on screen at once.
- **Distinct color per verb** — each verb type (schedule, note, handle, avoid, timer) gets its own left-border accent color on the row. Makes the feed scannable at a glance without reading text.
- **Sidebar navigation / filters** — filter the feed by verb, date range, or project. Useful once the log grows past a few hundred events.
- **Dark mode toggle** — the current dark theme is gone, but a toggle for users who prefer dark can be added as a CSS class swap in v0.5.
- **Timers panel collapse** — a small chevron to fold the timers panel when no timers are running, maximizing feed height.
