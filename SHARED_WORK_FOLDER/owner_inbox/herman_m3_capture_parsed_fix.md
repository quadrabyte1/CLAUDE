# Herman v1.3.1 — 2026-09-13 — Rune
## M3 Handoff: `/capture/parsed` date-hint fix

---

## What shipped

Herman v1.3.1 closes the two-facet bug in `/capture/parsed` that meant Sprite could never safely forward a relative day/time from its Ollama parse to Herman. All Herman tests green (118). All Sprite tests green (91).

---

## The bug (two facets)

**Facet 1 — Wire-level.** `ParsedCaptureRequest.when` was typed `Optional[datetime]`. If Sprite sent `"thursday"` in that field, Pydantic rejected it with a 400 before any handler ran. The docstring even said "Herman's date_resolver handles it" — but that was a lie; the schema prevented any non-ISO string from reaching Herman at all.

**Facet 2 — Handler-level.** Even if `when` arrived as a valid ISO-8601 datetime, `/capture/parsed` bypassed `date_resolver.py` entirely. The `_handle_schedule` and `_handle_handle` functions used `req.when` directly and fell back to `_next_business_morning` when it was None. The authoritative resolver that `/capture/text` relies on was never called on this path.

---

## The fix

### Schema (`schemas.py`)

Added two additive optional fields to `ParsedCaptureRequest`:

```python
day_hint: Optional[str] = None   # e.g. "thursday", "tomorrow", "next monday"
time_hint: Optional[str] = None  # e.g. "9am", "2:30 PM", "morning"
```

`when: Optional[datetime] = None` stays exactly as-is. Callers that have already resolved a datetime pass it there. Callers that want Herman's resolver to do the math pass hints and leave `when=None`. Explicit `when` always wins if both are present.

`ParsedCaptureResponse` gained two optional clarification fields (matching the `/capture/text` shape so clients implement one branch):

```python
clarifying_question: Optional[str] = None
ambiguous_fields: list[str] = Field(default_factory=list)
```

### Handlers (`capture_parsed.py`)

`_handle_schedule` and `_handle_handle` both now follow this precedence:

1. `when` is set → `_ensure_tz(req.when, tz)` — existing behavior, untouched.
2. `day_hint` or `time_hint` is present → call `date_resolver.resolve()` via the new `_resolve_from_hints` helper.
   - If resolver returns a non-empty `ambiguous` list → return `ParsedCaptureResponse(stored=False, clarifying_question=..., ambiguous_fields=...)` immediately, without touching the vault.
   - If resolver succeeds → use `resolved_at` as the event time.
3. Neither → fall back to `_next_business_morning` (existing behavior, untouched).

`dispatch()` gained a guard: when `resp.stored is False`, skip `_record_stored` and the activity log. A clarification response is not a committed record.

`compute_record_id()` was updated: when `when is None`, the key uses `day_hint@time_hint` so two records with different hints hash to different ids.

### Sprite (`herman.py`)

`build_request()` accepts `day_hint: Optional[str] = None` and `time_hint: Optional[str] = None`. They are included in the payload only when non-None (clean wire — no null keys).

---

## Red → green story

**Red state (before implementation):**

```
FAILED test_schedule_with_day_and_time_hints_creates_event_at_correct_time
  → stored=True but event landed on 2026-09-16 (next business day default),
    not 2026-09-17 (Thursday). Hints ignored.
FAILED test_handle_with_day_and_time_hints_creates_reminder_at_correct_time
  → Same root cause — handle handler also fell through to _next_business_morning.
FAILED test_ambiguous_time_hint_returns_stored_false_with_clarifying_question
  → Request returned stored=True (wrong date), no clarifying_question key.
FAILED test_ambiguous_day_hint_returns_stored_false_with_clarifying_question
  → Same.
FAILED test_hint_fields_round_trip_through_pydantic_model
  → ParsedCaptureRequest had no day_hint/time_hint fields; AttributeError.

5 failed, 26 passed  (22 original + 4 new tests that already passed)
```

**Green state (after implementation):**

