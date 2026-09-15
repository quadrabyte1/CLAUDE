"""
mac_calendar_bridge — Push Herman vault events to macOS Calendar.app.

Version 0.1.5  (belt-and-suspenders dup-prevention: query_pushed_event_ids()
wired into push_if_new(); push_event uses url-in-make-properties to prevent
silent Calendar.app event rollback on Sep 18 Friday event)
"""

VERSION = "0.1.5"
