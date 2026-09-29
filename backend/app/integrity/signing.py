"""Checkpoint signing (ULPF-master-prompt.md Part D3).

Two backends, selected by `settings.KEY_BACKEND`:

- "file" (default): Ed25519, private key in a PEM file under data/keys/.
  Demo-grade -- the private key lives on the same disk as the app. Fine for
  a local demo, explicitly not what "private key never on app disk" means.
- "pkcs11": ECDSA P-256, private key generated inside and never exported
  from a PKCS#11 token (a real HSM, or SoftHSM2 as a software stand-in --
  see docs/KEY_CEREMONY.md for how this was actually verified against a
  real SoftHSM2 instance, not just written and assumed to work). SoftHSM2's
  Windows build (2.5.0, the current release) does not implement EdDSA, so
  the HSM-backed path uses ECDSA P-256 instead of Ed25519 -- both are
  standard, independently-verifiable signature algorithms; which one signed
  a given checkpoint is recorded on the Checkpoint row itself
  (`algorithm`) and in every evidence bundle, so verification (including the
  standalone offline verifier) always knows which to check against.

"pkcs11" mode fails loudly if the module/token/PIN don't work -- it never
silently falls back to the file backend. A checkpoint signed while "the HSM
was down" would be indistinguishable from one signed with a real HSM-backed
key unless a missing HSM is a hard error, not a soft one.
"""
import hashlib
import os

from app.core.config import settings

# ─── File backend (Ed25519, demo-grade) ────────────────────────────

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives import hashes, serialization

KEY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "keys")
PRIVATE_KEY_PATH = os.path.join(KEY_DIR, "checkpoint_ed25519.pem")

_cached_file_key = None
_pkcs11_session = None
_pkcs11_lib = None


def _load_or_generate_file_key() -> Ed25519PrivateKey:
    global _cached_file_key
    if _cached_file_key is not None:
        return _cached_file_key

    os.makedirs(KEY_DIR, exist_ok=True)
    if os.path.exists(PRIVATE_KEY_PATH):
        with open(PRIVATE_KEY_PATH, "rb") as f:
            _cached_file_key = serialization.load_pem_private_key(f.read(), password=None)
        return _cached_file_key

    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(PRIVATE_KEY_PATH, "wb") as f:
        f.write(pem)
    try:
        os.chmod(PRIVATE_KEY_PATH, 0o600)
    except OSError:
        pass  # best-effort on platforms without POSIX permission bits (e.g. Windows)
    _cached_file_key = key
    return _cached_file_key


# ─── PKCS#11 backend (ECDSA P-256, HSM/SoftHSM2) ───────────────────

def _pkcs11_get_session():
    """Opens (and caches) a logged-in PKCS#11 session. Raises immediately
    and clearly if the module, token, or PIN don't work -- this is the
    "refuses without it" half of D3's acceptance criterion. Imports
    python-pkcs11 lazily so KEY_BACKEND=file (the default, what every test
    and the local demo use) never needs it installed."""
    global _pkcs11_session, _pkcs11_lib
    if _pkcs11_session is not None:
        return _pkcs11_session

    if not settings.PKCS11_MODULE_PATH:
        raise RuntimeError(
            "KEY_BACKEND=pkcs11 but PKCS11_MODULE_PATH is not set -- refusing to sign. "
            "Point it at your HSM's PKCS#11 module (a real HSM's vendor .so/.dll, or "
            "SoftHSM2's for a software stand-in). No fallback to the file backend."
        )

    import pkcs11 as _pkcs11
    _pkcs11_lib = _pkcs11.lib(settings.PKCS11_MODULE_PATH)
    token = _pkcs11_lib.get_token(token_label=settings.PKCS11_TOKEN_LABEL)
    # rw=True: key generation (first run) needs write access; signing itself
    # doesn't, but there's no reason to open a second read-only session.
    _pkcs11_session = token.open(user_pin=settings.PKCS11_PIN, rw=True)
    return _pkcs11_session


