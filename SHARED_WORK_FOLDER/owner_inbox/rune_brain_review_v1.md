# Rune — Fresh-eyes review of the Homunculus brain (v1.1)

**Reviewer:** Rune (Local-LLM Voice Assistant Backend Engineer)
**Brain commit reviewed:** repo head 2026-06-08, design v1.1, package v1.1.0
**Baseline:** 51 unit tests pass (`PYTHONPATH=. pytest tests/ -q` → `51 passed in 0.19s`). Unchanged.
**Scope:** review only. No refactors landed. No prompt tuning against a live model. No version bump.

---

## TL;DR

The v1.1 brain is on-architecture and is closer to "almost ready" than I expected for a Larry-scaffolded skeleton: schema-first discipline is intact, dates resolve in Python instead of in the prompt, the heuristic fallback is a real second parser rather than a debug helper, and the activity log is JSONL on disk rather than a SQLite footgun-in-waiting. What it is **not** yet ready for is a phone client and a real older user. The seven concrete gaps that scare me, in order: (1) no `speaker_tz` per-request — every event is written in the server's default zone even though the schema accepts a phone zone; (2) the morning summary function exists but nothing calls it, so the reliability chain the boss is counting on starts broken; (3) the inbox append is not lock-protected and the calendar write is not atomic, so two simultaneous captures can corrupt the vault; (4) `ambiguous_fields` is a `list[str]` of field *names* with no per-field confidence or candidate values, which means the clarifying-question UX is limited to "what day?" / "what time?" forever; (5) the system prompt instructs the model to copy time hints verbatim but gives it no examples and conflicts with `ambiguous_fields` ("if you guessed at any field, list it"); (6) `/ack`, `/undo`, `/reminders/upcoming`, and `/activity` are all unbuilt — Kit cannot ship a v1 phone without `/reminders/upcoming` and `/ack` at minimum; (7) there is no integration test that exercises capture → confirm → write → reminders → readback, which is the single user journey the boss will actually run. Below: section-by-section findings, then a prioritized punch-list. None of these block the heuristic-mode demo; all of them block trust.

---

## 1. Schema critique (`homunculus_brain/schemas.py`)

### What's right

- `ParsedIntent` is flat. No nested optional blobs. Good for a 7B model — qwen2.5:7b will fill a flat object far more reliably than a deeply nested one.
- `day_hint` / `time_hint` as raw strings, with the doctrine that resolution happens in `date_resolver.py`. This is the right call and the test suite at `tests/test_date_resolver.py` proves the math is testable.
- `body` field added in v1.1 for prompt notes. Good.
- `raw_text` is a required field — the LLM cannot lose the original utterance. Important for the activity log and for future "undo" recovery.

### What's missing or wrong

**(a) `ambiguous_fields` is too shallow to drive a real clarifying-question UX.**
Today it's `list[str]` of field names ("day", "time"). That gives the router exactly four clarifying questions ("What day?", "What time?", "What day and time?", "Can you say that again?") — see `intent_router._clarifying_question` at lines 332–339. It cannot express:
- "I heard Tuesday but I'm not sure if you meant *this* Tuesday or *next* Tuesday" (candidate values).
- "I'm 60% sure it's a calendar event, 40% sure it's a tool note" (per-field confidence).
- "I caught the name 'Jane' but I'm not sure if she's the participant or the topic" (semantic ambiguity).

For v1.2 I want this shape instead:
```python
class AmbiguousField(BaseModel):
    field: str                       # "day", "time", "kind", "people"
    why: str                         # human-readable: "said Tuesday but today is Tuesday afternoon"
    candidates: list[str] = []       # ["this Tuesday", "next Tuesday"]
ambiguous_fields: list[AmbiguousField] = []
```
That's a v1.2 schema change; it's a `PROTOCOL.md` change; Kit gets a review on it. **Do not ship this in v1.1** — the `list[str]` form is honest and works for the current four-question UX. But the persona-level commitment that "`ambiguous_fields` is the most valuable thing the parse returns" cannot stand if the shape stays this thin.

