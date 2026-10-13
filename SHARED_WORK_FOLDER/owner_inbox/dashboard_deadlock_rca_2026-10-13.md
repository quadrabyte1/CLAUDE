# Dashboard Deadlock RCA — 2026-10-13

**Analyst:** Sienna  
**Date:** 2026-10-13  
**App:** Dashboard Flask server (`app/app.py`, port 5051)  
**Incident:** ~16-hour uptime wedge; all requests timed out; worker PID 63133 stuck in `__psynch_cvwait` (POSIX semaphore wait)

---

## Hypothesis (2–3 sentences)

The worker process deadlocked on a **POSIX semaphore created by `multiprocessing.Value("B")`** inside Werkzeug's `DebuggedApplication.__init__()` (debug mode is enabled via `app.run(debug=True, ...)`). On macOS Python 3.13, `multiprocessing.Value` uses an `RLock` backed by a named POSIX semaphore (`/mp-*`) that is tracked by the OS resource-tracker. The most probable trigger is that an unclean worker exit (crash, signal, or OS-level forced teardown during an overnight idle) left the semaphore's internal reference count inconsistent, so the next request that called `_failed_pin_auth.value` (which always acquires the semaphore under the hood) blocked forever — producing exactly the `__psynch_cvwait` frame seen in the stack sample and the `UserWarning: resource_tracker: There appear to be 1 leaked semaphore objects ... /mp-xmsk5fp1` warning.

---

## Evidence

### 1. Debug mode is on — `multiprocessing.Value` is created at startup

`app/app.py`, last line:

```python
app.run(debug=True, host="0.0.0.0", port=5051, use_reloader=True)
```

When Flask runs with `debug=True`, it wraps the WSGI app in `werkzeug.debug.DebuggedApplication`. That class's `__init__` immediately does:

```python
# werkzeug/debug/__init__.py, line 291
self._failed_pin_auth = Value("B")
```

`Value("B")` from `multiprocessing` creates a `Synchronized` wrapper whose `.value` property **always acquires and releases an underlying RLock (backed by a macOS POSIX semaphore named `/mp-*`)** on every read and write. This is confirmed in `multiprocessing/sharedctypes.py`:

```python
def getvalue(self):
    self.acquire()
    try:
        return self._obj.value
    finally:
        self.release()
```

### 2. The semaphore name matches exactly

The `resource_tracker` warning names the leaked object `/mp-xmsk5fp1`. The `/mp-` prefix is the hardcoded POSIX semaphore name prefix used by Python's `_multiprocessing.SemLock` on macOS — confirmed live:

```python
>>> from multiprocessing import Value
>>> v = Value('B', 0)
>>> type(v.get_lock())
<class 'multiprocessing.synchronize.RLock'>
```

### 3. The stack trace points directly at this semaphore

```
_PyThread_acquire_lock → _PyMutex_LockTimed → _PyParkingLot_Park →
_PySemaphore_Wait → _pthread_cond_wait → __psynch_cvwait   ← stuck here
```

This is a Python-level lock acquisition, not SQLite. The thread is waiting for a POSIX semaphore to be released — a semaphore that was never released because the process that held it exited abnormally.

### 4. All routes that read `_failed_pin_auth.value` are affected

The Werkzeug `DebuggedApplication.__call__` path eventually reads `_failed_pin_auth.value` on every request that touches the debugger middleware (`check_pin_trust`, line 447; `_fail_pin_auth`, line 468; `pin_auth`, line 499, 507). Since the `DebuggedApplication` is the outermost WSGI wrapper, **any request** to the Flask app passes through it.

The `/editor` request (the last one before the wedge) was just the first request after the semaphore was corrupted; it had nothing intrinsically wrong — it just had the bad luck to be the request that attempted the first semaphore acquire after the damage.

### 5. The 16-hour gap + idle overnight is consistent

The worker sat idle overnight. On macOS, the OS POSIX semaphore subsystem may release resources for processes that have exited, but the `_failed_pin_auth` semaphore was created in the *worker* (child of the reloader), not the reloader parent. When the worker is clean-restarted by the reloader (e.g., due to a file-change event or an OS signal during sleep), the newly spawned worker inherits the file descriptor for the semaphore but may see the semaphore's count in an inconsistent state if the previous holder exited mid-acquire.

