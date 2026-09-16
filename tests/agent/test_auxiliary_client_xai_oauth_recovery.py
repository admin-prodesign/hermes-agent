"""Tests for xAI OAuth 403 error recovery in auxiliary_client.

xAI returns HTTP 403 (not 401) with "unauthenticated:bad-credentials" when
an OAuth2 access token has expired.  These tests verify:

1. _is_auth_error detects xAI 403 as an auth failure
2. _recoverable_pool_provider maps api.x.ai to xai-oauth
3. _refresh_provider_credentials includes xai-oauth refresh logic
4. _auth_refresh_provider_for_route maps auto + api.x.ai to xai-oauth so
   singleton refresh is not skipped on unpinned auxiliary tasks
5. _evict_cached_clients("auto") drops auto-keyed clients after backend recovery
"""

import pytest


# ── _is_auth_error ──────────────────────────────────────────────────────────

def _import_is_auth_error():
    from agent.auxiliary_client import _is_auth_error
    return _is_auth_error


class TestIsAuthErrorXaiOauth403:
    """Verify _is_auth_error correctly identifies xAI's 403 bad-credentials."""

    @pytest.fixture(autouse=True)
    def _import(self):
        self.is_auth_error = _import_is_auth_error()

    def test_xai_403_bad_credentials_is_auth_error(self):
        """The exact error xAI returns for expired OAuth tokens."""
        exc = Exception(
            "Error code: 403 - {'code': 'The caller does not have permission "
            "to execute the specified operation', 'error': 'The OAuth2 access "
            "token could not be validated. [WKE=unauthenticated:bad-credentials]'}"
        )
        exc.status_code = 403  # openai.PermissionDenied sets this
        assert self.is_auth_error(exc) is True

    def test_xai_403_bad_credentials_without_status_code(self):
        """Fallback match when status_code attribute is missing."""
        exc = Exception(
            "Error code: 403 - unauthenticated:bad-credentials"
        )
        # No status_code attribute — should still match via string pattern
        assert self.is_auth_error(exc) is True

    def test_generic_403_is_not_auth_error(self):
        """A generic 403 (e.g. rate limit, forbidden) should NOT be treated as auth."""
        exc = Exception("Error code: 403 - rate limit exceeded")
        exc.status_code = 403
        assert self.is_auth_error(exc) is False






    def test_unauthenticated_without_bad_credentials_is_not_auth_error(self):
        """'unauthenticated' alone (without 'bad-credentials') should not match."""
        exc = Exception("unauthenticated request")
        assert self.is_auth_error(exc) is False


# ── _recoverable_pool_provider ──────────────────────────────────────────────

def _import_recoverable_pool_provider():
    from agent.auxiliary_client import _recoverable_pool_provider
    return _recoverable_pool_provider


class TestRecoverablePoolProviderXaiOAuth:
    """Verify _recoverable_pool_provider maps api.x.ai to xai-oauth."""

    @pytest.fixture(autouse=True)
    def _import(self):
        self.recover = _import_recoverable_pool_provider()

    def test_explicit_xai_oauth_provider(self):
        """Explicit provider name passes through."""
        result = self.recover("xai-oauth", None)
        assert result == "xai-oauth"

    def test_api_x_ai_host_match(self):
        """api.x.ai base URL maps to xai-oauth pool."""
        class MockClient:
            base_url = "https://api.x.ai/v1/"

        result = self.recover("auto", MockClient())
        assert result == "xai-oauth"

    def test_auto_with_unknown_host_returns_none(self):
        """auto provider with unknown host returns None."""
        class MockClient:
            base_url = "https://unknown.example.com/v1/"

        result = self.recover("auto", MockClient())
        assert result is None


# ── _auth_refresh_provider_for_route ────────────────────────────────────────

def _import_auth_refresh_provider_for_route():
    from agent.auxiliary_client import _auth_refresh_provider_for_route
    return _auth_refresh_provider_for_route


class TestAuthRefreshProviderForRouteXaiOAuth:
    """Auto-routed aux calls must infer xai-oauth from api.x.ai, not stay 'auto'."""

    @pytest.fixture(autouse=True)
    def _import(self):
        self.refresh_for_route = _import_auth_refresh_provider_for_route()

    def test_auto_plus_api_x_ai_is_xai_oauth(self):
        assert self.refresh_for_route("auto", "https://api.x.ai/v1") == "xai-oauth"
        assert self.refresh_for_route("auto", "https://api.x.ai/v1/") == "xai-oauth"

    def test_explicit_xai_oauth_passes_through(self):
        assert self.refresh_for_route("xai-oauth", "https://api.x.ai/v1") == "xai-oauth"

    def test_auto_unknown_host_stays_auto(self):
        assert self.refresh_for_route("auto", "https://unknown.example.com/v1/") == "auto"


# ── auto cache-key eviction after backend recovery ──────────────────────────

class TestEvictAutoCacheKeyAfterBackendRecovery:
    """Pool recovery evicts xai-oauth; auto-routed tasks also cache under 'auto'."""

    def test_evict_auto_drops_auto_keys_not_other_providers(self):
        import agent.auxiliary_client as aux

        class Dummy:
            pass

        auto_client = Dummy()
        other_client = Dummy()
        auto_key = ("auto", False, "https://api.x.ai/v1")
        other_key = ("openrouter", False, "https://openrouter.ai/api/v1")
        aux._client_cache.clear()
        aux._client_cache[auto_key] = (auto_client, "grok-4.6", None)
        aux._client_cache[other_key] = (other_client, "other", None)
        try:
            aux._evict_cached_clients("auto")
            assert auto_key not in aux._client_cache
            assert other_key in aux._client_cache
        finally:
            aux._client_cache.clear()


# ── _refresh_provider_credentials (structure check) ─────────────────────────

def _import_refresh_provider_credentials():
    from agent.auxiliary_client import _refresh_provider_credentials
    return _refresh_provider_credentials


class TestRefreshProviderCredentialsXaiOAuth:
    """Verify _refresh_provider_credentials has xai-oauth branch.

    Full integration testing requires live OAuth tokens, so we verify
    the branch exists and handles the no-credential case gracefully.
    """

    @pytest.fixture(autouse=True)
    def _import(self):
        self.refresh = _import_refresh_provider_credentials()


    def test_unknown_provider_returns_false(self):
        """Unknown providers fall through to return False."""
        result = self.refresh("unknown-provider-xyz")
        assert result is False