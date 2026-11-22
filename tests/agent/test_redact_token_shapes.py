"""Token-shape redaction cases that landed with v0.23.3.

Kept out of tests/agent/test_redact.py so that file stays under the line cap.
"""

import logging

import pytest

from agent.redact import RedactingFormatter, redact_sensitive_text


@pytest.fixture(autouse=True)
def _ensure_redaction_enabled(monkeypatch):
    monkeypatch.delenv("HERMES_REDACT_SECRETS", raising=False)
    monkeypatch.setattr("agent.redact._REDACT_ENABLED", True)


def test_grafana_token_prefixes():
    """Bare Grafana service-account / Cloud tokens redact (#150339); look-alikes stay intact."""
    from agent.redact import redact_terminal_output
    # NOTE: prefix + suffix CONCATENATION so no contiguous token literal exists in this file.
    sa_body = "Q7zR4Lm9Xc2Vb5Nw8Kd3Hf6JtPa0Sg7Y"
    cloud_body = "eyJvIjoiMTIzNDU2IiwibiI6InN0YWNrLXRva2VuIiwiayI6Ilo3cTRMbTlYYzJWYjVOdzgifQ"
    for token, body in [
        ("glsa_" + sa_body + "_0123abcd", sa_body),
        ("glsa_" + sa_body, sa_body),
        ("glc_" + cloud_body + "==", cloud_body),
        ("glc_" + cloud_body, cloud_body),
        ("glc_" + cloud_body[:40] + "+/" + cloud_body[40:], cloud_body[40:]),
    ]:
        for out in (redact_sensitive_text(f"$ printf '%s' \"$GRAFANA_TOKEN\"\n{token}\n"),
                    redact_terminal_output(f"{token}\n", "printenv GRAFANA_TOKEN")):
            assert body not in out, f"{token!r} survived redaction: {out!r}"
    for benign in ["glsa_short", "glc_config_loader", "myglsa_" + sa_body,
                   "src/glc_renderer/backend/opengl/shaders/main.frag",
                   "cd /home/u/glc_project/build/release/artifacts/output"]:
        assert redact_sensitive_text(benign) == benign


def test_mixed_case_authorization_header_masked():
    # Regression for #108807: mixed-case header names must still mask Bearer/Basic.
    secret = "SyntheticOpaqueCredential92837465"
    for name in ("aUtHoRiZaTiOn", "pRoXy-AuThOrIzAtIoN", "AUTHORIZATION", "authorization"):
        for scheme in ("Bearer", "Basic"):
            text = f"{name}: {scheme} {secret}"
            result = redact_sensitive_text(text)
            assert secret not in result, text
            assert f"{name}: {scheme}" in result, result


def test_mixed_case_header_via_logging_formatter():
    formatter = RedactingFormatter("%(message)s")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="aUtHoRiZaTiOn: Bearer SyntheticOpaqueCredential92837465",
        args=(), exc_info=None)
    result = formatter.format(record)
    assert "SyntheticOpaqueCredential92837465" not in result
    assert "aUtHoRiZaTiOn: Bearer" in result, result


def test_tavily_environment_scoped_keys_redacted():
    # Current Tavily keys carry a tvly-dev-/tvly-prod- segment (#72925).
    for env in ("dev", "prod"):
        key = "tvly-" + env + "-Ab3dE5fG7hJ9kL1mN2pQ4rS6"
        for text in (f"echo {key} done", f'{{"query": "{key}"}}'):
            result = redact_sensitive_text(text)
            assert "E5fG7hJ9kL1m" not in result, result


def test_hyphenated_tavily_names_are_not_keys():
    for text in ("pip install tvly-python-client", "tvly-config-file"):
        assert redact_sensitive_text(text) == text