**(b) `speaker_tz` is on the request but not used.**
`CaptureRequest.speaker_tz: Optional[str]` (schemas.py:131) — accepted by `/capture/text` (server.py:50), and then **dropped on the floor**. The router uses `config.default_tz_name` unconditionally (intent_router.py:78, 127, 189). The persona's rule #4 ("Phone reports its TZ on every capture; the server respects it over `HOMUNCULUS_TZ`") is currently violated. If the boss takes his phone to the Caribbean and says "remind me at 10 AM," the brain will schedule it 10 AM Eastern instead of 10 AM local. **This is a v1.2 must-fix and not a hard refactor — wire `req.speaker_tz` through `now` and through every `ZoneInfo(...)` call in the router. Half a day of work.**

**(c) `ParsedIntent` has no `original_zone` or `at_speech_time` field.**
The phone sends `captured_at` (ISO8601 with offset) but the parsed intent loses provenance of *when* the utterance was captured. For "in 5 minutes" / "in an hour" relative parsing (not v1 but listed as future) this becomes important. Flag for v1.3.

**(d) `CalendarEvent` does not have an `acked_at` or `missed_at` field.**
The strike chain has nowhere to record completion in the event file itself. Today it would have to live in the reminder JSON sidecar, which is fine for v1.1 — but the moment `/ack` lands, the brain needs to update *something*. I'd rather it update the event frontmatter (`acked_at: <iso>`, `missed: false`) than the sidecar, because the markdown is the user-visible record. v1.2.

**(e) "Math never in the prompt" — is anything currently leaking?**
Audited. `SYSTEM_PROMPT` (llm.py:29) explicitly says "Do NOT compute the date — the caller does that" and "Do NOT convert to 24-hour." Good. The schema does not have a `start_datetime` field that the model could be tempted to fill with arithmetic. `duration_minutes` is the one numeric field, and that's fine — 30, 60, 90 are word-level extractions, not math. **Clean. No leak today.** Defend this when someone (probably Larry, with the best of intentions) proposes adding a `resolved_at` field to `ParsedIntent` for round-trip convenience. Say no.

**(f) Confidence levels collapse a useful gradient.**
`Confidence.HIGH/MEDIUM/LOW` is a coarse three-way. The router treats LOW as "drop to inbox" and HIGH/MEDIUM identically. That's fine for v1, but worth knowing: the model has more signal than the schema lets it express. For v1.3, consider a `float` confidence in `[0, 1]` and let the router use a threshold; for v1.2, leave it alone.

---

## 2. LLM prompt (`SYSTEM_PROMPT` in `llm.py:29-50`)

I'm reading this as `qwen2.5:7b` on a 16 GB Mac mini, cold-started, temperature 0.1, with the JSON schema constraint applied. A 7B model on a quiet machine, no warmup. Where does it wander?

### Conflicts within the rules

- **Rule 5** says "If you guessed at any field, list its name in `ambiguous_fields`." But **Rule 7** says "For `prompt_note`, put the full body the user dictated into `body` — the prompt and the answer they want to remember. If they only named the topic, leave `body` null." The two together imply that a null `body` is **not** a guess. A 7B model will not reliably make that distinction. It will read "if you guessed at any field, list it" and start including `body` in `ambiguous_fields` whenever it sets `body: null`, which is most of the time. That will trigger the router's clarifying-question branch and the user will get "what day and time?" for a prompt-note capture. **Fix:** add a rule "Only list fields in `ambiguous_fields` for calendar_event and calendar_query intents — never for note intents." Or, better, scope `ambiguous_fields` in the schema to a per-kind allow-list.

- **The 7B problem with "extract verbatim":** "Copy the day expression into `day_hint` exactly as the user said it ('Thursday', 'tomorrow', 'next Monday'). Do NOT compute the date" — a 7B model frequently *normalizes* on the way through. It will turn "thurs" into "Thursday" or "this thurs" into "Thursday". Mostly that's harmless (the date resolver normalizes anyway, see `_normalize` at date_resolver.py:46), but it means we can't trust `day_hint` to be the literal user words for the activity log. The activity log already preserves `raw_text` so this isn't a bug, but it's worth a comment for whoever next tunes the prompt.

### Missing: examples

