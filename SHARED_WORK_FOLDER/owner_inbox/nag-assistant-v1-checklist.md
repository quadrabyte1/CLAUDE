# Nag Assistant — v1 Build Checklist

A local-first shoulder-assistant that fires Pushover nags for upcoming Google Calendar events and waits for an ack before going quiet. Runs entirely on the Mac mini via n8n in Docker.

Built by Sienna (Full-Stack Application Developer, Thomas's AI team). Written 2026-04-20.

**Estimated time:** 2–4 hours (most of it is Phase 2 email migration if you choose to do it, and Phase 5a Google Cloud OAuth setup).

**Status:** not started

> Update the Status line as you go, e.g. `Status: Phase 3 in progress` or `Status: Phase 7 — stuck on node 4`. Future Claude Code sessions can open this file and pick up exactly where you left off.

---

## Phase 1 — Accounts & apps

- [ ] Create a Pushover account at https://pushover.net
- [ ] Install the Pushover app on your iPhone and sign in
- [ ] In Pushover web dashboard, note your **User Key** (top right)
- [ ] In Pushover web dashboard, create a new **Application** called `nag-assistant` and note its **API Token**
- [ ] Send a test push from the Pushover web UI to confirm your phone receives it
- [ ] Confirm you have a Google account you're willing to use for Calendar (personal Gmail is fine)

---

## Phase 2 — Migrate Proton → Google (optional but recommended)

Only do this phase if Calendar currently lives in Proton and you want to consolidate. Skip if you're already on Google Calendar.

- [ ] Export Proton Calendar to `.ics` (Proton Calendar → Settings → Import/Export → Export)
- [ ] Import the `.ics` into Google Calendar (calendar.google.com → Settings → Import & Export → Import)
- [ ] Spot-check 5–10 events to confirm times, attendees, and recurrence rules survived
- [ ] Update any calendar subscriptions on your devices (iPhone, Mac) to point at the Google account
- [ ] Decide: keep Proton Calendar as archive (read-only) or delete. v1 assumes Google is the single source of truth.

---

## Phase 3 — Mac mini: sleep, reboot, Docker

- [ ] System Settings → Energy → set **Prevent automatic sleeping** (or "Never") so n8n keeps running
- [ ] System Settings → Energy → enable **Start up automatically after a power failure**
- [ ] System Settings → General → Login Items → confirm Docker Desktop is set to open at login
- [ ] Install Docker Desktop if not already installed (https://www.docker.com/products/docker-desktop/)
- [ ] Launch Docker Desktop and confirm the whale icon is running in the menu bar
- [ ] Open Terminal, run `docker --version` to confirm CLI works
- [ ] Reboot the Mac mini once and confirm Docker comes back up on its own

---

## Phase 4 — Install n8n in Docker

- [ ] Create a persistent data directory: `mkdir -p ~/n8n-data`
- [ ] Pull and run n8n with the following command:

```bash
docker run -d \
  --name n8n \
  --restart unless-stopped \
  -p 5678:5678 \
  -v ~/n8n-data:/home/node/.n8n \
  -e GENERIC_TIMEZONE="America/Los_Angeles" \
  -e TZ="America/Los_Angeles" \
  -e N8N_SECURE_COOKIE=false \
  n8nio/n8n
```

- [ ] Wait ~30 seconds, then open http://localhost:5678 in your browser
- [ ] Create the n8n owner account (email + password) — this is local-only, stored in `~/n8n-data`
- [ ] Bookmark http://localhost:5678
- [ ] Confirm `docker ps` shows `n8n` with status `Up` and `restart unless-stopped`

---

## Phase 5 — Google Calendar OAuth into n8n

### 5a — Google Cloud project

- [ ] Go to https://console.cloud.google.com and create a new project called `nag-assistant`
- [ ] In the project, go to **APIs & Services → Library** and enable **Google Calendar API**
- [ ] Go to **APIs & Services → OAuth consent screen**, choose **External**, fill in app name `nag-assistant`, your email, and save
- [ ] Under **Scopes**, add `https://www.googleapis.com/auth/calendar` (read + write)
- [ ] Under **Test users**, add your own Google email
- [ ] Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
- [ ] Application type: **Web application**. Name: `n8n-local`
- [ ] Authorized redirect URI: `http://localhost:5678/rest/oauth2-credential/callback`
- [ ] Save and copy the **Client ID** and **Client Secret**

### 5b — n8n side

- [ ] In n8n, go to **Credentials → New → Google Calendar OAuth2 API**
- [ ] Paste Client ID and Client Secret
- [ ] Click **Sign in with Google**, approve the scopes on your own Google account
- [ ] Confirm the credential shows a green check
- [ ] Create a quick test workflow with one **Google Calendar → Get Many Events** node, run it, confirm your events come back

---

## Phase 6 — Pushover credentials in n8n

- [ ] In n8n, go to **Settings → Variables** (or use env vars on the container — variables are simpler for v1)
- [ ] Add variable `PUSHOVER_USER_KEY` with your Pushover user key
- [ ] Add variable `PUSHOVER_API_TOKEN` with your `nag-assistant` app token
- [ ] (Optional) Add variable `NAG_LEAD_MINUTES` = `15` — how many minutes before an event to start nagging

---

## Phase 7 — Build the workflow (`nag`)

One workflow. One Schedule Trigger. Fans into two branches.

- [ ] Create a new workflow, name it `nag`
- [ ] Add a **Schedule Trigger** node, set to run **every 1 minute**
- [ ] From the Schedule Trigger, branch into **two parallel paths**:
  - **Branch A:** send nags for upcoming events
  - **Branch B:** poll for acks and silence nagged events

### Branch A — Send nags

- [ ] **Google Calendar → Get Many Events** node
  - Calendar: your primary
  - Time Min: `{{ $now.toISO() }}`
  - Time Max: `{{ $now.plus({ minutes: $vars.NAG_LEAD_MINUTES || 15 }).toISO() }}`
  - Return All: true
- [ ] **Code** node (JavaScript) — filter to events that need a nag:

```javascript
const leadMs = ($vars.NAG_LEAD_MINUTES || 15) * 60 * 1000;
const now = Date.now();
const items = $input.all();

return items
  .filter(i => {
    const start = new Date(i.json.start?.dateTime || i.json.start?.date).getTime();
    const delta = start - now;
    return delta > 0 && delta <= leadMs;
  })
  .map(i => ({
    json: {
      id: i.json.id,
      summary: i.json.summary || '(no title)',
      start: i.json.start?.dateTime || i.json.start?.date,
      description: i.json.description || '',
    }
  }));
```

- [ ] **Code** node — check if we've already nagged this event in this window (use workflow static data):

```javascript
const staticData = $getWorkflowStaticData('global');
staticData.nagged = staticData.nagged || {};

const items = $input.all();
const fresh = [];

for (const item of items) {
  const id = item.json.id;
  const start = item.json.start;
  const key = `${id}__${start}`;
  if (!staticData.nagged[key]) {
    staticData.nagged[key] = { nagCount: 0, ackedAt: null };
    fresh.push(item);
  } else if (!staticData.nagged[key].ackedAt) {
    // already tracked but not acked — still nag again
    fresh.push(item);
  }
}

return fresh;
```

- [ ] **HTTP Request** node — send Pushover notification:

| Field | Value |
|-------|-------|
| Method | POST |
| URL | `https://api.pushover.net/1/messages.json` |
| Body Content Type | Form-Urlencoded |
| `token` | `{{ $vars.PUSHOVER_API_TOKEN }}` |
| `user` | `{{ $vars.PUSHOVER_USER_KEY }}` |
| `title` | `Upcoming: {{ $json.summary }}` |
| `message` | `Starts {{ $json.start }}. Reply ACK in calendar description to silence.` |
| `priority` | `1` |

- [ ] **Code** node — bump nag count after successful send:

```javascript
const staticData = $getWorkflowStaticData('global');
const items = $input.all();

for (const item of items) {
  const key = `${item.json.id}__${item.json.start}`;
  if (staticData.nagged[key]) {
    staticData.nagged[key].nagCount += 1;
    staticData.nagged[key].lastNaggedAt = new Date().toISOString();
  }
}

return items;
```

### Branch B — Poll acks

- [ ] **Code** node — pull the list of currently-nagged, un-acked event IDs from static data:

```javascript
const staticData = $getWorkflowStaticData('global');
staticData.nagged = staticData.nagged || {};

return Object.entries(staticData.nagged)
  .filter(([_, v]) => !v.ackedAt)
  .map(([key, _]) => {
    const [id, start] = key.split('__');
    return { json: { id, start, key } };
  });
```

- [ ] **Google Calendar → Get Event** node (fetch fresh copy by event ID)
- [ ] **Code** node — check if description contains `ACK` (case-insensitive):

```javascript
const items = $input.all();
const staticData = $getWorkflowStaticData('global');

for (const item of items) {
  const desc = (item.json.description || '').toLowerCase();
  if (desc.includes('ack')) {
    const key = item.json.key || `${item.json.id}__${item.json.start?.dateTime || item.json.start?.date}`;
    if (staticData.nagged[key]) {
      staticData.nagged[key].ackedAt = new Date().toISOString();
    }
  }
}

return items;
```

- [ ] Save the workflow and **activate** it (toggle top right)

---

## Phase 8 — End-to-end sanity test

- [ ] In Google Calendar, create a test event titled `nag-test` starting 5 minutes from now
- [ ] Wait 1–2 minutes — confirm Pushover fires on your iPhone
- [ ] Confirm the nag repeats on the next minute tick (should fire again)
- [ ] Edit the event, add the word `ACK` to the description, save
- [ ] Wait 1–2 minutes — confirm the nags stop
- [ ] Delete the test event
- [ ] In n8n, go to **Executions** tab and confirm you see clean runs (green) for both branches
- [ ] Leave the laptop closed / Mac mini idle for 15 minutes, create another test event, confirm nags still fire

---

## Phase 9 — Known v1 limitations

These are intentional v1 cuts. Revisit in v2.

- [ ] No snooze button — only ACK in the description silences it
- [ ] No per-event nag cadence — every un-acked event nags every minute inside the lead window
- [ ] No quiet hours — it will nag at 3am if you have a 3am event
- [ ] No multi-calendar support — only the primary calendar is polled
- [ ] Static data lives in the n8n container volume (`~/n8n-data`); if you `docker rm` the container and lose the volume, all nag state resets (not catastrophic — just means events may re-nag once)
- [ ] No web UI for viewing nag history — check n8n **Executions** tab
- [ ] If the Mac mini is fully powered off, no nags fire (Phase 3 mitigates this)

---

*End of checklist. Update Status at top as you progress. If you get stuck, Larry can spawn me (Sienna) or Kit to help — just reference the phase and step number.*
