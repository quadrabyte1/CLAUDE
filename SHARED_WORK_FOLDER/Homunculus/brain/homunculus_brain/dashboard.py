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

DASHBOARD_VERSION = "v0.1"

_VERB_ICONS: dict[str, str] = {
    "schedule": "📅",
    "handle": "✓",
    "note": "📝",
    "avoid": "⚠️",
    "event_ack": "✔️",
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

    # Fallback: raw_text truncated
    if raw:
        return raw[:80] + ("…" if len(raw) > 80 else "")
    return kind or "(no summary)"


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


def _shape_row(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Convert a raw JSONL row into a dashboard-renderable dict.

    Returns None if the row is too malformed to render at all (e.g. no 'at'
    field that can be parsed). Non-fatal missing fields degrade gracefully.
    """
    at_str = row.get("at")
    dt = _parse_at(at_str)
    if dt is None:
        # Can't render a row with no parseable timestamp
        return None

    details = row.get("details")
    if not isinstance(details, dict):
        details = {}

    return {
        "at": dt.isoformat(),
        "kind": row.get("kind") or "",
        "event_id": row.get("event_id"),
        "raw_text": row.get("raw_text") or "",
        "icon": _icon_for(row),
        "summary": _summary_for(row),
        "confidence": _confidence_for(row),
        "details": details,
        # Extras for the expand panel
        "written_path": details.get("written_path"),
        "ambiguous_fields": details.get("ambiguous_fields"),
    }


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

_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Homunculus Dashboard</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
    background: #111;
    color: #d4d4d4;
    min-height: 100vh;
  }

  /* ---- VERSION BADGE (upper-left) ---- */
  .version-badge {
    position: fixed;
    top: 8px;
    left: 10px;
    font-size: 11px;
    color: #555;
    letter-spacing: 0.04em;
    z-index: 100;
  }

  /* ---- HEADER ---- */
  header {
    padding: 12px 16px 10px 140px;
    border-bottom: 1px solid #222;
    display: flex;
    align-items: baseline;
    gap: 16px;
    flex-wrap: wrap;
  }

  header h1 {
    font-size: 17px;
    font-weight: 600;
    color: #e8e8e8;
    letter-spacing: -0.01em;
  }

  .header-meta {
    font-size: 12px;
    color: #666;
    flex: 1;
  }

  .refresh-link {
    font-size: 12px;
    color: #4a9eff;
    cursor: pointer;
    text-decoration: none;
    border: none;
    background: none;
    padding: 0;
  }
  .refresh-link:hover { text-decoration: underline; }

  .disconnected-badge {
    display: none;
    font-size: 12px;
    color: #e07a33;
    padding: 2px 8px;
    border-radius: 4px;
    background: #2a1a0a;
    border: 1px solid #5a3010;
  }
  .disconnected-badge.visible { display: inline-block; }

  /* ---- FEED ---- */
  #feed {
    max-width: 900px;
    margin: 12px auto;
    padding: 0 12px;
  }

  .empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #555;
    line-height: 1.9;
  }
  .empty-state code {
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: 12px;
    background: #1a1a1a;
    padding: 2px 6px;
    border-radius: 3px;
    color: #9cdcfe;
  }

  /* ---- ACTIVITY ROW ---- */
  .row {
    display: grid;
    grid-template-columns: 28px 1fr auto;
    align-items: start;
    gap: 0 10px;
    padding: 9px 10px;
    border-bottom: 1px solid #1e1e1e;
    cursor: pointer;
    transition: background 0.1s;
  }
  .row:hover { background: #181818; }

  /* New-row highlight animation */
  @keyframes highlightFade {
    from { background-color: #3a3300; }
    to   { background-color: transparent; }
  }
  .row.new-highlight {
    animation: highlightFade 1s ease-out forwards;
  }

  .row-icon {
    font-size: 16px;
    line-height: 1.4;
    text-align: center;
    user-select: none;
  }

  .row-body {
    min-width: 0;
  }

  .row-summary {
    font-size: 13px;
    color: #ccc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .row-meta {
    font-size: 11px;
    color: #555;
    margin-top: 2px;
  }

  .row-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
    white-space: nowrap;
  }

  .row-time {
    font-size: 11px;
    color: #666;
  }

  .conf-pill {
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 3px;
    font-weight: 500;
  }
  .conf-pill.ok   { background: #1e2a1e; color: #6a9a6a; }
  .conf-pill.warn { background: #2a1e10; color: #c87830; }

  /* ---- EXPAND PANEL ---- */
  .row-expand {
    display: none;
    grid-column: 2 / -1;
    margin-top: 6px;
    padding: 8px 10px;
    background: #161616;
    border-radius: 4px;
    border: 1px solid #252525;
    font-size: 12px;
    line-height: 1.6;
  }
  .row-expand.open { display: block; }

  .expand-field { margin-bottom: 4px; }
  .expand-label { color: #666; font-size: 11px; }
  .expand-value { color: #b8b8b8; word-break: break-all; }
  .expand-value a { color: #4a9eff; }

  .expand-json {
    margin-top: 6px;
    background: #111;
    border-radius: 3px;
    padding: 6px 8px;
    color: #9cdcfe;
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: 11px;
    white-space: pre;
    overflow-x: auto;
  }
</style>
</head>
<body>

<div class="version-badge">DASHBOARD_VERSION_PLACEHOLDER · Homunculus Dashboard</div>

<header>
  <h1>Homunculus Activity</h1>
  <span class="header-meta" id="header-meta">Loading…</span>
  <button class="refresh-link" onclick="refreshNow()">Refresh now</button>
  <span class="disconnected-badge" id="disconn-badge">⚠️ Disconnected</span>
</header>

<div id="feed">
  <div class="empty-state" id="empty-state" style="display:none">
    <p>No activity yet.</p>
    <p>Record a voice memo or POST to one of these endpoints:</p>
    <p><code>POST /capture/text</code> &nbsp;&nbsp; <code>POST /capture/parsed</code></p>
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
  div.className = "row" + (isNew ? " new-highlight" : "");
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
  const feed  = document.getElementById("feed");
  const empty = document.getElementById("empty-state");

  if (rows.length === 0 && rowCount === 0) {
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";

  // Insert newest rows at top (they come back newest-first already)
  const frag = document.createDocumentFragment();
  for (const r of rows) {
    frag.appendChild(buildRow(r, isNew));
  }
  feed.insertBefore(frag, feed.firstChild);
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
  // Full reload
  document.getElementById("feed").innerHTML =
    '<div class="empty-state" id="empty-state" style="display:none">...</div>';
  rowCount  = 0;
  latestAt  = null;
  initialLoad();
}

// ---- Boot -----------------------------------------------------------------
initialLoad();
</script>
</body>
</html>
"""

# Bake the version badge in at import time so we never serve a stale string
DASHBOARD_HTML = _DASHBOARD_HTML.replace("DASHBOARD_VERSION_PLACEHOLDER", DASHBOARD_VERSION)
