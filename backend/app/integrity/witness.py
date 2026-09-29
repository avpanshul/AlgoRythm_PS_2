"""Multi-party checkpoint witnessing.

A checkpoint signed only by this server's own key proves "the server that
holds this key attests to this root" -- but if that one key is compromised,
an attacker can both rewrite history AND re-sign the forged checkpoint,
leaving no cryptographic trace. Witnessing adds a second, independent
signature over the same (tree_size, root_hash) message from a second key,
so a forgery now requires compromising both.

Two witness sources, both real (never a fabricated/placeholder signature):

- "local": a second Ed25519 keypair, generated and stored the same
  file-backed way app/integrity/signing.py's demo-grade key is (a distinct
  PEM file, data/keys/witness_ed25519.pem). Honest about its own limit,
  same as KEY_BACKEND=file for the primary signer: if both keys live on the
  same disk, they don't provide independence against "attacker gets root on
  this box." Better than a single key regardless (two signatures to steal
  and use consistently, not one), and the structure is what lets a real
  second host take over the same role later without changing anything else.
- "external": a real second party (a different team, a different host, an
  auditor) independently verifies a checkpoint's (tree_size, root_hash) out
  of band and submits their own signature over that same message. Verified
  here against an operator-configured allowlist of trusted external witness
  public keys (WITNESS_TRUSTED_PUBLIC_KEYS) before being accepted -- an
  unrecognized public key is rejected, not silently stored.
"""
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

from app.core.config import settings

KEY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "keys")
WITNESS_PRIVATE_KEY_PATH = os.path.join(KEY_DIR, "witness_ed25519.pem")

_cached_witness_key = None


def _load_or_generate_witness_key() -> Ed25519PrivateKey:
    global _cached_witness_key
    if _cached_witness_key is not None:
        return _cached_witness_key

    os.makedirs(KEY_DIR, exist_ok=True)
    if os.path.exists(WITNESS_PRIVATE_KEY_PATH):
        with open(WITNESS_PRIVATE_KEY_PATH, "rb") as f:
            _cached_witness_key = serialization.load_pem_private_key(f.read(), password=None)
        return _cached_witness_key

    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(WITNESS_PRIVATE_KEY_PATH, "wb") as f:
        f.write(pem)
    try:
        os.chmod(WITNESS_PRIVATE_KEY_PATH, 0o600)
    except OSError:
        pass
    _cached_witness_key = key
    return _cached_witness_key


def local_witness_public_key_hex() -> str:
    pub = _load_or_generate_witness_key().public_key()
    return pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw).hex()


def sign_local_witness(message: bytes) -> bytes:
    return _load_or_generate_witness_key().sign(message)


def verify_witness_signature(message: bytes, signature: bytes, public_key_hex_str: str) -> bool:
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex_str))
        pub.verify(signature, message)
        return True
    except Exception:
        return False


def trusted_external_public_keys() -> set:
    return {k.strip().lower() for k in settings.WITNESS_TRUSTED_PUBLIC_KEYS.split(",") if k.strip()}


def is_trusted_external_key(public_key_hex_str: str) -> bool:
    return public_key_hex_str.strip().lower() in trusted_external_public_keys()
