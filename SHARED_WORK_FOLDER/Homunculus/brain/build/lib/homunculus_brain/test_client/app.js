/* Homunculus brain test client — v1.2.1
 *
 * Vanilla JS, no build step, no framework. The page is mounted at /test/
 * by the FastAPI server (see server.py) and hits the brain's HTTP surface
 * directly on the same origin. There is no auth — Tailscale is the trust
 * boundary, same as the phone client.
 *
 * Design notes:
 *   - The Confirm flow holds the ParsedIntent locally in the response card.
 *     The brain now echoes intent back from /capture/text (additive
 *     optional field on CaptureResponse) so the client never has to guess.
 *     If the brain omits it (older brain), the page degrades to "Confirm"
 *     disabled with a hint.
 *   - The upcoming-rows view auto-refreshes every 5s and reconciles: rows
 *     that disappear from the brain's response must disappear from the UI
 *     in the same tick. This is the bug the boss's polling script had.
 *   - "include fired" toggles the brain-side include_fired query param so
 *     the user can verify just-fired rows during testing.
 */

(() => {
  "use strict";

  const REFRESH_MS = 5000;

  // --- DOM ----
  const $ = (id) => document.getElementById(id);
  const captureText = $("capture-text");
  const captureSend = $("capture-send");
  const responseArea = $("response-area");
  const responseCard = $("response-card");
  const upcomingRows = $("upcoming-rows");
  const includeFiredCk = $("include-fired");
  const windowHoursInp = $("window-hours");
  const refreshBtn = $("refresh-now");
  const nextRefreshEl = $("next-refresh");
  const activityTail = $("activity-tail");
  const vbDesign = $("vb-design");
  const vbPkg = $("vb-pkg");
  const vbConn = $("vb-conn");
  const brainOrigin = $("brain-origin");
  const brainVault = $("brain-vault");

  brainOrigin.textContent = window.location.origin;

  // --- helpers ----
  const j = async (method, path, body) => {
    const init = { method, headers: { "Content-Type": "application/json" } };
    if (body !== undefined) init.body = JSON.stringify(body);
    const r = await fetch(path, init);
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`${method} ${path} -> ${r.status}: ${text}`);
    }
    return r.json();
  };

  const setConn = (state, label) => {
    vbConn.className = `vb-conn ${state}`;
    vbConn.textContent = label;
  };

  // Format an ISO datetime in its OWN tz, not the browser's. The row tells
  // us its tz; respect it. Falls back to browser locale if zone is missing
  // or unknown.
  const fmtFireTime = (iso, tz) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    try {
      return new Intl.DateTimeFormat(undefined, {
        timeZone: tz || undefined,
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }).format(d);
    } catch (e) {
      return d.toLocaleString();
    }
  };

  const escapeHtml = (s) => {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  };

  // --- /health ----
  async function loadHealth() {
    try {
      const h = await j("GET", "/health");
      vbDesign.textContent = h.design_version;
      vbPkg.textContent = h.package_version;
      brainVault.textContent = h.vault_path;
      setConn("ok", "online");
    } catch (e) {
      setConn("err", "offline");
      console.error(e);
    }
  }

  // --- /capture/text + /capture/confirm ----
  async function sendCapture() {
    const text = captureText.value.trim();
    if (!text) return;
    captureSend.disabled = true;
    captureSend.textContent = "Sending…";
    try {
      const body = {
        text,
        // The browser knows its own tz; pass it so the brain resolves
        // relative day/time hints from the boss's wall clock.
        speaker_tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      };
      const resp = await j("POST", "/capture/text", body);
      renderResponse(resp);
      await loadUpcoming();
    } catch (e) {
      renderError(e);
    } finally {
      captureSend.disabled = false;
      captureSend.textContent = "Send";
    }
  }

  async function confirmIntent(intent) {
    try {
      const body = {
        intent,
        speaker_tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      };
      const resp = await j("POST", "/capture/confirm", body);
      renderResponse(resp);
      await loadUpcoming();
    } catch (e) {
      renderError(e);
    }
  }

  function renderError(e) {
    responseArea.classList.remove("hidden");
    responseCard.className = "response-card needs_clarification";
    responseCard.innerHTML = `
      <span class="action-badge">error</span>
      <div class="spoken">Request failed.</div>
      <pre>${escapeHtml(e.message || String(e))}</pre>
    `;
    activityTail.textContent = e.message || String(e);
  }

  function renderResponse(resp) {
    responseArea.classList.remove("hidden");
    responseCard.className = `response-card ${resp.action}`;

    const parts = [];
    parts.push(`<span class="action-badge">${escapeHtml(resp.action)}</span>`);

    const spokenClass = resp.action === "needs_clarification" ? "spoken clarifying" : "spoken";
    parts.push(`<div class="${spokenClass}">${escapeHtml(resp.spoken_reply)}</div>`);

    if (resp.action === "needs_clarification" && resp.clarifying_question
        && resp.clarifying_question !== resp.spoken_reply) {
      parts.push(`<div class="spoken">${escapeHtml(resp.clarifying_question)}</div>`);
    }

    const kv = [];
    kv.push(`<div class="k">kind</div><div class="v">${escapeHtml(resp.kind)}</div>`);
    kv.push(`<div class="k">confidence</div><div class="v">${escapeHtml(resp.confidence)}</div>`);
    if (resp.written_path) {
      kv.push(`<div class="k">written</div><div class="v">${escapeHtml(resp.written_path)}</div>`);
    }
    if (resp.conflicts && (resp.conflicts.has_direct_conflict || resp.conflicts.has_fuzzy_conflict)) {
      const direct = resp.conflicts.has_direct_conflict ? "direct" : "fuzzy";
      kv.push(`<div class="k">conflict</div><div class="v">${direct}</div>`);
    }
    parts.push(`<div class="kv-grid">${kv.join("")}</div>`);

    if (resp.action === "needs_confirmation") {
      if (resp.intent) {
        parts.push(`
          <div class="confirm-actions">
            <button class="confirm" id="btn-confirm">Confirm — save event</button>
            <button class="cancel"  id="btn-cancel">Cancel</button>
          </div>
        `);
      } else {
        parts.push(`
          <div class="confirm-actions">
            <button class="confirm" disabled title="brain did not echo intent">Confirm (unavailable)</button>
            <span class="muted small">Brain response is missing the echoed intent.
            Update brain to v1.2.1+ to enable confirm from the test client.</span>
          </div>
        `);
      }
    }

    parts.push(`
      <details class="raw">
        <summary>raw response</summary>
        <pre>${escapeHtml(JSON.stringify(resp, null, 2))}</pre>
      </details>
    `);

    responseCard.innerHTML = parts.join("");

    // Wire up the confirm/cancel buttons. We capture the parsed intent in
    // the closure so we don't have to re-parse a hidden data attribute.
    if (resp.action === "needs_confirmation" && resp.intent) {
      $("btn-confirm").addEventListener("click", () => confirmIntent(resp.intent));
      $("btn-cancel" ).addEventListener("click", () => {
        responseArea.classList.add("hidden");
        captureText.focus();
      });
    }

    // Lightweight activity peek: dump the most recent response payload so
    // the boss can eyeball what the brain returned without opening
    // devtools. This is NOT the activity log endpoint (which doesn't exist
    // as an HTTP route yet — v1.3); it's just a debug aid.
    activityTail.textContent = JSON.stringify(resp, null, 2);
  }

  // --- /reminders/upcoming ----
  async function loadUpcoming() {
    const windowHours = Math.max(1, parseInt(windowHoursInp.value, 10) || 72);
    const includeFired = includeFiredCk.checked;
    const qs = new URLSearchParams({
      window_hours: String(windowHours),
      include_fired: includeFired ? "true" : "false",
    });
    try {
      const rows = await j("GET", `/reminders/upcoming?${qs}`);
      renderUpcoming(rows);
      setConn("ok", "online");
    } catch (e) {
      setConn("err", "fetch failed");
      console.error(e);
      upcomingRows.innerHTML = `<div class="muted">Fetch failed: ${escapeHtml(e.message)}</div>`;
    }
  }

  function renderUpcoming(rows) {
    // Reconcile semantics: this function rebuilds the DOM from scratch on
    // every refresh. Rows that disappear from the brain's response
    // disappear from the UI in the same tick — by construction. This is
    // the bug the boss's polling script had (stale cache).
    if (!rows.length) {
      upcomingRows.innerHTML = `<div class="muted">No upcoming reminders in window.</div>`;
      return;
    }

    // Group by event_id so each event's strike chain reads as a unit.
    const groups = new Map();
    for (const r of rows) {
      if (!groups.has(r.event_id)) groups.set(r.event_id, []);
      groups.get(r.event_id).push(r);
    }

    const out = [];
    for (const [eventId, rs] of groups) {
      rs.sort((a, b) => new Date(a.fire_at) - new Date(b.fire_at));
      const earliest = rs[0];
      const isSummary = earliest.kind === "morning_summary";
      out.push(`
        <div class="event-group" data-event-id="${escapeHtml(eventId)}">
          <div class="event-group-hdr">
            <span class="title">${isSummary ? "Morning summary" : escapeHtml(earliest.body.split(":")[0] || "Event")}</span>
            <span class="eid">${escapeHtml(eventId)}</span>
          </div>
          ${rs.map(renderRow).join("")}
        </div>
      `);
    }

    upcomingRows.innerHTML = out.join("");

    // Wire up ack buttons.
    upcomingRows.querySelectorAll("button.ack").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const eventId = btn.dataset.eventId;
        const kind = btn.dataset.kind;
        btn.disabled = true;
        btn.textContent = "…";
        try {
          await j("POST", "/ack", { event_id: eventId, kind });
          await loadUpcoming(); // immediate reconcile
        } catch (e) {
          renderError(e);
          btn.disabled = false;
          btn.textContent = "OK";
        }
      });
    });
  }

  function renderRow(r) {
    const faded = ["acked", "cancelled", "fired"].includes(r.status);
    const ackable = !faded && r.kind !== "morning_summary";
    return `
      <div class="row ${faded ? "faded" : ""}">
        <span class="kind-badge ${r.kind}">${escapeHtml(r.kind)}</span>
        <span class="status-badge ${r.status}">${escapeHtml(r.status)}</span>
        <span class="body">${escapeHtml(r.body)}</span>
        <span class="fire">${escapeHtml(fmtFireTime(r.fire_at, r.tz))}</span>
        <span class="ack-cell">
          ${ackable
            ? `<button class="ack" data-event-id="${escapeHtml(r.event_id)}" data-kind="${escapeHtml(r.kind)}">OK</button>`
            : ""}
        </span>
      </div>
    `;
  }

  // --- refresh loop (5s, with countdown) ----
  let countdown = REFRESH_MS / 1000;
  function tickCountdown() {
    nextRefreshEl.textContent = `next refresh in ${countdown}s`;
    countdown -= 1;
    if (countdown < 0) {
      countdown = REFRESH_MS / 1000;
      loadUpcoming();
    }
  }
  setInterval(tickCountdown, 1000);

  // --- wire events ----
  captureSend.addEventListener("click", sendCapture);
  captureText.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      sendCapture();
    }
  });
  document.querySelectorAll(".chip").forEach((c) => {
    c.addEventListener("click", () => {
      captureText.value = c.dataset.text;
      captureText.focus();
    });
  });
  refreshBtn.addEventListener("click", () => { countdown = 0; tickCountdown(); });
  includeFiredCk.addEventListener("change", loadUpcoming);
  windowHoursInp.addEventListener("change", loadUpcoming);

  // --- boot ----
  loadHealth();
  loadUpcoming();
})();