```
31 passed  (Herman test_capture_parsed.py)
118 passed (full Herman suite)
91 passed  (full Sprite suite)
```

The 5 previously-failing tests now pass. All 22 original tests pass unchanged (regression confirmed).

---

## Wire-shape summary

`ParsedCaptureRequest` (Herman v1.3.1):

| Field | Type | Notes |
|---|---|---|
| `verb` | `CaptureVerb` | required |
| `subject` | `str` | required, min_length=1 |
| `when` | `Optional[datetime]` | ISO-8601 or null — resolved datetime wins |
| `day_hint` | `Optional[str]` | **new v1.3.1** — e.g. "thursday" |
| `time_hint` | `Optional[str]` | **new v1.3.1** — e.g. "9am" |
| `criticality` | `CaptureCriticality` | default normal |
| `confidence` | `float [0,1]` | required |
| `raw_transcript` | `str` | required |
| `audio_path` | `str` | required |
| `captured_at` | `datetime` | required |

`ParsedCaptureResponse` (Herman v1.3.1):

| Field | Type | Notes |
|---|---|---|
| `stored` | `bool` | False when clarification needed |
| `record_id` | `str` | stable 32-char hex key |
| `verb` | `CaptureVerb` | echoed |
| `written_path` | `Optional[str]` | vault-relative when stored |
| `event_id` | `Optional[str]` | for schedule/handle when stored |
| `clarifying_question` | `Optional[str]` | **new v1.3.1** — only when stored=False |
| `ambiguous_fields` | `list[str]` | **new v1.3.1** — e.g. `["time"]` |

Cross-repo round-trip test in `Sprite/tests/test_herman_client.py::test_wire_shape_day_and_time_hints_round_trip` confirms `build_request()` output validates through `ParsedCaptureRequest.model_validate_json()`.

---

## Files changed

- `Homunculus/brain/homunculus_brain/schemas.py` — additive fields on `ParsedCaptureRequest` and `ParsedCaptureResponse`
- `Homunculus/brain/homunculus_brain/capture_parsed.py` — `_resolve_from_hints` helper, updated `_handle_schedule`, `_handle_handle`, `dispatch`, `compute_record_id`; added `date_resolver` import
- `Homunculus/brain/homunculus_brain/__init__.py` — VERSION 1.3.0 → 1.3.1
- `Homunculus/brain/pyproject.toml` — version 1.3.0 → 1.3.1
- `Homunculus/brain/tests/test_capture_parsed.py` — 9 new M3 tests (6 behavioral, 1 wire-shape round-trip, 2 regressions explicitly asserted)
- `Sprite/src/sprite/herman.py` — `build_request()` accepts `day_hint` / `time_hint`; updated wire contract docstring
- `Sprite/tests/test_herman_client.py` — 5 new tests (hint field coverage + cross-repo round-trips)

---

## What M4 should be

1. **Sprite parse layer** — `Sprite/src/sprite/parse.py` currently produces a dict from the Ollama response. It should be updated to emit `day_hint`/`time_hint` from the parsed intent instead of trying to forward a resolved `when` string. That's the last link in the chain that still does partial date work on the wrong side.

2. **Clarification round-trip** — When Herman returns `stored=False` + `clarifying_question`, Sprite needs to surface the question to the user (via Herman's TTS path or a Kit notification) and re-POST with a resolved `when` after the user responds. The protocol shape is defined; the round-trip handler in Sprite is the open work.

3. **`avoid` and `note` verbs with hints** — M3 only wires hints for `schedule` and `handle` (the verbs with a temporal dimension). `avoid` and `note` don't use `when` at all, so hints are irrelevant there. M4 should verify that explicitly and close any doc gaps in `PROTOCOL.md`.

4. **Kit alignment** — Update `PROTOCOL.md` with the v1.3.1 wire shape. Kit needs to know about `day_hint`/`time_hint` for the future iOS mic-capture path, and needs the `clarifying_question`/`ambiguous_fields` response fields to implement the clarification UI branch. This is a PR-review item per the ownership split.
