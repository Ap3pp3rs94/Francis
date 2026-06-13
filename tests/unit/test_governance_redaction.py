from __future__ import annotations

import json
from pathlib import Path


def test_redact_secret_text_handles_common_token_families() -> None:
    from francis.governance.redaction import REDACTED_SECRET, redact_secret_text

    raw_tokens = [
        "sk-proj-" + ("a" * 48),
        "github_pat_" + ("A" * 64),
        "glpat-" + ("b" * 24),
        "xox" + "b-" + "123456789012-123456789012-abcdefghijklmnop",
        "AIza" + ("C" * 35),
        "eyJabcde.eyJfghij.eyJklmno",
    ]

    redacted = redact_secret_text("operator pasted " + " ".join(raw_tokens))

    for token in raw_tokens:
        assert token not in redacted
    assert redacted.count(REDACTED_SECRET) == len(raw_tokens)


def test_seal_governed_approval_value_seals_known_token_family(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.governance.redaction import redact_governed_display_value, seal_governed_approval_value

    raw_token = "github_pat_" + ("B" * 64)
    value = f"deploy with {raw_token}"
    sealed = seal_governed_approval_value(value, key="operator_command")

    assert sealed["kind"] == "sealed_secret"
    assert sealed["redacted"] == "deploy with [REDACTED:secret]"
    assert str(sealed["digest"]).startswith("hmac-sha256:")
    assert raw_token not in json.dumps(redact_governed_display_value({"command": sealed}), sort_keys=True)


def test_config_keys_containing_secret_substring_are_not_redacted() -> None:
    # False-positive prevention: structural/config keys that merely *contain* a
    # sensitive substring (e.g. "secret") must never be redacted.
    from francis.governance.redaction import (
        redact_governed_display_value,
        redact_governed_value,
        seal_governed_approval_value,
    )

    payload = {
        "secret_storage_allowed": False,
        "store_sensitive_values": False,
        "secret_count": 3,
        "token_budget": 1000,
        "password_policy_enabled": True,
    }

    for fn in (redact_governed_value, redact_governed_display_value, seal_governed_approval_value):
        out = fn(payload)
        assert out == payload, f"{fn.__name__} altered non-sensitive config payload: {out}"


def test_explicit_sensitive_keys_are_redacted() -> None:
    # True-positive: an exact sensitive key holding a secret string is redacted.
    from francis.governance.redaction import REDACTED_SECRET, redact_governed_display_value, redact_governed_value

    payload = {"api_key": "abc123def456", "password": "hunter2hunter2", "endpoint": "https://example.test"}

    for fn in (redact_governed_value, redact_governed_display_value):
        out = fn(payload)
        assert out["api_key"] == REDACTED_SECRET
        assert out["password"] == REDACTED_SECRET
        assert "abc123def456" not in json.dumps(out)
        assert "hunter2hunter2" not in json.dumps(out)
        # Non-sensitive sibling preserved exactly.
        assert out["endpoint"] == "https://example.test"


def test_redaction_preserves_schema_keys_and_types() -> None:
    # Structural integrity + type safety: keys are never renamed/replaced, and
    # booleans are never redacted under any condition (even under a sensitive key).
    from francis.governance.redaction import redact_governed_display_value, redact_governed_value

    payload = {
        "api_key": "sk-secret-value-123456",
        "secret_storage_allowed": True,
        "token": True,  # boolean under a sensitive key must stay a boolean
        "retries": 5,
        "nested": {"client_secret": "shh-very-secret-1", "enabled": False},
        "flags": [True, False],
    }

    for fn in (redact_governed_value, redact_governed_display_value):
        out = fn(payload)
        assert set(out.keys()) == set(payload.keys())
        assert set(out["nested"].keys()) == {"client_secret", "enabled"}
        # Booleans untouched, including the one keyed "token".
        assert out["secret_storage_allowed"] is True
        assert out["token"] is True
        assert out["nested"]["enabled"] is False
        assert out["flags"] == [True, False]
        # Numbers untouched.
        assert out["retries"] == 5
        # Sensitive string values masked.
        assert out["api_key"] != "sk-secret-value-123456"
        assert out["nested"]["client_secret"] != "shh-very-secret-1"
