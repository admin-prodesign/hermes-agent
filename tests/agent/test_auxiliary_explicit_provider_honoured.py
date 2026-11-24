"""An explicit ``auxiliary.<task>.provider`` is honoured on every task, vision included.

Regression: ``auxiliary.<task>: {provider: xai-oauth, model: grok-4.20-0309-non-reasoning}`` on a
profile whose main provider is ``openai-codex``. When the xAI grant could not build a client, the
vision path walked the auto chain while keeping the pinned model, so the request went to Codex with
a Grok slug and came back HTTP 400 ("not supported when using Codex"). An unavailable explicit
provider may only fall to the task's own ``fallback_chain``; with none, the call fails naming it.
"""

from __future__ import annotations

import asyncio
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from agent import auxiliary_client as aux
from agent.auxiliary_unavailable import AuxiliaryClientUnavailable

GROK = "grok-4.20-0309-non-reasoning"
TASKS = ("vision", "title_generation", "compression", "mattermost_mention_translation")


def _write_config(home, extra: str = "") -> None:
    blocks = "\n".join(f"  {task}: {{provider: xai-oauth, model: {GROK}{extra}}}" for task in TASKS)
    (home / "config.yaml").write_text(textwrap.dedent("""\
        model:
          provider: openai-codex
          default: gpt-5.5
        auxiliary:
        """) + blocks + "\n", encoding="utf-8")


@pytest.fixture
def codex_only_home(tmp_path, monkeypatch):
    """xAI grant unusable, Codex OAuth healthy: the shape that produced the 400."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path)
    aux._client_cache.clear()
    aux._aux_unhealthy_until.clear()
    with patch.object(aux, "_resolve_xai_oauth_for_aux", return_value=None), \
         patch.object(aux, "_resolve_codex_credential_and_base",
                      return_value=("codex-token", "https://chatgpt.com/backend-api/codex")), \
         patch.object(aux, "_main_model_supports_vision", return_value=True):
        yield tmp_path
    aux._client_cache.clear()


def _prepare(task: str, async_mode: bool):
    return aux._prepare_aux_request(
        task, provider=None, model=None, base_url=None, api_key=None,
        main_runtime=aux._normalize_main_runtime(None), messages=[{"role": "user", "content": "x"}],
        temperature=None, max_tokens=None, tools=None, timeout=None, extra_body=None,
        reasoning_config=None, extra_headers=None, api_mode=None, route_info=None, async_mode=async_mode)


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("task", TASKS)
def test_unavailable_explicit_provider_never_reroutes_to_main(codex_only_home, task, async_mode):
    with pytest.raises(AuxiliaryClientUnavailable, match="xai-oauth"):
        _prepare(task, async_mode)


@pytest.mark.parametrize("task", TASKS)
def test_unavailable_explicit_provider_uses_its_own_fallback_chain(codex_only_home, task):
    _write_config(codex_only_home, ", fallback_chain: [{provider: openrouter, model: x-ai/grok-4}]")
    configured = MagicMock(name="openrouter", base_url="https://openrouter.ai/api/v1")
    with patch.object(aux, "_try_configured_fallback_chain",
                      return_value=(configured, "x-ai/grok-4", "fallback_chain[0](openrouter)")) as chain:
        req = _prepare(task, False)
    chain.assert_called_once()
    assert req.client is configured
    assert (req.request_provider, req.final_model) == ("fallback_chain[0](openrouter)", "x-ai/grok-4")


def test_explicit_vision_call_does_not_reach_codex(codex_only_home):
    """End to end through ``async_call_llm``: nothing is sent to the Codex endpoint."""
    sent = []
    with patch.object(aux, "_acreate_with_progress", side_effect=lambda client, kw, *a, **k: sent.append(kw)):
        with pytest.raises(AuxiliaryClientUnavailable):
            asyncio.run(aux.async_call_llm(task="vision", messages=[{"role": "user", "content": "x"}]))
    assert sent == []
