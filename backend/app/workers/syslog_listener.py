"""Standalone syslog UDP/TCP listener.

Runs as its own process, independent of the FastAPI app (a real deployment
exposes ingestion collectors on a different network path than the API/UI).
Each received message is pushed through the same process_single_log pipeline
the HTTP ingestion route uses, tagged with the real transport ("syslog-udp" /
"syslog-tcp"/"syslog-mtls") instead of the "syslog-http" placeholder the demo
HTTP endpoint uses for anything POSTed to /ingest/syslog.

Usage:
    python -m app.workers.syslog_listener --udp-port 5514 --tcp-port 5514

    # Mutual TLS (ULPF-master-prompt.md Part D2: "so a rogue device cannot
    # inject logs") on the TCP path -- UDP is connectionless and has no TLS
    # handshake to require a client cert during, so mTLS only applies here:
    python -m app.workers.syslog_listener --tcp-port 6514 --disable-udp \
        --tls-cert deploy/dev-ca/server.crt --tls-key deploy/dev-ca/server.key \
        --tls-ca deploy/dev-ca/ca.crt

Binding the standard port 514 requires elevated privileges on most systems;
this defaults to 5514 and expects a real deployment to port-forward or grant
CAP_NET_BIND_SERVICE rather than run the listener as root.
"""
import argparse
import logging
import os
import socketserver
import ssl
import threading

from app.core.database import SessionLocal
from app.api.v1.ingestion import process_single_log

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] syslog_listener: %(message)s")
log = logging.getLogger("syslog_listener")

MAX_MESSAGE_BYTES = 64 * 1024


def _ingest(raw_log: str, protocol: str, peer, device_cn: str = None) -> None:
    raw_log = raw_log.strip()
    if not raw_log:
        return
    db = SessionLocal()
    try:
        # device_cn (the client cert's Common Name, only present when mTLS
        # verified the connection) is the real per-device identity D2 asks
        # for -- source_id stays "UNKNOWN" (no source-registration handshake
        # exists yet), but the verified identity is not discarded: it rides
        # along as the ingestion protocol tag so it's visible on the raw
        # metadata row without inventing a source-mapping feature that
        # doesn't exist.
        tag = f"{protocol}:{device_cn}" if device_cn else protocol
        meta = process_single_log(db, raw_log, "UNKNOWN", tag)
        log.info("ingested %s from %s via %s", meta.event_id, peer, tag)
    except Exception:
        log.exception("failed to ingest message from %s via %s", peer, protocol)
    finally:
        db.close()


