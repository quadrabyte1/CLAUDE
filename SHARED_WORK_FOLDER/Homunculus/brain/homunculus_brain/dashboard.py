"""Dashboard — activity feed for the Homunculus brain.

Serves ``GET /dashboard/`` (HTML page) and ``GET /dashboard/data`` (JSON).
Both are read-only and touch no LLM, no vault writes, no external I/O.

Activity source: ``{vault_path}/_activity.jsonl``
Format per row (from activity_log.py):
    {"at": "<iso8601>", "kind": "<str>", "event_id": "<str|null>",
     "raw_text": "<str|null>", "details": {}}

Rows from Herman < v1.3 may have different shapes; we degrade gracefully
rather than crash.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DASHBOARD_VERSION = "v0.5"

_VERB_ICONS: dict[str, str] = {
    "schedule": "📅",
    "handle": "✓",
    "note": "📝",
    "avoid": "⚠️",
    "event_ack": "✔️",
    "timer_start": "⏱",
    "timer_stop": "⏱",
    "timer_reset": "⏱",
}
_DEFAULT_ICON = "🔹"

_MAX_ROWS = 1000
_DEFAULT_ROWS = 200


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------


def _icon_for(row: dict[str, Any]) -> str:
    details = row.get("details") or {}
    verb = details.get("verb") if isinstance(details, dict) else None
    kind = row.get("kind", "")
    return _VERB_ICONS.get(verb or kind, _DEFAULT_ICON)


def _summary_for(row: dict[str, Any]) -> str:
    details = row.get("details") or {}
    kind = row.get("kind", "")
    raw = row.get("raw_text") or ""

    if kind == "capture_parsed" and isinstance(details, dict):
        verb = details.get("verb", "")
        subject = details.get("subject", "")
        if verb or subject:
            return f"verb={verb}  {subject}".strip()

    if kind == "timer_start" and isinstance(details, dict):
        project = details.get("project", "")
        return f"Started: {project}" if project else "Timer started"

    if kind == "timer_stop" and isinstance(details, dict):
        project = details.get("project", "")
        duration = details.get("duration_seconds", 0)
        total = details.get("total_seconds", 0)
        dur_str = _short_duration(duration)
        total_str = _short_duration(total)
        if project:
            return f"Stopped: {project} — {dur_str} (total {total_str})"
        return "Timer stopped"

    if kind == "timer_reset" and isinstance(details, dict):
        project = details.get("project", "")
        cleared = details.get("cleared_seconds", 0)
        cleared_str = _short_duration(cleared)
        if project:
            return f"Reset: {project} — cleared {cleared_str}"
        return "Timer reset"

    # Fallback: raw_text truncated
    if raw:
        return raw[:80] + ("…" if len(raw) > 80 else "")
    return kind or "(no summary)"


def _short_duration(seconds: int) -> str:
    """Short format for dashboard feed rows: '47m 32s' or '4h 12m'."""
    if seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s"
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    return f"{hours}h {mins}m"


def _confidence_for(row: dict[str, Any]) -> Optional[float]:
    details = row.get("details")
    if not isinstance(details, dict):
        return None
    c = details.get("confidence")
    if c is None:
        return None
    try:
        return float(c)
    except (TypeError, ValueError):
        return None


def _parse_at(at_str: Any) -> Optional[datetime]:
    """Parse the 'at' field. Returns None if unparseable."""
    if not at_str:
        return None
    try:
        dt = datetime.fromisoformat(str(at_str))
        # If naive, assume UTC (older rows pre v1.3 may be naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _is_clarifying_row(row: dict[str, Any]) -> bool:
    """Return True if the activity row represents a stored=False clarifying question.

    A clarifying row has:
      - kind == 'capture_parsed'
      - details.stored == False  (note: bool False, not absent)
      - details.clarifying_question is non-empty
    """
    details = row.get("details")
    if not isinstance(details, dict):
        return False
    # stored=False is written into details by the v2.2.0 activity log path.
    if details.get("stored") is not False:
        return False
    question = details.get("clarifying_question")
    return bool(question)


def _shape_row(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Convert a raw JSONL row into a dashboard-renderable dict.

    Returns None if the row is too malformed to render at all (e.g. no 'at'
    field that can be parsed). Non-fatal missing fields degrade gracefully.

    v0.5: clarifying-question rows get a distinct icon, summary prefix, and
    is_clarifying=True flag for the frontend renderer.
    """
    at_str = row.get("at")
    dt = _parse_at(at_str)
    if dt is None:
        # Can't render a row with no parseable timestamp
        return None

    details = row.get("details")
    if not isinstance(details, dict):
        details = {}

    is_clarifying = _is_clarifying_row(row)

    if is_clarifying:
        icon = "⚠️❓"
        question = details.get("clarifying_question", "")
        q_truncated = (question[:57] + "…") if len(question) > 60 else question
        summary = f"Awaiting clarification — {q_truncated}"
        clarifying_question = question
    else:
        icon = _icon_for(row)
        summary = _summary_for(row)
        clarifying_question = None

    shaped: dict[str, Any] = {
        "at": dt.isoformat(),
        "kind": row.get("kind") or "",
        "event_id": row.get("event_id"),
        "raw_text": row.get("raw_text") or "",
        "icon": icon,
        "summary": summary,
        "confidence": _confidence_for(row),
        "details": details,
        # Extras for the expand panel
        "written_path": details.get("written_path"),
        "ambiguous_fields": details.get("ambiguous_fields"),
        # v0.5: clarifying-question flag for the frontend renderer
        "is_clarifying": True if is_clarifying else None,
        "clarifying_question": clarifying_question,
    }
    return shaped


