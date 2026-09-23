"""
mac_notifier — Mac notification poller for Herman/Homunculus.

Polls Herman's /reminders/upcoming endpoint and fires macOS notifications
when scheduled reminder rows come due.

v0.2.0 — 2026-09-22 — Rune
  - NOTIFIER_GRACE_WINDOW default raised from 90 → 300 (5 minutes).
    Rationale: poll interval is 60s; a notification queued in the wrong
    second-of-minute slot can drift past a 90s grace. 300s gives 5 minutes
    of tolerance. timer_stop notifications missing by 9s (99s > 90s grace)
    will now fire correctly. Env-var override preserved.
  - Plist updated to explicitly set NOTIFIER_GRACE_WINDOW=300.

v0.1.0 — 2026-09-15 — Rune
  Initial release.
"""

VERSION = "0.2.0"
