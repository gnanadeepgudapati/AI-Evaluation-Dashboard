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
