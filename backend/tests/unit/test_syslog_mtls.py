"""Tests for mutual TLS on the syslog TCP collector path (Part D2). Builds a
throwaway CA + server + device certs in memory with the `cryptography`
library (already a project dependency) rather than shelling out to openssl
or depending on deploy/dev-ca's gitignored files, so this runs anywhere.

The live, end-to-end proof (a real device cert accepted and ingested with
its identity attached, a device with no cert rejected at the TLS handshake)
was run manually against deploy/dev-ca's real generated certs and the real
syslog_listener.py server over an actual socket -- see docs/PKI.md for that
result. These tests cover the same logic at the unit level so it's checked
by the normal test suite, not only by hand.
"""
import datetime
import socket
import ssl
import sys
import os
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.workers.syslog_listener import _build_mtls_context, _client_cn


def _make_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _self_signed_ca(cn="Test Dev CA"):
    key = _make_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _issue(ca_key, ca_cert, cn, san_localhost=False):
    key = _make_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(ca_cert.subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
    )
    if san_localhost:
        builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
    cert = builder.sign(ca_key, hashes.SHA256())
    return key, cert


def _write_pem(path, key=None, cert=None):
    with open(path, "wb") as f:
        if cert is not None:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        if key is not None:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))


class TestMtlsContext:
    def test_context_requires_client_certs(self, tmp_path):
        ca_key, ca_cert = _self_signed_ca()
        server_key, server_cert = _issue(ca_key, ca_cert, "localhost", san_localhost=True)

        ca_path = tmp_path / "ca.crt"
        server_cert_path = tmp_path / "server.crt"
        server_key_path = tmp_path / "server.key"
        _write_pem(ca_path, cert=ca_cert)
        _write_pem(server_cert_path, cert=server_cert)
        _write_pem(server_key_path, key=server_key)

        context = _build_mtls_context(str(server_cert_path), str(server_key_path), str(ca_path))
        assert context.verify_mode == ssl.CERT_REQUIRED


class TestMtlsHandshakeOverARealSocket:
    """Exercises _build_mtls_context and _client_cn over a genuine TCP
    socket + TLS handshake (loopback), not a mock -- the same mechanism
    app/workers/syslog_listener.py's ThreadedTCPServer.get_request() uses."""

    def _setup_pki(self, tmp_path):
        ca_key, ca_cert = _self_signed_ca()
        server_key, server_cert = _issue(ca_key, ca_cert, "localhost", san_localhost=True)
        device_key, device_cert = _issue(ca_key, ca_cert, "test-device-1")

        paths = {}
        for name, key, cert in [
            ("ca", None, ca_cert), ("server", server_key, server_cert),
            ("device", device_key, device_cert),
        ]:
            p = tmp_path / f"{name}.pem"
            _write_pem(p, key=key, cert=cert)
            paths[name] = str(p)
        return paths

    def test_connection_without_client_cert_is_rejected(self, tmp_path):
        paths = self._setup_pki(tmp_path)
        server_context = _build_mtls_context(paths["server"], paths["server"], paths["ca"])

        raw_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_server.bind(("127.0.0.1", 0))
        raw_server.listen(1)
        port = raw_server.getsockname()[1]

        server_error = {}

        def accept_once():
            conn, _ = raw_server.accept()
            try:
                server_context.wrap_socket(conn, server_side=True)
            except ssl.SSLError as e:
                server_error["error"] = e
            finally:
                conn.close()

        t = threading.Thread(target=accept_once, daemon=True)
        t.start()
        time.sleep(0.1)

        client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        client_context.check_hostname = False
        client_context.verify_mode = ssl.CERT_NONE  # client doesn't even bother verifying the server for this test
        raw_client = socket.create_connection(("127.0.0.1", port), timeout=2)
        try:
            with client_context.wrap_socket(raw_client) as tls_client:
                # The handshake itself should fail server-side (no client cert
                # presented) -- reading from the client socket should error too.
                try:
                    tls_client.recv(1)
                except (ssl.SSLError, ConnectionResetError, OSError):
                    pass
        except (ssl.SSLError, ConnectionResetError, OSError):
            pass

        t.join(timeout=2)
        raw_server.close()
        assert "error" in server_error  # server-side handshake was rejected

    def test_connection_with_valid_device_cert_succeeds_and_identity_is_readable(self, tmp_path):
        paths = self._setup_pki(tmp_path)
        server_context = _build_mtls_context(paths["server"], paths["server"], paths["ca"])

        raw_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_server.bind(("127.0.0.1", 0))
        raw_server.listen(1)
        port = raw_server.getsockname()[1]

        result = {}

        def accept_once():
            conn, _ = raw_server.accept()
            tls_conn = server_context.wrap_socket(conn, server_side=True)
            result["cn"] = _client_cn(tls_conn)
            tls_conn.sendall(b"ok")
            tls_conn.close()

        t = threading.Thread(target=accept_once, daemon=True)
        t.start()
        time.sleep(0.1)

        client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        client_context.check_hostname = False
        client_context.verify_mode = ssl.CERT_NONE
        client_context.load_cert_chain(certfile=paths["device"], keyfile=paths["device"])

        raw_client = socket.create_connection(("127.0.0.1", port), timeout=2)
        with client_context.wrap_socket(raw_client, server_hostname="localhost") as tls_client:
            data = tls_client.recv(2)
            assert data == b"ok"

        t.join(timeout=2)
        raw_server.close()
        assert result["cn"] == "test-device-1"  # the real per-device identity, read from the verified cert