There are zero in-prompt examples. For a 7B model doing structured output, **2-3 worked examples in the system prompt is worth more than ten more rules.** I'd add:
```
Examples (input → JSON):

"can we meet for coffee Thursday at 10?"
→ {"kind":"calendar_query","confidence":"medium","title":"coffee","day_hint":"Thursday","time_hint":"10","duration_minutes":null,"people":[],"tags":[],"raw_text":"can we meet for coffee Thursday at 10?","ambiguous_fields":["time"],"body":null}

"note that tool — Craftsman open-end wrench"
→ {"kind":"tool_note","confidence":"high","title":"Craftsman open-end wrench","day_hint":null,"time_hint":null,"duration_minutes":null,"people":[],"tags":["craftsman","wrench"],"raw_text":"note that tool — Craftsman open-end wrench","ambiguous_fields":[],"body":null}

"save this prompt about rendering rules — body: the prompt was X, the answer was Y"
→ {"kind":"prompt_note","confidence":"high","title":"rendering rules","day_hint":null,"time_hint":null,"duration_minutes":null,"people":[],"tags":[],"raw_text":"save this prompt about rendering rules — body: the prompt was X, the answer was Y","ambiguous_fields":[],"body":"the prompt was X, the answer was Y"}
```
The `ambiguous_fields:["time"]` in example #1 is deliberate — "10" without am/pm is exactly the case where the resolver flags time as ambiguous (regex matches "10" without an am/pm group). Showing the model that pattern is teaching it the contract.

### Missing: the "speaker_tz / now context" instruction

The prompt never tells the model what "today" or "tomorrow" is relative to. For a calendar_query like "what do I have today?" the model would set `day_hint: "today"` which is correct — but if the user says "what about the 15th?" with no month, the model has no anchor. We could include "Today is {YYYY-MM-DD}, {Weekday}" as a system-prompt prefix the brain fills in per request. That's a minor v1.2 tweak.

### Missing: the failure-mode instruction

There's no rule telling the model what to do when it really can't parse — "if you cannot identify any of the four kinds, emit `kind: unknown`, `confidence: low`, and copy the utterance into `raw_text`." It's implied by the "Use unknown and confidence: low if you cannot tell" line but not paired with the explicit fallback that lets the router drop to inbox cleanly.

### What I'd ship for v1.2 (without live-tuning)

- Add the three worked examples above.
- Scope `ambiguous_fields` to calendar intents only, in both prompt and schema (per-kind validation).
- Add the today-anchor line.
- Add a `Field` description to each Pydantic field so the JSON-schema export (which Ollama uses for grammar-constrained decoding) carries the descriptions through to the model. Today the schema is property-typed but description-less. Cheap to add, demonstrably helps small models.

**What I won't do until the model is running:** anything that requires reading actual failures. Live-tuning is a v1.2.1 task; the boss has to have Ollama up first.

---

## 3. The four endpoints Kit asked about

### `POST /ack`

**Shape:**
```http
POST /ack
{"event_id": "2026-06-12-coffee-with-jane", "kind": "strike_0", "acked_at": "2026-06-12T10:00:32-04:00"}

→ 200 OK
{
  "event_id": "2026-06-12-coffee-with-jane",
  "cancelled_kinds": ["strike_5", "strike_10", "strike_15"],
  "spoken_reply": null
}
```
**Behavior:** read the reminder sidecar at `_reminders/<event_id>.json`. Mark the acked row `status: acked`. Mark every later row in the same chain (any strike after the one that was acked) `status: cancelled`. Write the sidecar back atomically. Append an `event_ack` entry to the activity log. Return the kinds the brain just cancelled so the phone can remove them from `UNUserNotificationCenter` even if its local-cache disagreed with the brain's view.

