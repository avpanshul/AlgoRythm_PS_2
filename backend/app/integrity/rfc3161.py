"""RFC 3161 trusted timestamping.

Optional and additive, same honesty pattern as SMS_GATEWAY_URL
(app/core/config.py): if RFC3161_TSA_URL isn't set (the default), checkpoints
get no timestamp token and rfc3161_status is recorded as "not_configured" --
never a fabricated token. When configured, every new checkpoint is
timestamped by a real, independent third-party Time Stamp Authority over the
exact `f"{tree_size}:{root_hash}"` message its own Ed25519/HSM signature
already covers. This closes a real gap a self-signed checkpoint alone can't:
the server's own clock and its own signing key can both be manipulated by
whoever controls the server, but a real external TSA's signed attestation of
"this exact hash existed at this time" cannot be backdated without also
compromising that separate, independent TSA.

Verified end-to-end against two real public TSAs during development
(freetsa.org, timestamp.digicert.com) -- request, decode, and full
`openssl ts -verify` signature-chain verification, documented in
docs/EVIDENCE_STANDARDS.md. Uses `rfc3161ng` for the request (reliable
against both) but shells out to `openssl ts -verify` for full CMS signature
verification rather than that library's own check_timestamp(), which was
found to hard-fail on EC-signed TSA responses (e.g. freetsa.org) and to
reject at least one real RSA-signed response (timestamp.digicert.com) during
testing -- openssl's `ts` subcommand is the standard, widely-trusted tool for
this exact job, and correctly verified both.
"""
import base64
import logging
import os
import shutil
import subprocess
import tempfile

from app.core.config import settings

log = logging.getLogger("rfc3161")


def is_configured() -> bool:
    return bool(settings.RFC3161_TSA_URL)


def request_timestamp(message: bytes) -> dict:
    """Requests a real RFC 3161 timestamp token over `message`. Never raises
    out to the caller -- a checkpoint must still be created even if the TSA
    is unreachable; a missing/failed timestamp is recorded honestly as
    status="failed", not treated as fatal to checkpoint creation."""
    if not is_configured():
        return {"status": "not_configured"}

    try:
        import rfc3161ng
        timestamper = rfc3161ng.RemoteTimestamper(
            settings.RFC3161_TSA_URL, hashname="sha256",
            include_tsa_certificate=True, timeout=settings.RFC3161_TIMEOUT_SECONDS,
        )
        token = timestamper.timestamp(data=message)
        return {
            "status": "obtained",
            "tsa_url": settings.RFC3161_TSA_URL,
            "token_b64": base64.b64encode(token).decode("ascii"),
        }
    except Exception as e:
        log.warning("RFC3161 timestamp request to %s failed: %s", settings.RFC3161_TSA_URL, e)
        return {"status": "failed", "tsa_url": settings.RFC3161_TSA_URL, "error": str(e)}


def decode_token_summary(token_b64: str) -> dict:
    """Dependency-light summary (embedded signing time, serial, policy OID)
    without doing full CMS signature verification -- see verify_with_openssl
    for that. Never raises; a malformed/unparseable token is reported as an
    error field, not an exception."""
    try:
        import rfc3161ng
        from pyasn1.codec.der import decoder
        token_bytes = base64.b64decode(token_b64)
        tst, _rest = decoder.decode(token_bytes, asn1Spec=rfc3161ng.TimeStampToken())
        info = tst.tst_info
        return {
            "genTime": str(info["genTime"]),
            "serialNumber": str(info["serialNumber"]),
            "policy": str(info["policy"]),
        }
    except Exception as e:
        return {"error": str(e)}


def verify_with_openssl(token_b64: str, message: bytes, ca_cert_path: str = None, untrusted_cert_path: str = None) -> dict:
    """Shells out to `openssl ts -verify -token_in` -- see this module's
    docstring for why. Returns {"available": False} if openssl isn't on
    PATH, so callers (e.g. the standalone evidence-bundle verifier) can
    degrade to decode_token_summary()'s basic check instead of crashing."""
    openssl_path = shutil.which("openssl")
    if not openssl_path:
        return {"available": False, "reason": "openssl binary not found on PATH"}

    token_bytes = base64.b64decode(token_b64)
    with tempfile.TemporaryDirectory() as tmp:
        token_path = os.path.join(tmp, "token.tsr")
        data_path = os.path.join(tmp, "data.bin")
        with open(token_path, "wb") as f:
            f.write(token_bytes)
        with open(data_path, "wb") as f:
            f.write(message)

        cmd = [openssl_path, "ts", "-verify", "-token_in", "-in", token_path, "-data", data_path]
        if ca_cert_path:
            cmd += ["-CAfile", ca_cert_path]
        if untrusted_cert_path:
            cmd += ["-untrusted", untrusted_cert_path]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return {
                "available": True,
                "verified": result.returncode == 0 and "Verification: OK" in result.stdout,
                "chain_trust_anchor_configured": bool(ca_cert_path),
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        except Exception as e:
            return {"available": True, "verified": False, "error": str(e)}