# ---------------------------------------------------------------------------
# Reading the log
# ---------------------------------------------------------------------------


def read_recent(
    vault_path: Path,
    limit: int = _DEFAULT_ROWS,
    since: Optional[datetime] = None,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Return shaped rows and the latest_at timestamp string.

    Rows are returned newest-first (reverse chronological).
    ``since`` is an optional lower-bound (exclusive): only rows with
    ``at > since`` are included. This is for incremental refresh.

    We read the file forward (simple), shape each line, collect all valid
    shaped rows, sort by timestamp descending, then slice to ``limit``.
    For 200 rows today this is fine. When the log hits 100 MB we can add
    seek-from-end; for now keep it simple and correct.
    """
    limit = min(limit, _MAX_ROWS)
    path = vault_path / "_activity.jsonl"

    shaped: list[dict[str, Any]] = []

    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row = _shape_row(raw)
                if row is None:
                    continue
                if since is not None:
                    row_dt = _parse_at(row["at"])
                    if row_dt is not None and row_dt <= since:
                        continue
                shaped.append(row)

    # Sort newest-first
    shaped.sort(key=lambda r: r["at"], reverse=True)

    # Capture latest_at before slicing
    latest_at: Optional[str] = shaped[0]["at"] if shaped else None

    return shaped[:limit], latest_at


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Homunculus Dashboard</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  /*
   * Dashboard v0.5 — light theme
   *
   * Layout model:
   *   body         flex-column, height:100vh, overflow:hidden
   *     header     sticky, z-index:20
   *     #timers-panel  sticky (below header), z-index:10
   *     #feed      flex:1, overflow-y:auto  ← only this scrolls
   *
   * Colours:
   *   Main bg      #f7f7f8  (off-white)
   *   Timers bg    #eef2f7  (subtle blue tint)
   *   Row bg       #ffffff
   *   Primary text #1a1a1a
   *   Secondary    #6b7280
   *   Border       #e5e7eb
   *   RUNNING      #16a34a (green-700)
   *   CLARIFY bg   #fffbeb  (warning amber tint, v0.5)
   *   CLARIFY border #f59e0b (amber-400)
   */

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 15px;
    line-height: 1.5;
    background: #f7f7f8;
    color: #1a1a1a;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  /* ---- VERSION BADGE (upper-left, inside header) ---- */
  .version-badge {
    font-size: 11px;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: 0.04em;
    background: #4b5563;
    padding: 2px 7px;
    border-radius: 4px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  /* ---- HEADER ---- */
  header {
    position: sticky;
    top: 0;
    z-index: 20;
    background: #ffffff;
    border-bottom: 1px solid #e5e7eb;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: nowrap;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    flex-shrink: 0;
  }

  header h1 {
    font-size: 16px;
    font-weight: 600;
    color: #111827;
    letter-spacing: -0.01em;
    white-space: nowrap;
  }

  .header-meta {
    font-size: 12px;
    color: #6b7280;
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .refresh-link {
    font-size: 12px;
    color: #2563eb;
    cursor: pointer;
    text-decoration: none;
    border: none;
    background: none;
    padding: 0;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .refresh-link:hover { text-decoration: underline; }

  .disconnected-badge {
    display: none;
    font-size: 12px;
    font-weight: 500;
    color: #b45309;
    padding: 2px 8px;
    border-radius: 4px;
    background: #fef3c7;
    border: 1px solid #f59e0b;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .disconnected-badge.visible { display: inline-block; }

  /* ---- TIMERS PANEL (sticky below header) ---- */
  #timers-panel {
    position: sticky;
    top: 45px;
    z-index: 10;
    background: #eef2f7;
    border-bottom: 1px solid #d1dce8;
    flex-shrink: 0;
  }

  .timers-inner {
    max-width: 900px;
    margin: 0 auto;
    padding: 10px 16px;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }

  .timers-section {
    background: #ffffff;
    border: 1px solid #dbe3ed;
    border-radius: 8px;
    overflow: hidden;
    flex: 1;
    min-width: 240px;
  }

  .timers-section-header {
    font-size: 11px;
    font-weight: 600;
    color: #374151;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    padding: 6px 12px 5px;
    border-bottom: 1px solid #e5e7eb;
    background: #f8fafc;
  }

  .timer-row {
    display: flex;
    align-items: center;
    padding: 7px 12px;
    border-bottom: 1px solid #f3f4f6;
    gap: 8px;
  }
  .timer-row:last-child { border-bottom: none; }

  .timer-icon { font-size: 13px; flex-shrink: 0; }

  .timer-project {
    flex: 1;
    font-size: 13px;
    font-weight: 500;
    color: #111827;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .timer-elapsed {
    font-size: 13px;
    font-variant-numeric: tabular-nums;
    color: #16a34a;
    font-weight: 600;
    min-width: 78px;
    text-align: right;
  }

  .timer-total {
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    color: #4b5563;
    min-width: 60px;
    text-align: right;
  }

  .timer-touched {
    font-size: 11px;
    color: #9ca3af;
    min-width: 70px;
    text-align: right;
  }

  .timer-running-badge {
    font-size: 10px;
    font-weight: 600;
    background: #dcfce7;
    color: #15803d;
    border: 1px solid #86efac;
    border-radius: 4px;
    padding: 1px 5px;
    letter-spacing: 0.03em;
    flex-shrink: 0;
  }

  .timers-empty {
    padding: 8px 12px;
    font-size: 12px;
    color: #9ca3af;
    font-style: italic;
  }

  /* ---- FEED (scrollable area) ---- */
  #feed {
    flex: 1;
    overflow-y: auto;
  }

  #feed-inner {
    max-width: 900px;
    margin: 0 auto;
    padding: 8px 16px 24px;
  }

  .empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #9ca3af;
    line-height: 2;
  }
  .empty-state .empty-icon {
    font-size: 36px;
    display: block;
    margin-bottom: 12px;
    opacity: 0.5;
  }
  .empty-state p { font-size: 14px; }
  .empty-state code {
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: 12px;
    background: #f3f4f6;
    padding: 2px 6px;
    border-radius: 3px;
    color: #374151;
  }

  /* ---- ACTIVITY ROW ---- */
  .row {
    display: grid;
    grid-template-columns: 30px 1fr auto;
    align-items: start;
    gap: 0 10px;
    padding: 10px 10px;
    background: #ffffff;
    border-bottom: 1px solid #f3f4f6;
    cursor: pointer;
    transition: background 0.1s;
    border-radius: 0;
  }
  .row:first-child { border-top: 1px solid #f3f4f6; }
  .row:hover { background: #f9fafb; }

  /* v0.5 — clarifying-question row: warning-amber accent */
  .row.clarify {
    background: #fffbeb;
    border-left: 3px solid #f59e0b;
  }
  .row.clarify:hover { background: #fef3c7; }
  .row.clarify .row-summary { color: #92400e; }

  /* New-row highlight animation */
  @keyframes highlightFade {
    from { background-color: #fef9c3; }
    to   { background-color: #ffffff; }
  }
  .row.new-highlight {
    animation: highlightFade 1.2s ease-out forwards;
  }

  .row-icon {
    font-size: 15px;
    line-height: 1.5;
    text-align: center;
    user-select: none;
    padding-top: 1px;
  }

  .row-body {
    min-width: 0;
  }

  .row-summary {
    font-size: 14px;
    font-weight: 500;
    color: #111827;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .row-meta {
    font-size: 11px;
    color: #9ca3af;
    margin-top: 2px;
  }

  .row-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
    white-space: nowrap;
    padding-top: 1px;
  }

  .row-time {
    font-size: 11px;
    color: #9ca3af;
  }

  .conf-pill {
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 3px;
    font-weight: 600;
  }
  .conf-pill.ok   { background: #dcfce7; color: #15803d; }
  .conf-pill.warn { background: #fef3c7; color: #b45309; }

  /* ---- EXPAND PANEL ---- */
  .row-expand {
    display: none;
    grid-column: 2 / -1;
    margin-top: 6px;
    padding: 10px 12px;
    background: #f8fafc;
    border-radius: 6px;
    border: 1px solid #e5e7eb;
    font-size: 12px;
    line-height: 1.6;
  }
  .row-expand.open { display: block; }

  .expand-field { margin-bottom: 6px; }
  .expand-label { color: #6b7280; font-size: 11px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
  .expand-value { color: #374151; word-break: break-all; margin-top: 1px; }
  .expand-value a { color: #2563eb; }

  .expand-json {
    margin-top: 8px;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 8px 10px;
    color: #334155;
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: 11px;
    white-space: pre;
    overflow-x: auto;
  }
</style>
</head>
<body>

<header>
  <span class="version-badge">DASHBOARD_VERSION_PLACEHOLDER</span>
  <h1>Homunculus</h1>
  <span class="header-meta" id="header-meta">Loading…</span>
  <button class="refresh-link" onclick="refreshNow()">Refresh</button>
  <span class="disconnected-badge" id="disconn-badge">⚠ Disconnected</span>
</header>

<!-- Timers Panel — sticky below header -->
<div id="timers-panel">
  <div class="timers-inner">
    <div class="timers-section" id="timers-running-section">
      <div class="timers-section-header">⏱ Running Timers</div>
      <div id="timers-running-body"><div class="timers-empty">No timers running.</div></div>
    </div>
    <div class="timers-section" id="timers-totals-section">
      <div class="timers-section-header">Project Totals</div>
      <div id="timers-totals-body"><div class="timers-empty">No project totals yet.</div></div>
    </div>
  </div>
</div>

<!-- Activity Feed — only this area scrolls -->
<div id="feed">
  <div id="feed-inner">
    <div class="empty-state" id="empty-state" style="display:none">
      <span class="empty-icon">📭</span>
      <p>No activity yet.</p>
      <p>Record a voice memo or POST to one of these endpoints:</p>
      <p><code>POST /capture/text</code> &nbsp;&nbsp; <code>POST /capture/parsed</code></p>
    </div>
  </div>
</div>

<script>
"use strict";

const DATA_URL = "/dashboard/data";
const POLL_INTERVAL_MS = 5000;

let latestAt = null;   // ISO string of newest row we've seen
let rowCount  = 0;
let pollTimer = null;
let disconnected = false;

// ---- Relative time --------------------------------------------------------

function relativeTime(isoStr) {
  const dt  = new Date(isoStr);
  const now = new Date();
  const diffMs  = now - dt;
  const diffSec = Math.round(diffMs / 1000);
  const diffMin = Math.round(diffMs / 60000);
  const diffH   = Math.round(diffMs / 3600000);

  if (diffSec < 60)   return "just now";
  if (diffMin < 60)   return diffMin + " min ago";
  if (diffH   < 24)   return diffH + " h ago";

  // Yesterday?
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (dt.toDateString() === yesterday.toDateString()) {
    return "Yesterday, " + dt.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"});
  }

  return dt.toLocaleDateString([], {month:"short", day:"numeric"})
    + ", " + dt.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"});
}

// ---- Row rendering --------------------------------------------------------

function buildRow(r, isNew) {
  const conf = (r.confidence != null) ? r.confidence : null;
  const confHtml = (conf !== null)
    ? `<span class="conf-pill ${conf >= 0.6 ? 'ok' : 'warn'}">${conf.toFixed(2)}</span>`
    : "";

  const timeStr = relativeTime(r.at);
  const absUtc  = new Date(r.at).toUTCString();

  // Build expand panel content
  let expandHtml = "";
  // v0.5: clarifying-question rows show full question + transcript at the top
  if (r.is_clarifying && r.clarifying_question) {
    expandHtml += `<div class="expand-field">
      <div class="expand-label">Clarifying question</div>
      <div class="expand-value" style="color:#92400e;font-weight:500">${esc(r.clarifying_question)}</div>
    </div>`;
  }
  if (r.raw_text) {
    expandHtml += `<div class="expand-field">
      <div class="expand-label">Raw text</div>
      <div class="expand-value">${esc(r.raw_text)}</div>
    </div>`;
  }
  if (r.event_id) {
    expandHtml += `<div class="expand-field">
      <div class="expand-label">Event ID</div>
      <div class="expand-value">${esc(r.event_id)}</div>
    </div>`;
  }
  if (r.written_path) {
    expandHtml += `<div class="expand-field">
      <div class="expand-label">Written path</div>
      <div class="expand-value"><code>${esc(r.written_path)}</code></div>
    </div>`;
  }
  if (r.ambiguous_fields && r.ambiguous_fields.length > 0) {
    expandHtml += `<div class="expand-field">
      <div class="expand-label">Ambiguous fields</div>
      <div class="expand-value">${r.ambiguous_fields.map(esc).join(", ")}</div>
    </div>`;
  }
  if (r.details && Object.keys(r.details).length > 0) {
    expandHtml += `<div class="expand-json">${esc(JSON.stringify(r.details, null, 2))}</div>`;
  }

  const div = document.createElement("div");
  // v0.5: add 'clarify' class for warning-amber styling on clarifying rows
  div.className = "row" + (isNew ? " new-highlight" : "") + (r.is_clarifying ? " clarify" : "");
  div.innerHTML = `
    <div class="row-icon">${r.icon}</div>
    <div class="row-body">
      <div class="row-summary">${esc(r.summary)}</div>
      <div class="row-meta">${esc(r.kind)}</div>
    </div>
    <div class="row-right">
      <span class="row-time" title="${esc(absUtc)}">${esc(timeStr)}</span>
      ${confHtml}
    </div>
    <div class="row-expand">${expandHtml}</div>
  `;

  // Click to expand
  div.addEventListener("click", () => {
    const panel = div.querySelector(".row-expand");
    panel.classList.toggle("open");
  });

  return div;
}

function esc(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---- Feed management ------------------------------------------------------

function prependRows(rows, isNew) {
  const feedInner = document.getElementById("feed-inner");
  const empty     = document.getElementById("empty-state");

  if (rows.length === 0 && rowCount === 0) {
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";

  // Insert newest rows at top of feed-inner (they come back newest-first already)
  const frag = document.createDocumentFragment();
  for (const r of rows) {
    frag.appendChild(buildRow(r, isNew));
  }
  feedInner.insertBefore(frag, feedInner.firstChild);
  rowCount += rows.length;
  updateMeta();
}

function updateMeta() {
  const el = document.getElementById("header-meta");
  el.textContent = `Last ${rowCount} event${rowCount !== 1 ? "s" : ""} · Auto-refresh 5 s`;
}

// ---- Fetch helpers --------------------------------------------------------

async function fetchData(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

async function initialLoad() {
  try {
    const data = await fetchData(DATA_URL);
    setConnected();
    if (data.latest_at) latestAt = data.latest_at;
    prependRows(data.rows || [], false);
  } catch (e) {
    setDisconnected();
  }
  schedulePoll();
}

async function pollIncremental() {
  const url = latestAt ? (DATA_URL + "?since=" + encodeURIComponent(latestAt)) : DATA_URL;
  try {
    const data = await fetchData(url);
    setConnected();
    const newRows = data.rows || [];
    if (newRows.length > 0) {
      if (data.latest_at) latestAt = data.latest_at;
      prependRows(newRows, true);
    }
  } catch (e) {
    setDisconnected();
  }
  schedulePoll();
}

function schedulePoll() {
  if (pollTimer) clearTimeout(pollTimer);
  pollTimer = setTimeout(pollIncremental, POLL_INTERVAL_MS);
}

function setConnected() {
  if (disconnected) {
    disconnected = false;
    document.getElementById("disconn-badge").classList.remove("visible");
  }
}

function setDisconnected() {
  if (!disconnected) {
    disconnected = true;
    document.getElementById("disconn-badge").classList.add("visible");
  }
}

function refreshNow() {
  if (pollTimer) clearTimeout(pollTimer);
  // Full reload — rebuild feed-inner, preserving the wrapper div
  document.getElementById("feed-inner").innerHTML =
    '<div class="empty-state" id="empty-state" style="display:none">...</div>';
  rowCount  = 0;
  latestAt  = null;
  initialLoad();
  fetchTimers();
}

// ---- Timers Panel ---------------------------------------------------------

const TIMERS_URL = "/dashboard/timers";
let timersPollTimer = null;
// Track running timers client-side for the 1-sec tick
let runningTimers = [];  // [{slug, started_at_ms, project}]

function fmtElapsed(totalSec) {
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return h + "h " + m + "m " + String(s).padStart(2, "0") + "s";
  return m + "m " + String(s).padStart(2, "0") + "s";
}

function fmtTotal(totalSec) {
  if (totalSec < 3600) {
    const m = Math.floor(totalSec / 60);
    return m + "m";
  }
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  return h + "h " + m + "m";
}

function renderRunning(items) {
  const el = document.getElementById("timers-running-body");
  if (!items || items.length === 0) {
    el.innerHTML = '<div class="timers-empty">No timers running.</div>';
    runningTimers = [];
    return;
  }
  runningTimers = items.map(r => ({
    slug: r.slug,
    project: r.project,
    started_at_ms: new Date(r.started_at).getTime(),
  }));
  let html = "";
  for (const r of items) {
    const elapsed = r.elapsed_seconds;
    html += `<div class="timer-row" id="trow-${esc(r.slug)}">
      <span class="timer-icon">⏱</span>
      <span class="timer-project">${esc(r.project)}</span>
      <span class="timer-running-badge">RUNNING</span>
      <span class="timer-elapsed" id="elapsed-${esc(r.slug)}">${fmtElapsed(elapsed)}</span>
    </div>`;
  }
  el.innerHTML = html;
}

function renderTotals(items) {
  const el = document.getElementById("timers-totals-body");
  if (!items || items.length === 0) {
    el.innerHTML = '<div class="timers-empty">No project totals yet.</div>';
    return;
  }
  let html = "";
  for (const t of items) {
    const runBadge = t.is_running
      ? '<span class="timer-running-badge">RUNNING</span>' : "";
    html += `<div class="timer-row">
      <span class="timer-icon">⏱</span>
      <span class="timer-project">${esc(t.project)}</span>
      ${runBadge}
      <span class="timer-total">${fmtTotal(t.total_seconds)}</span>
      <span class="timer-touched">${relativeTime(t.last_touched_at)}</span>
    </div>`;
  }
  el.innerHTML = html;
}

async function fetchTimers() {
  try {
    const data = await fetchData(TIMERS_URL);
    renderRunning(data.running || []);
    renderTotals(data.totals || []);
  } catch (e) {
    // Non-fatal; timers panel shows stale data
  }
  timersPollTimer = setTimeout(fetchTimers, 5000);
}

// 1-second tick to update elapsed times client-side without a server round-trip
setInterval(() => {
  const now = Date.now();
  for (const rt of runningTimers) {
    const el = document.getElementById("elapsed-" + rt.slug);
    if (el) {
      const elapsed = Math.floor((now - rt.started_at_ms) / 1000);
      el.textContent = fmtElapsed(elapsed);
    }
  }
}, 1000);

// ---- Boot -----------------------------------------------------------------
initialLoad();
fetchTimers();
</script>
</body>
</html>
"""

# Bake the version badge in at import time so we never serve a stale string
DASHBOARD_HTML = _DASHBOARD_HTML.replace("DASHBOARD_VERSION_PLACEHOLDER", DASHBOARD_VERSION)
