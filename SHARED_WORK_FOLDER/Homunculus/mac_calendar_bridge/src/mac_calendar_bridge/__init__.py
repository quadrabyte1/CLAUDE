"""
mac_calendar_bridge — Push Herman vault events to macOS Calendar.app.

Version 0.1.2  (remove invalid `tell account` — Calendar.app has no account
concept in AppleScript; bridge now uses verify_calendar_exists() at startup
and requires the user to create the "Homunculus" calendar manually in iCloud)
"""

VERSION = "0.1.2"