def _build_mtls_context(tls_cert: str, tls_key: str, tls_ca: str) -> ssl.SSLContext:
    """CERT_REQUIRED against `tls_ca`: a connecting device without a cert
    signed by this CA fails the TLS handshake before a single byte of log
    content is read -- this is the actual "rogue device cannot inject"
    enforcement, not an application-layer check after the fact."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=tls_cert, keyfile=tls_key)
    context.load_verify_locations(cafile=tls_ca)
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def _client_cn(sslsocket) -> str:
    cert = sslsocket.getpeercert()
    if not cert:
        return None
    for rdn in cert.get("subject", ()):
        for key, value in rdn:
            if key == "commonName":
                return value
    return None


class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        if len(data) > MAX_MESSAGE_BYTES:
            log.warning("dropped oversized UDP datagram from %s (%d bytes)", self.client_address, len(data))
            return
        try:
            raw_log = data.decode("utf-8", errors="replace")
        except Exception:
            return
        _ingest(raw_log, "syslog-udp", self.client_address)


class TCPHandler(socketserver.StreamRequestHandler):
    """Newline-delimited framing (most syslog-over-TCP senders); each line is
    ingested as one message. A production listener would also support RFC 6587
    octet-counting framing -- tracked separately, out of scope for this pass."""

    def handle(self):
        peer = self.client_address
        # When the server is TLS-wrapped (see ThreadedTCPServer), self.request
        # is an ssl.SSLSocket and its peer cert (already verified by the TLS
        # handshake itself before handle() ever runs) carries the device's
        # identity -- attach it to every message from this connection.
        device_cn = _client_cn(self.request) if isinstance(self.request, ssl.SSLSocket) else None
        protocol = "syslog-mtls" if device_cn else "syslog-tcp"
        while True:
            line = self.rfile.readline(MAX_MESSAGE_BYTES + 1)
            if not line:
                break
            if len(line) > MAX_MESSAGE_BYTES:
                log.warning("dropped oversized TCP line from %s", peer)
                continue
            try:
                raw_log = line.decode("utf-8", errors="replace")
            except Exception:
                continue
            _ingest(raw_log, protocol, peer, device_cn)


class ThreadedUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    allow_reuse_address = True


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, tls_context: ssl.SSLContext = None):
        super().__init__(server_address, handler_class)
        self.tls_context = tls_context

    def get_request(self):
        sock, addr = super().get_request()
        if self.tls_context:
            # A device without a cert signed by our CA fails right here --
            # SSLError propagates out of accept-time wrapping, socketserver
            # logs it via handle_error and moves on to the next connection,
            # so one rejected rogue device doesn't take down the listener.
            sock = self.tls_context.wrap_socket(sock, server_side=True)
        return sock, addr


def main():
    parser = argparse.ArgumentParser(description="ULPF syslog UDP/TCP listener")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--udp-port", type=int, default=5514)
    parser.add_argument("--tcp-port", type=int, default=5514)
    parser.add_argument("--disable-udp", action="store_true")
    parser.add_argument("--disable-tcp", action="store_true")
    parser.add_argument("--tls-cert", default=os.getenv("SYSLOG_TLS_CERT"),
                         help="Server cert for mutual TLS on the TCP listener (requires --tls-key and --tls-ca; env: SYSLOG_TLS_CERT)")
    parser.add_argument("--tls-key", default=os.getenv("SYSLOG_TLS_KEY"),
                         help="Server private key matching --tls-cert (env: SYSLOG_TLS_KEY)")
    parser.add_argument("--tls-ca", default=os.getenv("SYSLOG_TLS_CA"),
                         help="CA cert used to verify client (device) certs -- a device without a cert signed by this CA cannot connect (env: SYSLOG_TLS_CA)")
    args = parser.parse_args()

    tls_context = None
    if args.tls_cert or args.tls_key or args.tls_ca:
        if not (args.tls_cert and args.tls_key and args.tls_ca):
            parser.error("--tls-cert, --tls-key, and --tls-ca must all be given together")
        tls_context = _build_mtls_context(args.tls_cert, args.tls_key, args.tls_ca)
        log.info("mutual TLS enabled on the TCP listener -- devices without a cert signed by %s will be rejected at the TLS handshake", args.tls_ca)

    threads = []
    if not args.disable_udp:
        udp_server = ThreadedUDPServer((args.host, args.udp_port), UDPHandler)
        t = threading.Thread(target=udp_server.serve_forever, daemon=True, name="syslog-udp")
        t.start()
        threads.append(t)
        log.info("listening for syslog UDP on %s:%d (no TLS -- UDP is connectionless, mTLS applies to the TCP listener only)", args.host, args.udp_port)

    if not args.disable_tcp:
        tcp_server = ThreadedTCPServer((args.host, args.tcp_port), TCPHandler, tls_context=tls_context)
        t = threading.Thread(target=tcp_server.serve_forever, daemon=True, name="syslog-tcp")
        t.start()
        threads.append(t)
        log.info("listening for syslog TCP on %s:%d (mTLS=%s)", args.host, args.tcp_port, bool(tls_context))

    if not threads:
        log.error("both --disable-udp and --disable-tcp given -- nothing to listen on")
        return

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
