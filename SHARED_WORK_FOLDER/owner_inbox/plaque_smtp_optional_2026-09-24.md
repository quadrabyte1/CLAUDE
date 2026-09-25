# Plaque Editor — SMTP Graceful Fallback
<!-- v4.59 — 2026-09-24 — Sienna -->

---

## Bug Reproduction

**Thomas's exact error:**

```
POST /api/generate_plate → HTTP 500
{"status":"error","msg":"SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASS env vars. See app/.env.example."}
```

This fired whenever any of the three SMTP vars were absent — even though the 3MF generator is entirely offline and the local-Downloads write path already existed in the code.

---

## Design Rule (locked)

| SMTP state | Behaviour |
|---|---|
| All three vars set | Send email (unchanged). |
| Any var missing | Skip email silently. Always write `~/Downloads/<slug>.3mf`. Return 200. |
| Partial config (1–2 of 3 set) | Treat as unconfigured. Include warning in response naming which vars are missing. Log `WARNING`. |
| open_in_slicer + no SMTP | Still saves to Downloads (same as full-SMTP + open_in_slicer). |

---

## Response Schema

```json
{
  "status": "ok",
  "delivery": "email" | "local" | "email+local",
  "email_to": "address@..." | null,
  "local_path": "/Users/.../Downloads/<slug>.3mf" | null,
  "warnings": []
}
```

- `email` — SMTP configured, open_in_slicer=false
- `local` — SMTP not configured (or partial)
- `email+local` — SMTP configured, open_in_slicer=true

Legacy fields (`msg`, `recipient`, `stable_path`, `slicer_opened`, `slicer_error`) are preserved for backwards compatibility.

---

## Files Changed

| File | Change |
|---|---|
| `app/app.py` | Added `_smtp_config()` helper (line ~2499). Rewrote `api_generate_plate()` to use it. Bumped `APP_VERSION` v4.58 → **v4.59**. |
| `app/templates/plaque.html` | Success result block switched on `delivery` field (`email` / `local` / `email+local`). Warnings rendered as yellow notices. Description + Tips updated to reflect dual-mode behaviour. |
| `app/tests/test_generate_plate.py` | New file — 11 TDD tests (see table below). |

---

## Red → Green Table

| # | Test | Before | After |
|---|---|---|---|
| 1 | No SMTP → 200, delivery="local" (regression) | RED 500 | GREEN |
| 2 | All SMTP, no slicer → delivery="email", local_path=None | RED KeyError | GREEN |
| 3 | All SMTP, open_in_slicer=true → delivery="email+local" | RED KeyError | GREEN |
| 4 | Partial SMTP (HOST only) → warnings mention USER+PASS | RED 500 | GREEN |
| 5 | Connection refused → HTTP 500 still fires (guard) | already GREEN | GREEN |
| 6 | 3MF failure → HTTP 500 "3MF generation failed:" (guard) | RED (SMTP blocked it first) | GREEN |
| 7 | No lines → HTTP 400 (guard) | already GREEN | GREEN |
| 8 | Local file written, non-zero, ZIP magic | RED 500 | GREEN |
| 9 | `_smtp_config()` all set → missing_vars=[] | RED AttributeError | GREEN |
| 10 | `_smtp_config()` HOST only → missing SMTP_USER + SMTP_PASS | RED AttributeError | GREEN |
| 11 | `_smtp_config()` none set → all three missing | RED AttributeError | GREEN |

**9 RED → 11 GREEN** (tests 5 and 7 were already passing; included as regression guards).

---

## Migration Steps for Thomas

1. The editor auto-reloads on file save (debug=True). Refresh the browser at `http://localhost:5051`.
2. If the process needs bouncing:
   ```sh
   pkill -f 'python.*app.py'
   cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app && python app.py &
   ```
3. Open the **Custom Text Plaque** page. Enter any text and click **Generate** — without SMTP configured it will now succeed, showing "Saved to ~/Downloads/…" in the result card.
4. Check `~/Downloads/` for the `.3mf` file.

---

## Follow-Up: Other Routes That Assume Email Delivery

Grepped `app/app.py` for every `smtplib`, `SMTP_HOST`, `EmailMessage`, and `send_message` reference.

**Result: `api_generate_plate` is the only SMTP consumer in the codebase.** No other routes require this treatment.

The `_smtp_config()` helper is now available for future routes if email delivery is added elsewhere.
