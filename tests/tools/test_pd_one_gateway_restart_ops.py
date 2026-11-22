"""Behaviour contracts for Andy-origin gateway restart safe-ops."""
from __future__ import annotations

import pytest

from tools.pd_one_ops import pd_one_gateway_restart_ops as restart_ops

ANDY_USER_ID = "5nak6m7nmf8kudbrwbtccazbgc"
EMPLOYEE_USER_ID = "abcdefghijklmnopqrstuvwx"
ORIGIN_POST_ID = "zyxwvutsrqponmlkjihgfedcba"


def test_gateway_restart_dry_run_does_not_call_busctl():
    payload = restart_ops.restart_gateway(
        unit_name="hermes-gateway-pdone.service",
        dry_run=True,
    )
    assert payload["mode"] == "dry-run"
    assert payload["writes"] is False
    assert payload["plan"]["would_restart"] is True


def test_gateway_restart_live_calls_fake_busctl(tmp_path, monkeypatch):
    monkeypatch.setattr(restart_ops, "_andy_user_id", lambda: ANDY_USER_ID)
    calls: list[list[str]] = []

    def _fetch(post_id: str) -> dict:
        assert post_id == ORIGIN_POST_ID
        return {
            "id": post_id,
            "user_id": ANDY_USER_ID,
            "delete_at": 0,
            "message": "Please restart hermes-gateway-pdone.service now",
        }

    def _busctl(argv: list[str]) -> dict:
        calls.append(argv)
        return {"returncode": 0, "stdout": "s", "stderr": ""}

    payload = restart_ops.restart_gateway(
        unit_name="hermes-gateway-pdone.service",
        dry_run=False,
        requester_user_id=ANDY_USER_ID,
        origin_post_id=ORIGIN_POST_ID,
        confirm_live_write=restart_ops.LIVE_CONFIRMATION,
        post_fetcher=_fetch,
        busctl_runner=_busctl,
    )
    assert payload["writes"] is True
    assert payload["authorization"]["authorization"] == "andy_origin_post"
    assert len(calls) == 1
    assert calls[0][0:2] == ["busctl", "--user"]
    assert "hermes-gateway-pdone.service" in calls[0]


def test_gateway_restart_rejects_employee_sender(monkeypatch):
    monkeypatch.setattr(restart_ops, "_andy_user_id", lambda: ANDY_USER_ID)
    with pytest.raises(SystemExit):
        restart_ops.restart_gateway(
            unit_name="hermes-gateway.service",
            dry_run=False,
            requester_user_id=EMPLOYEE_USER_ID,
            origin_post_id=ORIGIN_POST_ID,
            confirm_live_write=restart_ops.LIVE_CONFIRMATION,
            post_fetcher=lambda post_id: {
                "id": post_id,
                "user_id": EMPLOYEE_USER_ID,
                "delete_at": 0,
                "message": "restart gateway",
            },
            busctl_runner=lambda argv: {"returncode": 0},
        )