**Edge cases:**
- Phone acks twice (duplicate POST) → idempotent, return the same `cancelled_kinds` (now empty because they're already cancelled).
- Phone acks a kind that doesn't exist in the sidecar → return 200 with empty `cancelled_kinds`. Don't 404; the phone may have a stale view, and 404 noise costs trust.
- Phone acks an event the brain doesn't know about (deleted on the brain side) → log it, return 200 with empty `cancelled_kinds`. The brain is the source of truth; the phone reconciles on next pull.

**Ship in v1.2.** This is the first thing the phone strictly needs after `/capture/text` and `/capture/confirm`. Without `/ack`, the strike chain runs to T+15 even when the user heard the first strike and tapped OK. That's a trust-fracture-grade behavior.

### `POST /undo`

**Shape:**
```http
POST /undo
{"event_id": "2026-06-12-coffee-with-jane"}

→ 200 OK
{
  "spoken_reply": "Undone — coffee with Jane on Friday June 12 at 10 AM is removed.",
  "removed_event_id": "2026-06-12-coffee-with-jane",
  "removed_paths": ["calendar/2026-06/2026-06-12-coffee-with-jane.md", "_reminders/2026-06-12-coffee-with-jane.json"]
}
```

**Behavior:** check the activity log for an `event_create` entry with this event_id whose `at` is within `reminder_undo_window_seconds` (300s = 5 min) of now. If yes: delete the calendar markdown file, delete the reminder sidecar, append `event_undo` to the activity log. If no (outside window, or never created): return `400 outside_undo_window` or `404 not_found` — and the phone speaks "I can only undo within five minutes."

**Voice command bound to this:** "undo that" or "scratch that," scoped to the *most recent* event the brain created. The phone doesn't need to know the event id — it can call `POST /undo` with no body and the brain picks the most recent event_create from the activity log that's within the window. That's a tighter UX. I'd add `POST /undo` with body optional.

**Ship in v1.2.** The boss greenlit this and it's small. ~half a day if `/ack` is already in.

### `GET /reminders/upcoming`

**Shape:**
```http
GET /reminders/upcoming?hours=72

→ 200 OK
[
  {
    "event_id": "2026-06-12-coffee-with-jane",
    "kind": "heads_up_30",
    "fire_at": "2026-06-12T09:30:00-04:00",
    "tz": "America/New_York",
    "body": "In 30 minutes: Coffee with Jane at 10:00 AM.",
    "status": "scheduled"
  },
  ...
  {
    "event_id": "summary-2026-06-12",
    "kind": "morning_summary",
    "fire_at": "2026-06-12T07:00:00-04:00",
    "tz": "America/New_York",
    "body": "Good morning. Today: 10:00 AM Coffee with Jane.",
    "status": "scheduled"
  }
]
```

**Behavior:** walk every event in the calendar between `now` and `now + hours`, build (or read) its reminder sidecar, filter rows whose `fire_at` is in `[now, now + hours]`, append the morning-summary row for every day in the window. Sort by `fire_at`. Return.

**Edge cases:**
- Already-fired strikes (acked or missed) → exclude. Status filter is `status in ("pending", "scheduled")`.
- An event whose sidecar doesn't exist (was hand-edited into existence) → generate the schedule on the fly. Don't persist on a read.
- Morning summaries need to be generated lazily here (because nobody is generating them today — see §6 below).

**Ship in v1.2.** Kit's spec is explicit that the phone polls this on launch, foreground, and after every capture. The "client-side shim" (derive the schedule on the phone from `/events`) is an unacceptable v1.0 corner-cut because it forces the strike-plan logic to live in two places and drift.

### `GET /activity`

**Shape:**
```http
GET /activity?n=50

→ 200 OK
[
  {"at":"2026-06-08T12:00:00-04:00","kind":"parse","event_id":null,"raw_text":"can we meet Thursday at 10","details":{"kind":"calendar_query","confidence":"medium","ambiguous_fields":[]}},
  {"at":"2026-06-08T12:00:01-04:00","kind":"event_create","event_id":"2026-06-12-coffee-with-jane","raw_text":"...","details":{...}},
  ...
]
```

**Behavior:** thin wrapper over `activity_log.tail(vault_path, n)`. Default `n=50`. Cap at `n=500`. No filter parameters in v1.2; if the phone wants to filter by kind or event_id, it does that client-side over the returned slice.

**Ship in v1.2.** Trivial to add (the JSONL machinery is already there). Powers Kit's debug `ActivityView` and gives the boss a "why did it think I said that?" answer when something parses wrong.

### Ordering recommendation

Land in this order for v1.2:
1. `GET /activity` — five lines, zero risk, gives the dev viewer immediately.
2. `GET /reminders/upcoming` — Kit's hard blocker. Pair with §6 (morning summary generation must happen here).
3. `POST /ack` — unblocks the strike chain trust.
4. `POST /undo` — boss's stated UX. Smallest of the four functionally; ships last only because the activity-log audit window must exist first.

All four are v1.2. None are v1.3+.

---

## 4. Date resolver (`date_resolver.py`)

### What it handles correctly

- `tzinfo` is enforced on `now` (date_resolver.py:63-64). Naive datetimes raise. Good.
- Today-named-weekday before/after noon rule (date_resolver.py:135-143) matches the Mori spec.
- "this Tuesday" vs "next Tuesday" — "next Tuesday" when said on Monday correctly rolls a week-and-a-day (date_resolver.py:144-147).
- ISO absolute date `2026-07-04` works (date_resolver.py:215).
- `month-day` absolute like `July 4` works, with a "more than 30 days in the past → assume next year" rule (date_resolver.py:228-230). Sensible heuristic.

### Gaps

**(a) DST transitions — no test coverage.**
The resolver builds datetimes via `datetime.combine(date, time, tzinfo=tz)`. On the DST-skipped hour (March 8 2026, 2 AM Eastern → 3 AM), `datetime(2026, 3, 8, 2, 30, tzinfo=ZoneInfo("America/New_York"))` is a non-existent local time. `zoneinfo` resolves it as the second 2:30 (folded back into ST) which is *not* what the user means if they say "set a meeting at 2:30 AM on March 8" (rare but real, e.g. travelers). On the fall-back hour (November 1 2026, 2 AM EDT → 1 AM EST), "1:30 AM" is ambiguous (it happens twice). The resolver silently picks one and moves on. **Add tests for both DST weekends in 2026 and 2027. Decide policy: ambiguous DST → `ambiguous_fields: ["dst"]` and clarifying question, or default to the first occurrence and log it.** Persona rule: DST weekend is an RC blocker. This is currently uncovered.

**(b) Leap years.**
Feb 29 absolute — `_try_absolute_date("february 29", now_in_2027)` will construct `datetime(2027, 2, 29).date()` and raise `ValueError`. The resolver does not catch it and the error propagates up. Test missing. Fix: try/except around the `datetime(...).date()` calls in `_try_absolute_date` and return `(None, True, "invalid date")`.

**(c) "this/next" said exactly at a weekday boundary.**
Persona example: "this Tuesday" said on Tuesday at exactly 11:59 AM (stays today) versus 12:00 PM (rolls to next Tuesday). The current rule is `if now_local.hour >= 12` which works at minute-level precision. The off-by-one at noon is harmless; the off-by-one at `now_local.hour == 12` is the cliff edge — a user saying "this Tuesday" at noon exactly gets next Tuesday. That's the spec, so it's fine, but worth a comment so the next person doesn't "fix" it.

**(d) "the 15th" without a month name.**
Not supported. The `_try_absolute_date` regex requires `^([a-z]+)\s+(\d{1,2})$` (a word *and* a number). A bare "the 15th" or "the 15" or "fifteenth" falls through to "could not parse day." For an older user this is a natural phrasing and we should support it. **Behavior I'd add:** "the Nth" or "N" (1–31), interpret as "the next occurrence of day-of-month N in the future." If today is the 8th, "the 15th" → this month's 15th. If today is the 20th, "the 15th" → next month's 15th. v1.2 nice-to-have.

**(e) "in 5 minutes" / "in an hour" / "in 30."**
Not supported. Out of scope for v1 per the locked memory? Not explicit. The persona's daily-workflow §2.5 reference to "deterministic resolution from a configurable morning anchor" suggests relative durations are in scope. For v1.2 I'd add a `duration_hint` field on the schema and a `_resolve_relative` branch in the resolver. Flag for v1.2.

**(f) Time regex doesn't accept "10 o'clock."**
`_TIME_REGEX` expects `<digit>[:<digit>][am|pm]`. "10 o'clock" or "ten o'clock" fall through. The 7B model will probably normalize "ten o'clock" → "10" so the schema-level form is mostly fine, but the heuristic fallback will miss it. v1.3.

### What I'd ship for v1.2

Tests for DST weekends, leap year, "the 15th" parsing. Maybe the "in 30 minutes" branch. The corner cases above are flags, not fixes — and the persona is explicit that DST is an RC blocker, so v1.2 tests must include forced-DST cases.

---

## 5. Calendar conflicts (`calendar.check_conflicts`)

The fuzz check at calendar.py:120-123 compares all four edges:
```python
edges_existing = (e.starts_at, e.ends_at)
edges_proposed = (starts_at, ends_at)
if any(abs(a - b) <= fuzz for a in edges_existing for b in edges_proposed):
    fuzzy.append(e)
```

### Where this over-flags

**Back-to-back events at 0 minutes apart.** Existing event ends at 10:00; proposed starts at 10:00 (and ends at 10:30). Are these a direct conflict?
- Direct check: `e.starts_at < ends_at and e.ends_at > starts_at` → `9:30 < 10:30 ✓ AND 10:00 > 10:00 ✗` → NO direct conflict. Half-open intervals: ends-at is exclusive. Correct.
- Fuzzy check: `abs(10:00 - 10:00) = 0 ≤ 30` → YES fuzzy conflict.

So back-to-back events are flagged as fuzzy. **Is that intent?** The persona suggests yes — "ends 15 min before this starts" is the case the comment cites and back-to-back is the limit of that case. The boss is older; he probably *does* want a heads-up that the next thing starts the moment the current one ends. **I'd keep this behavior and add a unit test that pins it down.** The risk is that a sequence of back-to-back-to-back errands ("pharmacy 9-9:30, then bank 9:30-10, then post office 10-10:30") would have every event flag every adjacent event as fuzzy, which floods the readback. **Mitigation:** the readback only mentions the *first* conflict, so the user gets one flag not three. Acceptable.

### Where this under-flags

**An existing event far from the proposed event but happening to fall on the same day, when the user said only a day hint.** Not under-flagged today because we don't fuzz at the day level — we fuzz on the proposed event's *resolved* edges. Good.

**A long meeting (4 hours) and a proposed 30-minute event 28 minutes after it ends.** Direct: no. Fuzzy: `abs(meeting_end - proposed_start) = 28 ≤ 30` → flagged. Good.

**Two events whose edges are all > 30 min apart but the intervals overlap.** Can't happen: if the intervals overlap, edges-to-edges has at least one pair at distance 0 (because they overlap). Direct catches it first.

### My take

The fuzz logic is correct. The back-to-back-as-fuzzy behavior is a *product* decision worth pinning down in a test and noting in the readback copy ("right after your previous thing" vs "near another event"). v1.2 polish, not a v1.1 bug.

### One real bug worth flagging

`list_events` reads every markdown file in `vault/calendar/**/*.md` on every conflict check (calendar.py:81-90, called from check_conflicts:111). For a vault with 200 events this is two hundred YAML parses per `/capture/text`. The persona's stance is "no cache that survives process death" — but an in-process mtime-keyed cache is allowed and explicitly listed in §2.4 of the hiring research as a v1.1 optimization. **Not v1.2 priority** (the brain is single-user with maybe a dozen events at first), but worth a note for the day the vault crosses ~100 events.

---

## 6. Morning summary — nothing is generating it (`reminders.build_morning_summary`)

**Confirmed:** `build_morning_summary` exists (reminders.py:83-108) and `_compose_summary_body` exists (reminders.py:111-121) and they have tests (tests/test_reminders.py:60-83) — but **nothing in the codebase calls them**. Grepping the source:

- `intent_router.commit_calendar_event` calls `build_event_schedule` and `persist_event_schedule` and `push_to_phone` — never the summary builder.
- There is no scheduled job, no cron, no daily-tick handler in `server.py`.
- The persona's locked rule (#7): "morning summary at user-configured time, T-30 heads-up, T-5 pre, then strikes" — the morning summary half of that chain is **latent code, not running code.**

This is the riskiest gap in the v1.1 codebase for end-user trust. (See §8 for why.)

### What to do

Two options for v1.2.

**Option A (preferred — pull model):** generate the morning summary on demand inside `/reminders/upcoming`. Walk events for each day in the window, build the summary row for each day at the configured local time, return it alongside the strikes. The phone registers it like any other `UNCalendarNotificationTrigger`. **The brain has no scheduler — the phone is the scheduler.** This is consistent with the v1.0 design (Mac pushes a schedule, phone fires it locally). Half a day of work in `/reminders/upcoming`.

**Option B (rejected for v1.2):** add a background `asyncio` task in the brain that ticks at midnight local and persists the day's summary sidecar. This adds a long-running task to the FastAPI process and a recovery problem if the brain restarts mid-day. Persona rule #6 ("one model resident, don't swap") generalizes: keep the brain's runtime simple. Don't add a scheduler unless you have to.

Option A. Ship in v1.2 alongside `/reminders/upcoming`.

---

## 7. Testing gaps

51 unit tests is a solid foundation. The gap is **integration coverage of the one user journey that matters.**

### What's well-covered

- Date resolution (10 tests).
- Calendar conflicts (5 tests).
- Vault round-trips and slugs (7 tests).
- Heuristic parser per intent (6 tests).
- Reminder generation (6 tests).
- Activity log (5 tests).
- Prompt-note body persistence (2 tests).
- Intent router individual branches (6 tests).

### What's missing

**No end-to-end test that exercises `POST /capture/text → confirm → write → read events back → register reminders → ack → verify cancellation.**

Sketch I'd add as `tests/test_capture_lifecycle.py`:
```python
@pytest.mark.asyncio
async def test_calendar_event_full_lifecycle(tmp_path, monkeypatch):
    # Hermetic config pointing at tmp_path. Force heuristic mode by setting
    # OLLAMA_BASE_URL to an unreachable host.
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")  # connection refused
    app = create_app()
    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        # 1) Capture
        r = await c.post("/capture/text", json={"text": "add a meeting with Jane Thursday at 2pm"})
        assert r.json()["action"] == "needs_confirmation"
        intent = r.json()["intent"]  # echo back — see schema gap (e) below

        # 2) Confirm
        r = await c.post("/capture/confirm", json={"intent": intent})
        assert r.json()["action"] == "wrote"
        event_id = r.json()["event_id"]

        # 3) Read events back
        r = await c.get("/events?day=2026-06-11")
        assert any(e["title"].startswith("meeting") for e in r.json())

        # 4) Reminders sidecar exists
        assert (tmp_path / "_reminders" / f"{event_id}.json").exists()

        # 5) /ack cancels remaining strikes (when /ack lands)
        # 6) Activity log has parse + event_create entries (when /activity lands)
```

Schema gap (e): `CaptureResponse` doesn't currently echo the parsed intent back to the phone, so the confirm step has nowhere to get the intent from. Today the phone has to keep the intent client-side from the first response — which the iOS spec acknowledges in passing. Fix: add `parsed_intent: Optional[ParsedIntent]` to `CaptureResponse`. v1.2.

Beyond this lifecycle test:
- **Concurrent capture test** — two simultaneous `/capture/text` posts targeting the same minute, assert no inbox corruption and no duplicate event. (See §8 for why this matters.)
- **DST test for `commit_calendar_event`** — capture "Sunday at 10am" on a DST-transition Sunday and assert the resulting `starts_at` is the right wall-clock.
- **Markdown hand-edit test** — write an event file directly to the filesystem with a frontmatter change, assert `list_events` reflects it on the next call.

### What I'd ship for v1.2

The lifecycle test above (~half a day). Concurrent capture test (~half a day, requires fixing the inbox lock first — see §8). DST tests (a couple hours). The hand-edit test is small.

---

## 8. The riskiest thing in the codebase

**The inbox file is appended without a lock, the calendar markdown is written without atomic write-rename, the reminder sidecar is written without atomic write-rename, and there is no morning summary actually firing in the schedule.** The trust contract the persona signs in blood — "morning summary → T-30 → T-5 → four strikes → missed log → next-morning reschedule offer" — has two broken links at once: the *first* link (morning summary) is latent code, and the *last* link (missed log re-surfacing tomorrow) inherits the same gap. Concurrently, two captures landing within the same millisecond can corrupt the inbox file because `vault.append_inbox` (vault.py:145-161) opens the file in append mode without any `asyncio.Lock` and without atomic write-rename — and `vault.write_markdown` (vault.py:55-64) writes directly to the target path with `path.write_text(...)` rather than to a `.tmp` and renaming, so a crash mid-write leaves a truncated file. None of these are theoretical; the boss is one moment away from rapid-fire-capturing twice in succession, and a Mac mini that loses power during a write will leave a corrupted markdown file in the vault that `list_events` will then silently skip via the bare `except Exception` at calendar.py:87-89. The product's whole reason for existing — "I forgot, the brain will remember" — sits on top of a vault that is not currently crash-safe. **This is the v1.2 must-fix above all others. `asyncio.Lock` on the inbox, atomic write-rename on every `write_markdown` and every sidecar write, and don't silence parsing errors — log them loudly and surface them in `/activity`.**

---

## Prioritized punch-list

### Must do before v1.2 ships (5)

1. **Atomic write-rename in `vault.write_markdown` and `vault.write_reminder_schedule`.** Write to `<file>.tmp`, fsync, rename. Persona rule #9. (~half a day)
2. **`asyncio.Lock` (or per-file lock) around the inbox append and the activity-log append.** Persona rule #6. (~half a day)
3. **Wire `req.speaker_tz` through to the router and the date resolver.** Today it's ignored; the persona's TZ rule is currently violated. (~half a day)
4. **Generate the morning summary as part of `/reminders/upcoming`.** Option A in §6. The reliability chain is incomplete without it. (~half a day; pairs with item 5 below)
5. **Surface the four endpoints in the order recommended in §3** — `/activity` (trivial), `/reminders/upcoming` (pairs with morning summary), `/ack`, `/undo`. (~2-3 days total)

### Should do for v1.2 (6)

6. **Echo the parsed intent back in `CaptureResponse`** so the confirm round-trip is symmetric. Schema field `parsed_intent: Optional[ParsedIntent]`. (~1 hour)
7. **DST tests in the date resolver** (forced spring-forward and fall-back). Decide on the ambiguous-hour policy and pin it down. (~half a day)
8. **Leap-year safety in `_try_absolute_date`.** Try/except around `datetime(year, month, day).date()`. (~30 minutes)
9. **End-to-end lifecycle test** (sketch in §7). Run in heuristic mode, no Ollama required. (~half a day)
10. **Prompt examples in `SYSTEM_PROMPT`** plus the `ambiguous_fields` scoping fix. Don't tune against a live model yet — these are paper improvements. (~1 hour)
11. **Pydantic `Field(description=...)` on every field in `ParsedIntent`** so the JSON-schema export carries descriptions through to Ollama's GBNF grammar. Demonstrably helps small models. (~30 minutes)

### v1.3 and later (5)

12. **Richer `ambiguous_fields` shape** with per-field reasons and candidate values (§1a). Requires `PROTOCOL.md` change + Kit review.
13. **"the 15th" and "in 30 minutes" date parsing** (§4d, §4e).
14. **`acked_at` / `missed_at` in `CalendarEvent` frontmatter** so the markdown record is the user-visible truth about completion (§1d).
15. **Mtime-keyed in-process cache for `list_events`** when the vault crosses ~100 events (§5 close).
16. **Float confidence in `ParsedIntent`** (§1f). Bigger change; requires Kit review.

---

## Process notes

- No code was changed. No version was bumped. No prompt was tuned against a live model. 51 tests still pass.
- I've added zero design-version churn — Larry to bump after Thomas reads.
- The `PROTOCOL.md` artifact called for in my persona doesn't exist yet. That's a v1.2 deliverable; I'll author it once the four new endpoints are designed against Kit's review, not before.
- Activity-log JSONL is in the right shape and the tail/iter helpers are clean. When `/activity` lands, the HTTP surface is five lines.

---

*Rune — fresh eyes, kept hands off the code.*
