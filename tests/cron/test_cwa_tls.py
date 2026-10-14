"""CWA fetches keep certificate verification and drop only VERIFY_X509_STRICT."""

import socket
import ssl
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cron.cwa_tls import cwa_ssl_context, install_cwa_tls, without_x509_strict


@pytest.fixture(autouse=True)
def _restore_tls_hooks():
    """Keep the CWA mount inside this module. Other tests share the process."""
    saved_urlopen = urllib.request.urlopen
    session_cls = None
    saved_init = None
    saved_flag = None
    try:
        from requests.sessions import Session
    except ImportError:
        pass
    else:
        session_cls = Session
        saved_init = Session.__init__
        saved_flag = getattr(Session, "_hermes_cwa_tls", None)
    yield
    urllib.request.urlopen = saved_urlopen
    if session_cls is not None:
        session_cls.__init__ = saved_init
        if saved_flag is None:
            if hasattr(session_cls, "_hermes_cwa_tls"):
                delattr(session_cls, "_hermes_cwa_tls")
        else:
            session_cls._hermes_cwa_tls = saved_flag

_STRICT = getattr(ssl, "VERIFY_X509_STRICT", 0)


def _assert_verifying(context: ssl.SSLContext) -> None:
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    if _STRICT:
        assert not (context.verify_flags & _STRICT)


def test_cwa_context_clears_strict_and_keeps_verification():
    context = cwa_ssl_context()
    _assert_verifying(context)
    default = ssl.create_default_context()
    if _STRICT and (default.verify_flags & _STRICT):
        assert not (context.verify_flags & _STRICT)


def test_without_x509_strict_refuses_a_context_that_does_not_verify():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with pytest.raises(RuntimeError, match="certificate verification"):
        without_x509_strict(context)


def test_without_x509_strict_refuses_hostname_checks_turned_off():
    context = ssl.create_default_context()
    context.check_hostname = False
    with pytest.raises(RuntimeError, match="certificate verification"):
        without_x509_strict(context)


def _ca_without_subject_key_identifier(tmp_path: Path):
    """CA shape that Python 3.13+ rejects: key usage and AKI, no SKI."""
    cryptography = pytest.importorskip("cryptography")
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "cwa-test-ca")])
    key_usage = x509.KeyUsage(
        digital_signature=False, content_commitment=False, key_encipherment=False,
        data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
        encipher_only=False, decipher_only=False,
    )
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(key_usage, critical=True)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    leaf = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(ca_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=True,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    ca_pem = tmp_path / "ca.pem"
    cert_pem = tmp_path / "cert.pem"
    key_pem = tmp_path / "key.pem"
    ca_pem.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_pem.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_pem.write_bytes(leaf_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    return ca_pem, cert_pem, key_pem, cryptography


def _serve_tls(cert_pem: Path, key_pem: Path):
    raw = socket.socket()
    raw.bind(("127.0.0.1", 0))
    raw.listen(5)
    raw.settimeout(0.5)
    stop = threading.Event()

    def loop():
        server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server.load_cert_chain(cert_pem, key_pem)
        while not stop.is_set():
            try:
                conn, _addr = raw.accept()
            except socket.timeout:
                continue
            try:
                tls = server.wrap_socket(conn, server_side=True)
                tls.recv(16)
                tls.close()
            except Exception:
                pass

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return raw, raw.getsockname()[1], stop, thread


def _handshake(port: int, context: ssl.SSLContext) -> None:
    with socket.create_connection(("127.0.0.1", port), timeout=3) as sock:
        with context.wrap_socket(sock, server_hostname="localhost") as tls:
            tls.send(b"hi")


def test_strict_flag_rejects_ca_missing_ski_and_cwa_context_accepts(tmp_path):
    if not _STRICT:
        pytest.skip("this runtime has no VERIFY_X509_STRICT")
    ca_pem, cert_pem, key_pem, _cryptography = _ca_without_subject_key_identifier(tmp_path)
    _sock, port, stop, thread = _serve_tls(cert_pem, key_pem)
    try:
        strict = ssl.create_default_context(cafile=str(ca_pem))
        strict.verify_flags |= _STRICT
        with pytest.raises(ssl.SSLCertVerificationError, match="Subject Key Identifier"):
            _handshake(port, strict)
        relaxed = cwa_ssl_context(cafile=str(ca_pem))
        _assert_verifying(relaxed)
        _handshake(port, relaxed)
    finally:
        stop.set()
        _sock.close()
        thread.join(timeout=2)


def test_urllib_mount_uses_the_relaxed_context_only_for_cwa(monkeypatch):
    import urllib.request

    captured: list[dict] = []

    def record(url, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, *,
               cafile=None, capath=None, cadefault=False, context=None):
        captured.append({"url": url, "context": context, "cafile": cafile})
        return "ok"

    monkeypatch.setattr(urllib.request, "urlopen", record)
    install_cwa_tls()
    supplied_ctx = ssl.create_default_context()
    urllib.request.urlopen("https://www.cwa.gov.tw/V8/C/P/Typhoon/")
    urllib.request.urlopen("https://example.com/")
    urllib.request.urlopen("https://opendata.cwa.gov.tw/file", context=supplied_ctx)
    cwa, other, supplied = captured
    _assert_verifying(cwa["context"])
    assert other["context"] is None
    # A caller-supplied context is not rewritten, even for a CWA host.
    assert supplied["context"] is supplied_ctx


def test_requests_session_routes_cwa_and_leaves_other_hosts():
    requests = pytest.importorskip("requests")
    from requests.sessions import Session

    install_cwa_tls()
    session = Session()
    try:
        adapter = session.get_adapter("https://www.cwa.gov.tw/V8/")
        cwa = adapter.ssl_context_for_host("opendata.cwa.gov.tw")
        _assert_verifying(cwa)
        assert adapter.ssl_context_for_host("example.com") is None
        assert adapter.ssl_context_for_host("cwa.gov.tw.example.com") is None
    finally:
        session.close()
    assert requests.Session._hermes_cwa_tls is True
