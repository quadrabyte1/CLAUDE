# NLU

**Owner:** Mori. **Milestone:** M2.

## Responsibility

Turn a raw transcription string into a typed `ParsedSchedulingIntent`, using Apple's
on-device Foundation Models with `@Generable` guided generation.

- `@Generable` Swift types (schema-first; prompt is the second artifact).
- Prompt authoring and tuning for the on-device ~3B model.
- Deterministic date/time resolution **in Swift, not in the prompt** —
  "Tuesday", "tomorrow morning", "in 30 minutes" all land in a pure, testable function
  that takes `(relativeDayHint, relativeTimeHint, startLocal, now, userTZ, morningAnchorHour)`.
- `ambiguousFields` is the most important output — non-empty means the UI must ask.
- Multi-step utterance detection — refuse politely, ask for one-at-a-time rephrasing.
- **No cloud fallback. Ever. In v1.**

## Boundary

- **Consumes:** `CalendarCore` (settings + TZ helpers).
- **Does not consume:** VoiceCapture, Scheduling, NotificationsKit, AppShell.
- **Is consumed by:** AppShell (via a parse coordinator).

## Non-goals

- No STT. Strings come in; intents go out.
- No confirmation UI. That's AppShell.
- No database writes. AppShell + CalendarCore handle that on confirm.
- No Claude or other cloud LLM code paths — by design.
