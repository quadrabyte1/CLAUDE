"""
mac_notifier — Mac notification poller for Herman/Homunculus.

Polls Herman's /reminders/upcoming endpoint and fires macOS notifications
when scheduled reminder rows come due.

v0.3.0 — 2026-09-27 — Rune
  - Bundle-first notification path via mac_notifier.bundle.
    Notifications now show as "Homunculus Notifier" (bundle ID
    com.homunculus.notifier) instead of "Script Editor".
  - Two dispatch paths: terminal-notifier (if installed) → Swift stub
    inside the .app bundle (preferred); osascript legacy fallback when
    bundle is absent.
  - fire_notification_with_fallback() in applescript.py is the new call
    site. poller.py updated to use it.
  - deploy/install_bundle.sh builds and installs the .app bundle.
  - deploy/notifier_stub/notifier.swift — minimal Swift CLI stub using
    UserNotifications framework (macOS 12+, Swift 5.5+).
  - deploy/notifier_stub/Info.plist — bundle metadata with correct ID.
  - 23 new tests: test_bundle.py (16) + test_applescript_v03.py (7).
    Total suite: 151 tests, all passing.
  - No Herman/Sprite/brain changes.

v0.2.0 — 2026-09-22 — Rune
  - NOTIFIER_GRACE_WINDOW default raised from 90 → 300 (5 minutes).

v0.1.0 — 2026-09-15 — Rune
  Initial release.
"""

VERSION = "0.3.0"
