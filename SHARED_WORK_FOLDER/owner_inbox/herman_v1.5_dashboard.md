# Herman v1.5.0 — Activity Dashboard Handoff

**Date:** 2026-09-15 | **Author:** Rune

---

## Version badge

`v0.1 · Homunculus Dashboard` — displayed in the upper-left corner of the page.
Herman itself: `1.5.0` / design `1.5`.

---

## What shipped

### New files

| File | Purpose |
|------|---------|
| `Homunculus/brain/homunculus_brain/dashboard.py` | All dashboard logic: row shaping, JSONL reader, HTML string |
| `Homunculus/brain/tests/test_dashboard.py` | 10 new tests covering all six spec items + limit param |

### Changed files

| File | Change |
|------|--------|
| `homunculus_brain/server.py` | Two new routes: `GET /dashboard/` and `GET /dashboard/data` |
| `homunculus_brain/__init__.py` | VERSION 1.4.0 → 1.5.0, DESIGN_VERSION 1.4 → 1.5 |
| `pyproject.toml` | version 1.4.0 → 1.5.0 |
| `docs/RUNBOOK.md` | Version header, health-response example, version-history table |
| `deploy/README.md` | Version header and health-response note |
| `README.md` | Status block — v1.5.0 entry prepended |

### No new Python dependencies

Everything runs on FastAPI + stdlib. No npm, no build step.

---

## Layout — ASCII mockup

```
┌──────────────────────────────────────────────────────────────────────────┐
│ v0.1 · Homunculus Dashboard                                              │
│                                                                          │
│  Homunculus Activity    Last 39 events · Auto-refresh 5 s   Refresh now │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  📝  verb=note  test notes mechanism                      just now  0.85 │
│      capture_parsed                                                      │
│ ─────────────────────────────────────────────────────────────────────── │
│  ✓   verb=handle  Check on Frozen auditions               3 h ago   0.82 │
│      capture_parsed                                                      │
│ ─────────────────────────────────────────────────────────────────────── │
│  ✓   verb=handle  review the homunculus enhancement list  Yesterday 0.85 │
│      capture_parsed                                                      │
│ ─────────────────────────────────────────────────────────────────────── │
│  📅  verb=schedule  second meeting with myself            Yesterday 0.85 │
│      capture_parsed                      [ROW EXPANDED ↓]               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ Raw text    Let's set a second meeting with myself tomorrow at…   │   │
│  │ Event ID    2026-09-15-second-meeting-with-myself                 │   │
│  │ Written     calendar/2026-09/2026-09-15-second-meeting-with-…    │   │
│  │ {                                                                 │   │
│  │   "verb": "schedule",                                            │   │
│  │   "subject": "second meeting with myself",                       │   │
│  │   "confidence": 0.852                                            │   │
│  │ }                                                                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│ ─────────────────────────────────────────────────────────────────────── │
│  📅  verb=schedule  code review with myself               Yesterday 0.83 │
│  ...                                                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

**Icon legend:**

| Icon | Verb / Kind |
|------|-------------|
| 📅 | schedule |
| ✓ | handle |
| 📝 | note |
| ⚠️ | avoid |
| ✔️ | event_ack |
| 🔹 | unknown |

**Confidence pill:** grey (`0.85`) if ≥ 0.6, orange if < 0.6.

---

## Steps to view

### 1. Bounce Herman via launchd

```bash
launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
launchctl load   ~/Library/LaunchAgents/com.homunculus.brain.plist
```

Wait ~3 seconds for uvicorn to come up, then:

```bash
curl http://localhost:8765/health
# Should show: "package_version": "1.5.0"
```

### 2. Open the dashboard

```
http://localhost:8765/dashboard/
```

The page loads the last 200 rows from `vault/_activity.jsonl` immediately,
then polls `/dashboard/data?since=<latest-seen>` every 5 seconds and prepends
any new rows with a 1-second pale-yellow fade highlight.

### 3. Trigger a new capture to watch it appear

Send a voice memo via Sprite, or POST directly:

```bash
curl -s -X POST http://localhost:8765/capture/text \
  -H 'Content-Type: application/json' \
  -d '{"text":"take a note about the dashboard","captured_at":null,"speaker_tz":"America/New_York"}' \
  | python3 -m json.tool
```

Within 5 seconds the new row appears at the top of the feed with the yellow
highlight. Click the row to expand — you'll see `raw_text`, `event_id`,
`written_path`, and the full `details` JSON.

### 4. Verify the since-filter (optional)

```bash
# Returns only rows since a specific timestamp
curl 'http://localhost:8765/dashboard/data?since=2026-09-14T00:00:00Z' | python3 -m json.tool
```

### 5. If Herman isn't running

The dashboard shows `⚠️ Disconnected` in the header and keeps retrying every
5 seconds. Once Herman comes back up, it clears automatically on the next
successful poll — no page reload needed.

---

## Empty state

If `vault/_activity.jsonl` doesn't exist or has no valid rows, the feed shows:

> No activity yet.
> Record a voice memo or POST to one of these endpoints:
> `POST /capture/text`   `POST /capture/parsed`

---

## Test summary

10 new tests in `tests/test_dashboard.py`, 128 total passing:

| # | Test | Covers |
|---|------|--------|
| 1 | `test_dashboard_page_returns_200_html` | HTML served, version badge present |
| 2 | `test_dashboard_data_empty_vault` | No file → `{"rows":[],"latest_at":null}` |
| 3 | `test_dashboard_data_reverse_chron_and_shape` | Newest-first; icon/summary/confidence correct per verb |
| 4 | `test_dashboard_data_since_filter` | `?since=` returns only rows newer than timestamp |
| 5 | `test_dashboard_data_since_exclusive` | Row exactly at `since` is excluded |
| 6 | `test_dashboard_data_skips_malformed_rows` | Bad JSON / missing `at` / unparseable `at` skipped |
| 7 | `test_confidence_nested_in_details` | `details.confidence` float extracted |
| 8 | `test_confidence_missing_is_null` | No confidence field → null |
| 9 | `test_confidence_string_value_coerced` | String `"high"` (v1.2-era rows) → null, no crash |
| 10 | `test_dashboard_data_limit` | `?limit=N` caps results |

---

## What v0.2 of the dashboard should be

Suggested priorities for the next dashboard iteration:

1. **Aggregate Sprite inbox + bridge push events.** Right now we only read
   `_activity.jsonl`. Adding Sprite's `processed.jsonl` and the bridge's
   pushed events would give a unified pipeline view: memo recorded → parsed
   → dispatched → calendar event created → reminder scheduled → acked. One
   row per stage, linked by `record_id`.

2. **Per-verb filter dropdown.** A `<select>` at the top of the feed
   filtering by verb (`all | schedule | handle | note | avoid | event_ack`).
   Client-side JS filter against the already-fetched rows — no extra endpoint.

3. **Manual "attended?" button.** Per-row button to mark an event as
   attended / resolved. Needs a new endpoint (`POST /dashboard/attended/{event_id}`)
   that writes a flag to the sidecar. The button would only appear on rows
   with an `event_id` and a `schedule` verb.

4. **Pagination / virtual scroll.** For now we cap at 200 rows. If the log
   ever gets large, add cursor-based pagination: `?before=<iso8601>` on
   `/dashboard/data`, with an infinite-scroll trigger at the bottom of the feed.

5. **WebSocket push.** Replace the 5-second poll with a WebSocket channel
   that streams new log entries as they're appended. Reduces latency from
   ~5 s to ~0 s. Not worth the complexity today; polling is fine for v1.

---

*Rune — Herman v1.5.0 — 2026-09-15*
