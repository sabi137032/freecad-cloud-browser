---
phase: 04-testing-verification
plan: "01"
subsystem: tests
tags: [testing, unit-tests, config-store, file-cache, tdd]
dependency_graph:
  requires: []
  provides: [test-suite-config-store, test-suite-file-cache]
  affects: [core/config_store.py, core/file_cache.py]
tech_stack:
  added: [pytest]
  patterns: [tmp_path fixtures, unittest.mock.patch, TDD]
key_files:
  created:
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_config_store.py
    - tests/test_file_cache.py
  modified: []
decisions:
  - Used unittest.mock.patch("os.replace") to simulate PermissionError without touching real filesystem
  - FileCache._cache_key tested as static method directly on the class
metrics:
  duration: ~5 min
  completed: 2026-05-03
  tasks_completed: 3
  files_created: 4
---

# Phase 04 Plan 01: Unit Tests for ConfigStore and FileCache Summary

**One-liner:** Pytest unit tests for ConfigStore (deepcopy isolation, atomic save, corruption recovery) and FileCache (cache key determinism, ISO-8601/Unix staleness, invalidation) — 21 tests, all pass.

## What Was Built

A `tests/` package with shared fixtures and two test modules verifying the data-layer invariants introduced in Phase 1.

### tests/__init__.py
Empty package marker enabling pytest discovery.

### tests/conftest.py
Two function-scoped fixtures using `tmp_path`:
- `config_store` — `ConfigStore(tmp_path / "cfg" / "config.json")`
- `cache` — `FileCache(str(tmp_path / "cache"))`

### tests/test_config_store.py (10 tests)
| Test | Invariant |
|------|-----------|
| test_config_dir_is_directory | config_dir is a real directory |
| test_list_accounts_empty | fresh store returns [] |
| test_add_and_list | add_account returns UUID; list has 'id' key |
| test_get_account_deepcopy | mutating returned dict doesn't affect store |
| test_list_accounts_deepcopy | mutating list item doesn't affect store |
| test_delete_account | deleted account → get_account returns None |
| test_save_persists | second ConfigStore at same path reads same data |
| test_atomic_save_on_corrupted_json | garbage JSON → empty accounts, no exception |
| test_get_set_setting | settings round-trip and persist across reload |
| test_save_raises_on_permission_error | PermissionError propagated unchanged |

### tests/test_file_cache.py (11 tests)
| Test | Invariant |
|------|-----------|
| test_cache_key_deterministic | same inputs → same 20-char hex key |
| test_cache_key_differs_by_provider | provider name is part of key |
| test_get_local_path_creates_dir | parent dir created on first access |
| test_is_cached_false_when_missing | missing file → False |
| test_is_cached_true_when_file_exists | existing file, no remote_modified → True |
| test_is_cached_stale_when_remote_newer | future ISO-8601 timestamp → False |
| test_is_cached_fresh_when_remote_older | old ISO-8601 timestamp → True |
| test_is_cached_unix_timestamp | remote_modified="0" (epoch), local newer → True |
| test_invalidate_removes_file | invalidate → is_cached False |
| test_clear_provider_removes_dir | clear_provider → directory gone |
| test_cache_size_bytes | two known-size files → sum ≥ 300 bytes |

## Deviations from Plan

**1. [Rule 3 - Blocking Issue] pytest not installed**
- **Found during:** task 1 verification
- **Issue:** `python -m pytest` failed with "No module named pytest"
- **Fix:** Ran `pip install pytest` (installed pytest 9.0.3)
- **Files modified:** none (system dependency)

None in plan logic — all tests implemented exactly as specified.

## Known Stubs

None.

## Threat Flags

None — test files only write to `tmp_path` (OS temp dir), auto-cleaned by pytest. No new network endpoints or auth paths introduced.

## Self-Check

- [x] tests/__init__.py exists
- [x] tests/conftest.py exists with config_store and cache fixtures
- [x] tests/test_config_store.py exists, 10 tests pass
- [x] tests/test_file_cache.py exists, 11 tests pass
- [x] `python -m pytest tests/test_config_store.py tests/test_file_cache.py` → 21 passed

## Self-Check: PASSED
