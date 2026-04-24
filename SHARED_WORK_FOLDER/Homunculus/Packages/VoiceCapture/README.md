# VoiceCapture

**Owner:** Mori. **Milestone:** M2.

## Responsibility

The microphone-to-mouth loop. Everything between the user pressing Talk and the raw
transcription string + spoken-readback surface.

- `AVAudioSession` configuration (`.playAndRecord` + `.duckOthers` + `.allowBluetooth`),
  single activation pattern, teardown with `.notifyOthersOnDeactivation`.
- `SpeechAnalyzer` + `SpeechTranscriber` + `SpeechDetector` push-to-talk capture.
- `contextualStrings` seeded from recent event titles + known participant names
  (pulled from `CalendarCore`).
- `AVSpeechSynthesizer` playback with premium Siri voice.
- Barge-in: the Talk button stops synthesis before starting capture; never layer audio
  sessions.
- Permission prompting for mic + speech recognition at the first Talk tap — not at launch.

## Boundary

- **Consumes:** `CalendarCore` (read-only; recent titles/names for contextual biasing).
- **Does not consume:** NLU, Scheduling, NotificationsKit, AppShell.
- **Is consumed by:** AppShell, NLU (via a transcription stream).

## Non-goals

- No NLP. Raw transcription out, that's it.
- No database writes. Never.
- No notification scheduling.
- No view code (Kit owns the Talk button UI; this module exposes the engine behind it).