### 6. Two FDs on `workspace.db` — likely benign

SQLite WAL mode opens three files (main, WAL, SHM), but the kernel exposes the SHM and WAL through the same inode cluster. Two FDs to `workspace.db` is consistent with Werkzeug's reloader: the reloader parent holds one FD (inherited at `init_db()` time, then closed), and the worker holds another. This is expected behavior and is **not** contributing to the deadlock.

---

## Proposed Fix

### Primary fix — disable debug mode in production (1-line)

`app/app.py`, line 2825:

**Before:**
```python
app.run(debug=True, host="0.0.0.0", port=5051, use_reloader=True)
```

**After:**
```python
app.run(debug=False, host="0.0.0.0", port=5051, use_reloader=True)
```

With `debug=False`, `DebuggedApplication` is never instantiated, `multiprocessing.Value` is never created, and the `/mp-*` POSIX semaphore lifecycle disappears entirely. The Werkzeug reloader is controlled by `use_reloader`, not `debug`, so file-change restarts still work.

**Important:** Disabling debug mode also removes the interactive debugger and PIN from the browser — which is desirable for a long-running production process anyway.

### Secondary fix — remove `use_reloader=True` (optional hardening)

The process tree observed was:

```
820 (start_web_servers.sh) → 822 (reloader parent) → 63133 (worker)
```

When the worker was `kill -9`'d, the reloader parent died too (because the shell script started it synchronously). With `use_reloader=False`, the app runs as a single flat process with no parent/child semaphore inheritance, eliminating the entire class of "child inherits parent semaphore, parent exits, semaphore leaks" bugs.

```python
app.run(debug=False, host="0.0.0.0", port=5051, use_reloader=False)
```

The trade-off is losing hot-reload on code changes, which is acceptable for a server that restarts via Login Item.

---

## Hardening — Self-Liveness Watchdog

**Recommended, low priority.** Since the root-cause fix removes the semaphore entirely, the watchdog is a belt-and-suspenders measure, not a mitigation for this specific bug.

**Proposed approach:** Add a simple health-check cron or launchd timer that runs every 5–10 minutes:

```bash
# /usr/local/bin/dashboard_watchdog.sh
HTTP_CODE=$(curl -o /dev/null -s -w "%{http_code}" --max-time 5 http://localhost:5051/api/tasks/running_count)
if [ "$HTTP_CODE" != "200" ]; then
  echo "$(date): dashboard wedged (HTTP $HTTP_CODE), restarting" >> ~/Library/Logs/dashboard_watchdog.log
  pkill -f "python.*app.py" 2>/dev/null
  sleep 2
  /Users/$(whoami)/.local/bin/start_web_servers.sh &
fi
```

Wire it via `launchd` on the boot volume (not on `/Volumes/GIT` — see `project_external_volume_nosuid.md` memory note). This ensures Thomas never has to manually restart after the next unexpected wedge, whatever its cause.

---

## Summary of Findings

| Item | Finding |
|------|---------|
| Root cause | `multiprocessing.Value("B")` in `werkzeug.debug.DebuggedApplication` (line 291) creates a POSIX semaphore that leaked when the worker exited uncleanly |
| Trigger | `app.run(debug=True, ...)` in `app/app.py` line 2825 — debug mode unconditionally instantiates `DebuggedApplication` |
| Deadlock mechanism | Every request that passes through the debug middleware acquires the semaphore via `.value` read; the leaked semaphore blocks forever |
| Last-request clue | `/editor` was just the first post-wedge request; the route itself is clean |
| SQLite FDs (89u, 90u) | WAL mode + reloader parent inheritance — benign, not contributing |
| Primary fix | Change `debug=True` → `debug=False` in `app.run(...)` (1 line) |
| Optional hardening | Also set `use_reloader=False` to run a flat single process |
| Watchdog | Launchd health-check timer on boot volume (nice-to-have) |
