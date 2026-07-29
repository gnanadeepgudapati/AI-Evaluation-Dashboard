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
