# tests/test_auth_manager.py
# Unit tests for AuthManager — three-tier credential storage:
#   keyring → Fernet → base64

import json
import base64
import pytest
from unittest.mock import MagicMock, patch
from core.auth_manager import AuthManager, SERVICE_NAME

# _is_sensitive is a static method on AuthManager
_is_sensitive = AuthManager._is_sensitive


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_auth(config_store):
    """Return an AuthManager backed by the given config_store."""
    return AuthManager(config_store)


def make_keyring_mock():
    """Return an in-memory keyring mock that behaves like the real API."""
    kr = MagicMock()
    store = {}
    kr.get_password.side_effect = lambda svc, acct: store.get((svc, acct))
    kr.set_password.side_effect = lambda svc, acct, val: store.update({(svc, acct): val})
    kr.delete_password.side_effect = lambda svc, acct: store.pop((svc, acct), None)
    return kr


ACCOUNT_ID = "test-account-1"


# ---------------------------------------------------------------------------
# _is_sensitive tests
# ---------------------------------------------------------------------------

def test_is_sensitive_true():
    """Keys ending in sensitive suffixes should return True."""
    assert _is_sensitive("client_secret") is True
    assert _is_sensitive("admin_password") is True
    assert _is_sensitive("access_token") is True
    assert _is_sensitive("api_key") is True
    assert _is_sensitive("service_account_json") is True
    assert _is_sensitive("token_cache_json") is True


def test_is_sensitive_false():
    """Non-sensitive keys should return False."""
    assert _is_sensitive("name") is False
    assert _is_sensitive("email") is False
    assert _is_sensitive("bucket") is False
    assert _is_sensitive("provider") is False
    assert _is_sensitive("folder_id") is False


def test_is_sensitive_case_insensitive():
    """Suffix matching should be case-insensitive."""
    assert _is_sensitive("Access_Token") is True
    assert _is_sensitive("CLIENT_SECRET") is True
    assert _is_sensitive("Admin_Password") is True


# ---------------------------------------------------------------------------
# Keyring tier tests
# ---------------------------------------------------------------------------

def test_save_load_keyring(config_store):
    """save_credentials stores sensitive fields via keyring; load_credentials merges them."""
    kr = make_keyring_mock()
    with patch("core.auth_manager._get_keyring", return_value=kr):
        auth = make_auth(config_store)
        auth.save_credentials(ACCOUNT_ID, {
            "bucket": "my-bucket",
            "access_token": "tok123",
        })

        # keyring.set_password should have been called with the sensitive field
        assert kr.set_password.called
        call_args = kr.set_password.call_args
        assert call_args[0][0] == SERVICE_NAME
        assert call_args[0][1] == ACCOUNT_ID
        payload = json.loads(call_args[0][2])
        assert payload["access_token"] == "tok123"

        # load_credentials should return the plaintext token
        loaded = auth.load_credentials(ACCOUNT_ID)
        assert loaded["access_token"] == "tok123"
        assert loaded["bucket"] == "my-bucket"


def test_delete_credentials_calls_keyring_delete(config_store):
    """delete_credentials calls keyring.delete_password for the account."""
    kr = make_keyring_mock()
    with patch("core.auth_manager._get_keyring", return_value=kr):
        auth = make_auth(config_store)
        auth.save_credentials(ACCOUNT_ID, {"access_token": "tok-del"})
        auth.delete_credentials(ACCOUNT_ID)

        kr.delete_password.assert_called_with(SERVICE_NAME, ACCOUNT_ID)


# ---------------------------------------------------------------------------
# Fernet tier tests
# ---------------------------------------------------------------------------

def test_save_load_fernet(config_store):
    """When keyring is absent, sensitive fields are Fernet-encrypted in config."""
    with patch("core.auth_manager._get_keyring", return_value=None):
        auth = make_auth(config_store)
        auth.save_credentials(ACCOUNT_ID, {
            "bucket": "fernet-bucket",
            "access_token": "fernet-tok",
        })

        # Config store should contain a '_sensitive_fernet' field, not plaintext
        raw = config_store.get_account(ACCOUNT_ID)
        assert "_sensitive_fernet" in raw, "Expected _sensitive_fernet in config after Fernet save"
        assert "access_token" not in raw, "Plaintext token must not be stored in config"

        # load_credentials must return the decrypted plaintext token
        loaded = auth.load_credentials(ACCOUNT_ID)
        assert loaded["access_token"] == "fernet-tok"
        assert loaded["bucket"] == "fernet-bucket"


def test_fernet_field_not_in_loaded_result(config_store):
    """After load_credentials with Fernet path, '_sensitive_fernet' must not be in the result."""
    with patch("core.auth_manager._get_keyring", return_value=None):
        auth = make_auth(config_store)
        auth.save_credentials(ACCOUNT_ID, {"api_key": "secret-key"})

        loaded = auth.load_credentials(ACCOUNT_ID)
        assert "_sensitive_fernet" not in loaded


# ---------------------------------------------------------------------------
# Base64 fallback tests
# ---------------------------------------------------------------------------

def test_save_load_base64(config_store):
    """When keyring and cryptography are both absent, base64 fallback is used."""
    with patch("core.auth_manager._get_keyring", return_value=None), \
         patch("core.auth_manager._try_fernet_encrypt", return_value=None), \
         patch("core.auth_manager._try_fernet_decrypt", return_value=None):
        auth = make_auth(config_store)
        auth.save_credentials(ACCOUNT_ID, {
            "bucket": "b64-bucket",
            "access_token": "b64-tok",
        })

        # Config store must have '_sensitive_b64'
        raw = config_store.get_account(ACCOUNT_ID)
        assert "_sensitive_b64" in raw, "Expected _sensitive_b64 in config after base64 save"

        # load_credentials must return the decoded plaintext
        loaded = auth.load_credentials(ACCOUNT_ID)
        assert loaded["access_token"] == "b64-tok"
        assert loaded["bucket"] == "b64-bucket"


# ---------------------------------------------------------------------------
# Non-sensitive fields round-trip
# ---------------------------------------------------------------------------

def test_non_sensitive_fields_in_config(config_store):
    """
    Non-sensitive fields appear directly in config; sensitive fields do NOT
    appear as plaintext in config (whether stored via keyring, Fernet, or b64).
    """
    kr = make_keyring_mock()
    with patch("core.auth_manager._get_keyring", return_value=kr):
        auth = make_auth(config_store)
        auth.save_credentials(ACCOUNT_ID, {
            "bucket": "public-bucket",
            "access_token": "super-secret",
        })

        raw = config_store.get_account(ACCOUNT_ID)
        # Non-sensitive key present directly
        assert raw.get("bucket") == "public-bucket"
        # Sensitive key NOT present as plaintext
        assert "access_token" not in raw


# ---------------------------------------------------------------------------
# update_token tests
# ---------------------------------------------------------------------------

def test_update_token_delegates(config_store):
    """update_token delegates to save_credentials; load_credentials returns new value."""
    kr = make_keyring_mock()
    with patch("core.auth_manager._get_keyring", return_value=kr):
        auth = make_auth(config_store)

        # Initial save
        auth.save_credentials(ACCOUNT_ID, {"access_token": "old-tok", "bucket": "b"})

        # Update the token
        auth.update_token(ACCOUNT_ID, {"access_token": "new-tok"})

        loaded = auth.load_credentials(ACCOUNT_ID)
        assert loaded["access_token"] == "new-tok"
