# GPS Heightmap — De Laveaga fixture fix

**v0.1.1 — 2026-09-25 — Larry (inline, Topo rate-limited)**

## Result

40/40 tests in `app/tests/test_gps_heightmap.py` green. The 4 `TestRealDataDeLaveaga` setup errors Sienna flagged are gone, and the regression test `test_strips_inline_speech_to_text_contamination` now passes too.

## Root cause

`ItWentIn/De Laveaga GPS from Stracka.txt` had voice-typed prose injected into the middle of the JSON body, on the `altitude` line of the second GPS cell (file line 50):

```
"altitude": 111.5904,Is a path to a text file in JSON format that gives so-called geohash...
```

`json.loads` correctly rejected this at column 30 of body-line 14. The cruft-skip logic was fine — the corruption was inside the JSON.

## Fix — two parts

**1. Cleaned the fixture file** — surgical edit to remove the injected prose, leaving `"altitude": 111.5904,` intact.

**2. Hardened the parser** — `app/gps_heightmap.py` now runs each JSON line through `_CONTAM_RE` before `json.loads`:

```python
_CONTAM_RE = re.compile(r'^(\s*"[^"]+"\s*:\s*-?[\d.eE+]+\s*,)\s*[A-Za-z].*$')
```

Any line that looks like `"key": <number>,<letter>...` gets truncated at the comma. Numeric-value lines only — string values, structural lines, and legitimate `,` followed by whitespace are all untouched.

## Red → green

| Test | Before | After |
|---|---|---|
| `TestRealDataDeLaveaga::test_points_used_greater_than_30` | ERROR (JSONDecode) | ✅ |
| `TestRealDataDeLaveaga::test_heightmap_has_meaningful_variation` | ERROR | ✅ |
| `TestRealDataDeLaveaga::test_no_nan_inside_mask` | ERROR | ✅ |
| `TestRealDataDeLaveaga::test_result_is_heightmap_result_instance` | ERROR | ✅ |
| `TestParseGpsFile::test_strips_inline_speech_to_text_contamination` | (was passing before contamination test suite existed — now passing on strengthened parser) | ✅ |

## Files touched

- `ItWentIn/De Laveaga GPS from Stracka.txt` — one-line prose stripped
- `app/gps_heightmap.py` — `_CONTAM_RE` + preprocess loop; `__version__` already at 0.1.1
- `app/app.py` — `APP_VERSION` v4.60 → v4.61

## Follow-ups

- Check `Stanford (8).gps` for the same class of contamination — if the parser had to swallow anything, we'd want to know before it's already too late.
- Root cause of the injection is likely Wispr Flow / voice typing landing in a text editor with this file open. Not something to fix in code, just something to be aware of.

Task 597 (Larry) + 598 (Topo) both closed in `db/workspace.db`; activity_log entries added.