def _pkcs11_get_or_create_keypair():
    import pkcs11 as _pkcs11
    from pkcs11 import Attribute, KeyType, Mechanism, ObjectClass

    session = _pkcs11_get_session()
    label = settings.PKCS11_KEY_LABEL

    existing_priv = list(session.get_objects({Attribute.CLASS: ObjectClass.PRIVATE_KEY, Attribute.LABEL: label}))
    existing_pub = list(session.get_objects({Attribute.CLASS: ObjectClass.PUBLIC_KEY, Attribute.LABEL: label}))
    if existing_priv and existing_pub:
        return existing_pub[0], existing_priv[0]

    # secp256r1 (P-256) OID, DER-encoded -- goes in the public key's
    # EC_PARAMS attribute, which is how python-pkcs11 actually expects this
    # (not a top-level generate_keypair() kwarg -- verified against a real
    # SoftHSM2 instance; the library's own type hints don't make this
    # obvious from the outside).
    ecparams = bytes.fromhex("06082a8648ce3d030107")
    pub, priv = session.generate_keypair(
        KeyType.EC, mechanism=Mechanism.EC_KEY_PAIR_GEN, store=True,
        public_template={Attribute.EC_PARAMS: ecparams, Attribute.VERIFY: True, Attribute.LABEL: label},
        private_template={Attribute.SIGN: True, Attribute.SENSITIVE: True, Attribute.EXTRACTABLE: False, Attribute.LABEL: label},
    )
    return pub, priv


def _pkcs11_public_key_hex() -> str:
    """The EC point (uncompressed form, 0x04||X||Y), hex-encoded -- enough
    for anyone to reconstruct the public key and verify a signature without
    this codebase or the HSM, same "standalone verifiable" property the file
    backend's raw Ed25519 public key bytes have."""
    from pkcs11 import Attribute
    pub, _ = _pkcs11_get_or_create_keypair()
    point_der = pub[Attribute.EC_POINT]
    # EC_POINT is DER OCTET STRING-wrapped; the wrapped content is the
    # uncompressed point itself for the P-256 keys this module generates.
    point = point_der[2:] if point_der[0] == 0x04 and point_der[1] == len(point_der) - 2 else point_der
    return point.hex()


def _pkcs11_sign(message: bytes) -> bytes:
    """Signs SHA-256(message) with the token's private key via raw ECDSA
    (SoftHSM2 2.5.0 doesn't implement the combined ECDSA_SHA256 mechanism),
    then re-encodes python-pkcs11's raw r||s output as a standard DER ECDSA
    signature so verification can use the same `cryptography` API as any
    other ECDSA signature, HSM-produced or not."""
    from pkcs11 import Mechanism
    _, priv = _pkcs11_get_or_create_keypair()
    digest = hashlib.sha256(message).digest()
    raw_sig = priv.sign(digest, mechanism=Mechanism.ECDSA)
    r = int.from_bytes(raw_sig[:32], "big")
    s = int.from_bytes(raw_sig[32:], "big")
    return encode_dss_signature(r, s)


# ─── Public API ─────────────────────────────────────────────────────

def current_algorithm() -> str:
    return "ecdsa-p256-hsm" if settings.KEY_BACKEND == "pkcs11" else "ed25519"


def sign_checkpoint(message: bytes) -> bytes:
    if settings.KEY_BACKEND == "pkcs11":
        return _pkcs11_sign(message)
    return _load_or_generate_file_key().sign(message)


def public_key_hex() -> str:
    if settings.KEY_BACKEND == "pkcs11":
        return _pkcs11_public_key_hex()
    pub = _load_or_generate_file_key().public_key()
    raw = pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return raw.hex()


def verify_checkpoint(message: bytes, signature: bytes, public_key_hex_str: str, algorithm: str = "ed25519") -> bool:
    """Standalone-verifiable: only needs the algorithm name, the public key
    hex, the signed message bytes, and the signature -- an external auditor
    never needs this codebase or a live HSM, just `cryptography`."""
    try:
        if algorithm == "ecdsa-p256-hsm":
            point = bytes.fromhex(public_key_hex_str)
            pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
            pub.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        else:
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex_str))
            pub.verify(signature, message)
        return True
    except Exception:
        return False
