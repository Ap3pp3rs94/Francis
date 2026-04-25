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
