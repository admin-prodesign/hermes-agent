"""TLS for Central Weather Administration hosts only.

Python 3.13+ turns on ``ssl.VERIFY_X509_STRICT``. Certificates in the CWA
chain omit the Subject Key Identifier, so a default context fails with
``CERTIFICATE_VERIFY_FAILED`` / ``Missing Subject Key Identifier``. The
context built here keeps ``CERT_REQUIRED`` and hostname checks and clears
only that flag, and only for ``cwa.gov.tw``.
"""

from __future__ import annotations

import socket
import ssl
import urllib.parse
import urllib.request
from typing import Any

def _is_cwa_host(host: str) -> bool:
    name = host.lower().rstrip(".")
    return name == "cwa.gov.tw" or name.endswith(".cwa.gov.tw")


def _request_host(url: Any) -> str:
    if hasattr(url, "full_url"):
        raw = url.full_url
    elif hasattr(url, "host") and getattr(url, "host", None):
        return str(url.host)
    else:
        raw = url if isinstance(url, str) else ""
    return urllib.parse.urlparse(raw).hostname or ""


def without_x509_strict(context: ssl.SSLContext) -> ssl.SSLContext:
    """Clear ``VERIFY_X509_STRICT`` on a context that still verifies.

    Refuses a context that has verification turned off, so this cannot be
    used to smuggle ``verify=False`` into the CWA fetch.
    """
    if context.verify_mode == ssl.CERT_NONE or not context.check_hostname:
        raise RuntimeError("CWA TLS context must keep certificate verification on")
    flag = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if flag:
        context.verify_flags &= ~flag
    return context


def cwa_ssl_context(cafile: str | None = None) -> ssl.SSLContext:
    """Default verification, minus the strict X.509 flag CWA's chain fails."""
    context = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    return without_x509_strict(context)


def _requests_adapter_cls(requests_module: Any) -> type:
    base = requests_module.adapters.HTTPAdapter

    class CwaHttpsAdapter(base):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._cwa: Any = None

        def ssl_context_for_host(self, host: str) -> ssl.SSLContext | None:
            if _is_cwa_host(host):
                return cwa_ssl_context()
            return None

        def _cwa_adapter(self) -> Any:
            if self._cwa is None:
                adapter = base(
                    pool_connections=self._pool_connections,
                    pool_maxsize=self._pool_maxsize,
                    max_retries=self.max_retries,
                    pool_block=self._pool_block,
                )
                adapter.init_poolmanager(
                    self._pool_connections,
                    self._pool_maxsize,
                    block=self._pool_block,
                    ssl_context=cwa_ssl_context(),
                )
                self._cwa = adapter
            return self._cwa

        def send(self, request: Any, *args: Any, **kwargs: Any) -> Any:
            host = urllib.parse.urlparse(getattr(request, "url", "") or "").hostname or ""
            if _is_cwa_host(host):
                return self._cwa_adapter().send(request, *args, **kwargs)
            return super().send(request, *args, **kwargs)

    return CwaHttpsAdapter


def _install_urllib() -> None:
    current = urllib.request.urlopen
    if getattr(current, "_hermes_cwa_tls", False):
        return

    def urlopen(url, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, *,
                cafile=None, capath=None, cadefault=False, context=None):
        # A caller-supplied context is left alone. The default path for a
        # CWA URL gets the strict-flag exception and nothing else.
        if context is None and cafile is None and capath is None and _is_cwa_host(_request_host(url)):
            context = cwa_ssl_context()
        return current(
            url, data, timeout, cafile=cafile, capath=capath,
            cadefault=cadefault, context=context,
        )

    urlopen._hermes_cwa_tls = True  # type: ignore[attr-defined]
    urllib.request.urlopen = urlopen


def _install_requests() -> None:
    try:
        import requests
        from requests.sessions import Session
    except ImportError:
        return
    if getattr(Session, "_hermes_cwa_tls", False):
        return
    adapter_cls = _requests_adapter_cls(requests)
    original_init = Session.__init__

    def init(self, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        # Longest-prefix match in requests still selects ``https://`` for
        # every CWA subdomain. One routing adapter covers them; other hosts
        # fall through to a normal pool.
        self.mount("https://", adapter_cls())

    Session.__init__ = init  # type: ignore[method-assign]
    Session._hermes_cwa_tls = True  # type: ignore[attr-defined]


def install_cwa_tls() -> None:
    """Mount the CWA context for ``requests`` and ``urllib`` in this process.

    Idempotent. Other hostnames keep the process default context, including
    ``VERIFY_X509_STRICT``.
    """
    _install_urllib()
    _install_requests()
