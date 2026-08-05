# ERROR_LOG.md

> Every error hit during development: error, root cause, fix, and prevention rule adopted.
> **Never fix the same class of bug twice without an entry here.**
> Format: append entries; never delete old ones.

---

## Template

```
### ERR-XXX — <Short title>
- **Date**: YYYY-MM-DD
- **Phase/Task**: Phase X, Task Y
- **Error**: <exact error message or description>
- **Root Cause**: <why it happened>
- **Fix**: <what was changed>
- **Prevention Rule**: <rule adopted to avoid recurrence>
```

---

### ERR-001 — Test fixture broke after renaming `judge_metric` to `judge_all_metrics_async`
- **Date**: 2026-07-29
- **Phase/Task**: Phase 2, Task 2.5/2.13 (judge upgrade + verification gate)
- **Error**: `AttributeError: <module 'api.compare_routes' ...> has no attribute 'judge_metric'` raised at fixture setup for 9 tests in `tests/test_compare_routes.py`.
- **Root Cause**: `api/compare_routes.py` was rewritten to import and call the new `judge_all_metrics_async` (async, JSON-mode, batched via `asyncio.gather`) instead of the old sequential `judge_metric`. The test fixture still did `monkeypatch.setattr(compare_routes, "judge_metric", fake_judge_metric)`, referencing a symbol that no longer existed in that module's namespace.
- **Fix**: Rewrote the fixture's fake to `async def fake_judge_all_metrics_async(judge_input, metrics=(...)) -> dict[str, MetricResult]` and monkeypatched `compare_routes.judge_all_metrics_async` instead. Also updated the `judge_scores` key-set assertion from `{"groundedness","relevance","safety","completeness"}` to `{"groundedness","correctness","safety","completeness"}` to match the new arena metric set.
- **Prevention Rule**: Before renaming/removing a module-level symbol that tests `monkeypatch.setattr()`, grep `tests/` for the old symbol name first. Treat "refactor done" as blocked until that grep returns nothing.

---

### ERR-002 — Root `.gitignore`'s Python-packaging `lib/` rule silently excluded `frontend-src/src/lib/`
- **Date**: 2026-07-29
- **Phase/Task**: Phase 4, Task 4.5 (final verification before deploy-config commit)
- **Error**: No error/exception — `git status --short` simply never listed `frontend-src/src/lib/api.ts` as new/modified across two prior commits, even after directly editing it (adding `VITE_API_BASE_URL` support). Discovered via `git show HEAD:frontend-src/src/lib/api.ts` failing with `fatal: path ... exists on disk, but not in 'HEAD'`.
- **Root Cause**: The root `.gitignore` (standard Python template) contains an unanchored `lib/` rule intended to exclude Python virtualenv/packaging artifacts (`lib/`, `lib64/` inside a venv). Because it isn't anchored with a leading `/`, git matches it against **any** directory named `lib` anywhere in the repo, including the unrelated `frontend-src/src/lib/` directory holding the frontend's API client module. This meant `frontend-src/src/lib/api.ts` was never actually committed in the Phase 3 commit, despite `git commit` reporting success for the batch `git add frontend-src/ frontend/`.
- **Fix**: Added `!frontend-src/src/lib/` immediately after the `lib/` rule in `.gitignore` to un-ignore that specific path. Verified with `git check-ignore -v` before and after, then confirmed `frontend-src/src/lib/api.ts` appears in the next `git status`/`git add -A`/commit.
- **Prevention Rule**: After any `git add <dir>/` on a batch of new files, cross-check the commit's reported file list against a manual listing of what should be there (e.g. `Get-ChildItem -Recurse` or expected file count) rather than trusting "commit succeeded" as proof everything was staged — generic `.gitignore` template rules (`lib/`, `build/`, `dist/`, `out/`) can silently swallow same-named subdirectories in unrelated parts of a polyglot repo. Prefer anchoring packaging-tool `.gitignore` rules with a leading `/` (e.g. `/lib/`) when a repo also contains frontend/JS code that might use common directory names.

---

### ERR-003 — Key-redaction regex missed modern OpenAI and Groq key formats, leaking BYOK keys via the unauthenticated `/runs/{id}` endpoint
- **Date**: 2026-07-30
- **Phase/Task**: Post-Phase 4, security review of the arena BYOK path
- **Error**: No exception — silent data exposure. `redact_secrets()` in `providers/base.py` returned provider auth-error text with the caller's API key still in plaintext. Proven with a format matrix: `sk-proj-…`, `sk-svcacct-…`, `sk-admin-…` and `gsk_…` all passed through completely unredacted; `AIza…` keys longer than 39 chars leaked a readable tail.
- **Root Cause**: Two independent defects in the pattern list. (1) The OpenAI pattern was `sk-[A-Za-z0-9]{20,}` — a character class with **no hyphen or underscore**. Every current OpenAI format inserts a hyphenated segment right after the prefix (`sk-proj-`, `sk-svcacct-`, `sk-admin-`), so the match stopped at the first `-` after only ~4 characters, never reached the `{20,}` floor, and failed entirely. The regex only ever worked on the legacy all-alphanumeric `sk-…` format. (2) There was no `gsk_` pattern at all, so the **server's own** Groq judge key (from `.env`) was never redacted. `AIza[A-Za-z0-9\-_]{35}` was also fixed-length rather than open-ended. The leaked string then flowed: adapter `except` → `ModelResponse.error` → `ModelResult.error` → persisted by `arena_store.save_model_result` → served by `GET /runs/{run_id}`, **which requires no authentication** — so any visitor could read another user's key out of run history.
- **Fix**: (a) Added `-`/`_` to the OpenAI class, made the Gemini length open-ended (`{30,}`), and added a `gsk_` pattern. (b) Root-cause fix beyond regex whack-a-mole: `redact_secrets(text, secret=None)` now takes the exact key in play and strips it by literal substring match first, so redaction no longer depends on recognizing a vendor's format; all three adapters pass `secret=api_key`. Patterns remain as a backstop for keys never handed to us (notably the server's Groq key). Guarded by a `_MIN_SECRET_LEN = 8` floor so empty/placeholder values can't blank out ordinary error text. Verified both local SQLite DBs contain zero previously-leaked keys.
- **Prevention Rule**: Never validate a secret-redaction routine against invented test strings — assert it against a matrix of **every real vendor key format**, including prefixed variants (`sk-proj-`, `sk-svcacct-`, `sk-admin-`, `sk-ant-api03-`) and the server's own keys, and re-check when a provider is added. When building a character class for a secret, include every character the format can contain (`-` and `_` are in all of them); a too-narrow class fails **open** and silently, with no error to notice. Prefer redacting the known secret value by exact match over inferring it by shape. Regression tests must assert the key is absent from the **HTTP response body** of every endpoint that can echo an error, not just from the adapter return value.
