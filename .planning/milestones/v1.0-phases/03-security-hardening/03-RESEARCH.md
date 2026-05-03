# Phase 3: Security Hardening - Research

**Researched:** 2026-05-03
**Domain:** Python keyring, Fernet encryption, credential migration
**Confidence:** HIGH (all critical claims verified against FreeCAD's bundled Python)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-020 | Fernet key stored in system keyring, not in config directory | keyring confirmed available in FreeCAD's Python; full migration strategy documented below |
</phase_requirements>

---

## Summary

Phase 3 has one concrete requirement: move the Fernet encryption key from `secret.key`
(currently stored in the same config directory as the ciphertext) into the OS keychain via
`keyring`.  This eliminates the "backup or sync the whole AppData folder and you get the key
too" threat model.

Both `keyring` (47.0.0) and `cryptography` (47.0.0) are already bundled with FreeCAD 1.1's
conda-Python 3.11.14 on Windows.  The active backend on Windows is
`keyring.backends.Windows.WinVaultKeyring`, which maps to Windows Credential Manager — a
hardware-backed secrets store.  A set/get/delete round-trip was verified in the FreeCAD
interpreter.

The existing `auth_manager.py` already contains a `_get_fernet_key()` function and the
`_get_keyring()` helper.  The code even has a `# SEC-1` comment explicitly noting the key
co-location problem.  The fix is therefore surgical: modify `_get_fernet_key()` to (1) check
keyring first, (2) generate & store a new key in keyring when none exists, and (3) transparently
migrate any existing `secret.key` / `.credential_key` file on first load.

**Primary recommendation:** Modify `_get_fernet_key()` to use keyring as primary storage for
the Fernet key; keep the file fallback only when keyring raises `NoKeyringError` or
`KeyringLocked`; migrate the on-disk key file to keyring on first successful contact.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `keyring` | 47.0.0 | OS-level secret storage | Bundled with FreeCAD conda Python; maps to Windows Credential Manager / macOS Keychain / libsecret on Linux |
| `cryptography` | 47.0.0 | Fernet symmetric encryption | Already in use; bundled with FreeCAD |

> [VERIFIED: FreeCAD 1.1 bundled Python 3.11.14] Both packages confirmed via
> `"C:\Program Files\FreeCAD 1.1\bin\python.exe" -c "import keyring; import cryptography"`.

### Keyring Backends by Platform
| Platform | Backend | Notes |
|----------|---------|-------|
| Windows | `WinVaultKeyring` (Windows Credential Manager) | Confirmed active in FreeCAD Python |
| macOS | `Keychain` | Standard macOS Keychain |
| Linux | `SecretService` (libsecret/GNOME Keyring) or `KWallet` | May not be available on headless/CI |
| Any (no backend) | `keyring.backends.fail.Keyring` | Raises `NoKeyringError` on all operations |

> [ASSUMED] Linux/macOS backend availability not verified in this session — only Windows was tested.

**Installation (not needed for FreeCAD 1.1):**
```bash
# Both already bundled — only needed for other environments
pip install keyring cryptography
```

---

## Architecture Patterns

### Current Flow (Phase 3 start state)

```
_get_fernet_key(config_dir)
  ├── file exists → read from .credential_key file
  └── no file → generate new key → write .credential_key file
                                  (key lives next to ciphertext ← SEC-1 bug)
```

### Target Flow (Phase 3 end state)

```
_get_fernet_key(config_dir)
  ├── keyring available & has key → return key (migrate file → delete file)
  ├── keyring available, no key, file exists → read file → store in keyring → delete file
  ├── keyring available, no key, no file → generate → store in keyring
  └── keyring unavailable (NoKeyringError / KeyringLocked)
        ├── file exists → read from .credential_key (fallback, log warning)
        └── no file → generate → write .credential_key (fallback, log warning)
```

### Keyring Service / Username Convention

The existing code uses `SERVICE_NAME = "FreeCAD-CloudBrowser"` for storing
*account credentials* (OAuth tokens, API keys) with `username = account_id`.

For the **Fernet key** itself, use a distinct service name to avoid namespace collision:

```python
_KEYRING_SERVICE = "FreeCAD-CloudBrowser"
_KEYRING_FERNET_KEY_ACCOUNT = "fernet_encryption_key"
```

This means:
- Account credentials: `keyring.get_password("FreeCAD-CloudBrowser", "<uuid>")`
- Fernet key: `keyring.get_password("FreeCAD-CloudBrowser", "fernet_encryption_key")`

> [VERIFIED: keyring docs + local test] `keyring` stores/retrieves strings only.
> Fernet keys are already URL-safe base64-encoded bytes (44 ASCII chars) — they can be
> stored directly as strings and decoded back with `.encode()` to `bytes`.

### Fernet Key Round-Trip Pattern

```python
# Fernet.generate_key() returns 44 URL-safe base64 bytes — safe as-is for keyring string API
from cryptography.fernet import Fernet

# Store
key_bytes: bytes = Fernet.generate_key()
keyring.set_password(SERVICE, ACCOUNT, key_bytes.decode("ascii"))

# Retrieve
stored: str = keyring.get_password(SERVICE, ACCOUNT)
key_bytes: bytes = stored.encode("ascii")

# Use
fernet = Fernet(key_bytes)
```

> [VERIFIED: local FreeCAD Python test] Round-trip confirmed; decoded length = 32 bytes.

### Migration Strategy for Existing Users

```python
KEY_FILE_NAMES = (".credential_key", "secret.key")  # both historical names

def _get_fernet_key(config_dir: str) -> bytes:
    kr = _get_keyring()
    if kr is not None:
        try:
            stored = kr.get_password(_KEYRING_SERVICE, _KEYRING_FERNET_KEY_ACCOUNT)
            if stored:
                # Migration: delete any stale key files
                _delete_legacy_key_files(config_dir)
                return stored.encode("ascii")
            # No key in keyring yet — check legacy files
            legacy_key = _load_legacy_key_file(config_dir)
            if legacy_key:
                # Migrate: write to keyring, then delete file
                kr.set_password(_KEYRING_SERVICE, _KEYRING_FERNET_KEY_ACCOUNT,
                                legacy_key.decode("ascii"))
                _delete_legacy_key_files(config_dir)
                logger.info("Migrated Fernet key from file to system keyring.")
                return legacy_key
            # No key anywhere — generate fresh
            key = Fernet.generate_key()
            kr.set_password(_KEYRING_SERVICE, _KEYRING_FERNET_KEY_ACCOUNT,
                            key.decode("ascii"))
            logger.info("Generated new Fernet key; stored in system keyring.")
            return key
        except (keyring.errors.KeyringLocked, keyring.errors.NoKeyringError,
                keyring.errors.KeyringError) as exc:
            logger.warning("Keyring unavailable (%s); falling back to key file.", exc)
    # Fallback: key file
    return _get_or_create_key_file(config_dir)
```

**Important:** Only delete the legacy key file **after** successfully storing in keyring.
Never delete first — if `set_password` raises, the key would be lost.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OS secret storage | Custom encrypted file | `keyring` | Platform-native security, ACLs, hardware-backed on modern Windows |
| Fernet key generation | Custom PBKDF | `Fernet.generate_key()` | Cryptographically correct; no password needed for machine key |
| Atomic file writes | Custom rename logic | Already in `_save()` | Already implemented; don't change |

---

## Common Pitfalls

### Pitfall 1: Deleting Key File Before Keyring Write Confirms
**What goes wrong:** File deleted → `set_password()` raises → key is permanently lost → all
existing credentials become undecryptable.
**How to avoid:** Always write to keyring first, verify no exception, then delete file.

### Pitfall 2: keyring.errors not imported — bare `except Exception`
**What goes wrong:** Swallowing unexpected errors silently.
**How to avoid:** Catch `keyring.errors.KeyringLocked`, `keyring.errors.NoKeyringError`,
and `keyring.errors.KeyringError` explicitly. Let unknown exceptions propagate or log them at
ERROR level.
**Available exception classes:** `KeyringError`, `KeyringLocked`, `NoKeyringError`,
`PasswordSetError`, `PasswordDeleteError` — all in `keyring.errors`.

### Pitfall 3: `keyring` Not Imported at Module Level
**What goes wrong:** `_get_keyring()` already does a lazy import inside a try/except — that
is correct. But mixing `import keyring` at module level in the same file would crash if
keyring is absent.
**How to avoid:** Keep all `keyring` access behind the `_get_keyring()` pattern.

### Pitfall 4: keyring.backends.fail.Keyring Is Active
**What goes wrong:** On headless Linux with no secret service, `keyring.get_keyring()` returns
`keyring.backends.fail.Keyring` which raises `NoKeyringError` on every call.
**How to avoid:** Wrap all keyring calls in `try/except keyring.errors.NoKeyringError` and
fall back to the file-based key.

### Pitfall 5: Re-reading key file after migration
**What goes wrong:** If both the keyring key and a stale key file exist (partial migration
from a previous run that crashed), reading the file key instead of the keyring key would
produce a different key → Fernet decryption fails.
**How to avoid:** In `_get_fernet_key()`, always check keyring first. Delete stale key
files whenever keyring returns a valid key.

### Pitfall 6: `delete_password` raises `PasswordDeleteError` when entry does not exist
**What goes wrong:** Calling `keyring.delete_password()` for a non-existent entry raises
`keyring.errors.PasswordDeleteError` — not silently ignored.
**How to avoid:**
```python
try:
    kr.delete_password(SERVICE, ACCOUNT)
except keyring.errors.PasswordDeleteError:
    pass  # already absent — fine
```
> [VERIFIED: local test in FreeCAD Python]

---

## Other Security Issues in auth_manager.py / config_store.py

After reviewing both files, only one issue is worth fixing in this phase beyond REQ-020:

### SEC-1 (the main issue — REQ-020): Key co-location
Already described above. Fix: `_get_fernet_key()` to keyring.

### SEC-2 (existing, acceptable): Base64 fallback
The existing base64 fallback already logs a very loud `SECURITY WARNING`. This is the
correct behaviour when neither `keyring` nor `cryptography` is available. No change needed.

### SEC-3 (informational only): `_save()` writes a tmp file visible to other processes
`tempfile.mkstemp()` in `config_store._save()` creates a world-readable temp file on some
Linux configurations. This is the Fernet-encrypted JSON, so it's ciphertext, not plaintext.
Low risk. **Recommend: out of scope for this phase** — it is a config store concern and the
data is already encrypted.

### Summary: No other active security bugs found
`config_store.py` is clean for this phase. The scope is exactly: fix `_get_fernet_key()`.

---

## Code Examples

### Pattern: Complete `_get_fernet_key()` replacement

```python
# Source: verified keyring API + FreeCAD Python test 2026-05-03
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_KEYRING_SERVICE = "FreeCAD-CloudBrowser"
_KEYRING_FERNET_KEY_ACCOUNT = "fernet_encryption_key"
_LEGACY_KEY_FILENAMES = (".credential_key", "secret.key")


def _get_keyring():
    """Try to import keyring; return None if not available."""
    try:
        import keyring
        return keyring
    except ImportError:
        return None


def _load_legacy_key_file(config_dir: str) -> Optional[bytes]:
    """Return the bytes from the first legacy key file found, or None."""
    for name in _LEGACY_KEY_FILENAMES:
        path = os.path.join(config_dir, name)
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return f.read()
            except OSError:
                pass
    return None


def _delete_legacy_key_files(config_dir: str) -> None:
    """Remove any legacy on-disk key files after migration to keyring."""
    for name in _LEGACY_KEY_FILENAMES:
        path = os.path.join(config_dir, name)
        try:
            os.unlink(path)
            logger.info("Removed legacy Fernet key file: %s", path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("Could not remove legacy key file %s: %s", path, exc)


def _get_fernet_key(config_dir: str) -> bytes:
    """
    Load or generate the Fernet encryption key.

    Priority:
    1. System keyring (Windows Credential Manager / macOS Keychain / libsecret)
    2. Migrate from legacy .credential_key / secret.key file → keyring
    3. Generate new key → keyring
    4. Fallback to key file when keyring is unavailable/locked (logs warning)
    """
    from cryptography.fernet import Fernet

    kr = _get_keyring()
    if kr is not None:
        try:
            import keyring.errors as _ke
            stored = kr.get_password(_KEYRING_SERVICE, _KEYRING_FERNET_KEY_ACCOUNT)
            if stored:
                # Keyring has the key — clean up any stale file from old installs
                _delete_legacy_key_files(config_dir)
                return stored.encode("ascii")

            # No key in keyring yet
            legacy = _load_legacy_key_file(config_dir)
            if legacy is not None:
                # Migrate: store in keyring, then delete file
                kr.set_password(
                    _KEYRING_SERVICE, _KEYRING_FERNET_KEY_ACCOUNT,
                    legacy.decode("ascii"),
                )
                _delete_legacy_key_files(config_dir)
                logger.info(
                    "Migrated Fernet encryption key from file to system keyring."
                )
                return legacy

            # Generate a brand-new key and store in keyring
            key = Fernet.generate_key()
            kr.set_password(
                _KEYRING_SERVICE, _KEYRING_FERNET_KEY_ACCOUNT,
                key.decode("ascii"),
            )
            logger.info("Generated new Fernet key; stored securely in system keyring.")
            return key

        except (_ke.KeyringLocked, _ke.NoKeyringError, _ke.KeyringError) as exc:
            logger.warning(
                "System keyring unavailable (%s). "
                "Falling back to on-disk key file — credentials are less secure. "
                "Ensure a keyring backend is available for full protection.",
                exc,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Unexpected keyring error (%s). Falling back to on-disk key file.",
                exc,
            )

    # Fallback: on-disk key file
    legacy = _load_legacy_key_file(config_dir)
    if legacy is not None:
        return legacy

    key_path = os.path.join(config_dir, ".credential_key")
    key = Fernet.generate_key()
    logger.warning(
        "System keyring not available. Storing Fernet key at %s. "
        "Install a keyring backend for stronger protection.",
        key_path,
    )
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key
```

### Pattern: Exception handling for `delete_password`

```python
# Safely delete a keyring entry that may or may not exist
try:
    kr.delete_password(SERVICE_NAME, account_id)
except keyring.errors.PasswordDeleteError:
    pass  # already absent
except (keyring.errors.KeyringLocked, keyring.errors.KeyringError) as exc:
    logger.warning("Could not delete keyring entry for %s: %s", account_id, exc)
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Not yet established (Phase 4 adds tests) |
| Quick run command | N/A — Phase 4 |
| Notes | Phase 3 is code-only; Phase 4 will add tests for `auth_manager` |

### Manual Verification Steps for Phase 3
1. Delete any existing `.credential_key` / `secret.key` in the config dir
2. Launch FreeCAD, add a cloud account — verify key appears in Windows Credential Manager
   under "FreeCAD-CloudBrowser / fernet_encryption_key"
3. Restart FreeCAD — verify credentials still load correctly
4. **Migration test:** Create a `.credential_key` file manually, restart FreeCAD — verify it
   is migrated to keyring and the file is deleted
5. **Fallback test:** Set `keyring` to use the fail backend and verify key file is created
   with warning logged

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `keyring` | Fernet key storage in OS keychain | ✓ | 47.0.0 | On-disk `.credential_key` file |
| `cryptography` | Fernet encryption | ✓ | 47.0.0 | Base64 fallback (already implemented) |
| Windows Credential Manager | WinVaultKeyring backend | ✓ | Built-in | — |

> [VERIFIED: FreeCAD 1.1 bundled Python on Windows 2026-05-03]

**Linux / macOS note:** `keyring` is bundled but the active backend depends on the desktop
environment. Headless Linux will get `keyring.backends.fail.Keyring` → `NoKeyringError` →
falls back to key file. This is acceptable behaviour. [ASSUMED — not verified in this session]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Linux / macOS keyring backends work correctly in FreeCAD's bundled Python | Environment Availability | Users on those platforms may get unexpected errors; fallback to key file would still work |
| A2 | Fernet keys from existing installs are stored as raw bytes (not base64-encoded) in the `.credential_key` file | Migration strategy | If stored differently, `legacy.decode("ascii")` would fail; handle with try/except |

---

## Open Questions (RESOLVED)

1. **Is `.credential_key` always valid ASCII / base64?**
   - What we know: `Fernet.generate_key()` returns 44 URL-safe base64 bytes — always valid ASCII
   - What's unclear: If a user manually edited or corrupted the file
   - Recommendation: Wrap `legacy.decode("ascii")` in a try/except; if it fails, generate a new key and re-encrypt credentials
   - **RESOLVED:** `UnicodeDecodeError` is caught in `_get_fernet_key()`; a fresh key is generated on a corrupt file. Implemented in plan 03-01 Task 1 action block.

2. **Should the Fernet key account name be user-scoped?**
   - What we know: `SERVICE_NAME = "FreeCAD-CloudBrowser"` is already global; keyring allows multiple "usernames" per service
   - What's unclear: Whether multi-user Windows machines could collide (each Windows user has their own Credential Manager vault, so no collision)
   - Recommendation: `"fernet_encryption_key"` as the account/username is sufficient; no per-user scoping needed
   - **RESOLVED:** Global account name `"fernet_encryption_key"` is sufficient — Windows Credential Manager is per-user-scoped by the OS; no collision possible.

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: FreeCAD 1.1 bundled Python] `keyring` 47.0.0, `cryptography` 47.0.0 both present and functional — tested 2026-05-03
- [VERIFIED: local Python test] `keyring.backends.Windows.WinVaultKeyring` active; set/get/delete round-trip confirmed
- [VERIFIED: local Python test] `Fernet.generate_key()` produces 44 ASCII-safe bytes; `.decode("ascii")` safe for keyring string API
- [VERIFIED: local Python test] `keyring.delete_password()` raises `PasswordDeleteError` for non-existent entries

### Secondary (MEDIUM confidence)
- [ASSUMED] `keyring` Linux/macOS behaviour — based on keyring library documentation, not tested in this session

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified in FreeCAD's actual bundled Python
- Architecture: HIGH — based on reading existing source code + verified keyring API behaviour
- Migration strategy: HIGH — logic derived from verified API; see Assumption A2 for one edge case
- Pitfalls: HIGH — Pitfalls 1, 4, 6 verified by direct testing; others from code reading

**Research date:** 2026-05-03
**Valid until:** 2026-11-03 (6 months — `keyring` API is very stable)
