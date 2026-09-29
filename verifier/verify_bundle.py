#!/usr/bin/env python3
r"""ULPF standalone offline evidence bundle verifier.

Deliberately independent of the main ULPF application: this file has no
import of anything under backend/app/, so it can be copied to any machine
(including one that has never run ULPF) and used to check a bundle without
trusting the system that produced it. Its only third-party dependency is the
`cryptography` package (for Ed25519 signature verification); everything else
is Python standard library.

What it checks, and what each check actually proves:

  1. raw_event.txt's SHA-256 matches manifest.json's recorded hash for it,
     and matches chain_of_custody.json's raw_sha256.
     -> Proves the raw bytes in this bundle are exactly what was hashed at
        ingestion time (assuming you trust manifest.json/chain_of_custody.json
        themselves -- which checks 2-3 below establish independently of trust).

  2. normalized_event.json's canonical form, re-hashed with the same RFC 8785
     (JCS) canonicalization ULPF uses, matches chain_of_custody.json's
     normalized_sha256.
     -> Proves the normalized event hasn't been edited since it was produced.

  3. merkle_proof.json's audit path, replayed against its own leaf_hash,
     reproduces the Merkle root in the accompanying checkpoint.
     -> Proves this event's hash is really included in that specific,
        checkpointed Merkle tree -- not just asserted to be.

  4. The checkpoint's Ed25519 signature, verified against its own public key
     bundled in checkpoint.json, is valid for (tree_size, root_hash).
     -> Proves the checkpoint (and therefore the root the proof was checked
        against in step 3) was signed by whoever holds the private key --
        this is the step that requires an out-of-band trust decision: you
        must already know and trust that public key (e.g. from a separate,
        independently-obtained key registry) for this to mean anything. This
        tool does NOT verify the key itself, only the signature against the
        key found inside the bundle -- said plainly so nobody mistakes
        "signature valid" for "signed by someone I trust."

Usage:
    python verify_bundle.py evidence_evt_xxx.zip
    python verify_bundle.py evidence_evt_xxx.zip --trusted-key <hex public key>
"""
import argparse
import hashlib
import json
import sys
import zipfile

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
except ImportError:
    print("ERROR: this tool needs the 'cryptography' package. Install with: pip install cryptography")
    sys.exit(2)


def _verify_signature(algorithm: str, pubkey_hex: str, message: bytes, signature: bytes) -> bool:
    """Dispatches on the checkpoint's own recorded algorithm (Part D3):
    "ed25519" for the demo-grade file-backed key, "ecdsa-p256-hsm" for a
    PKCS#11/HSM-backed key -- either way, verification here needs only the
    public key and `cryptography`, never this codebase or a live HSM."""
    try:
        if algorithm == "ecdsa-p256-hsm":
            point = bytes.fromhex(pubkey_hex)
            pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
            pub.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        else:
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
            pub.verify(signature, message)
        return True
    except Exception:
        return False


# ─── RFC 8785 (JCS) canonical JSON -- copied, not imported, so this tool has
# no dependency on the main app. Must stay byte-identical to
# backend/app/integrity/canonical_json.py. ──────────────────────────────────

def _canonicalize(value):
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value.keys(), key=lambda s: [ord(c) for c in s])}
    if isinstance(value, list):
        return [_canonicalize(v) for v in value]
    return value


def canonicalize(obj) -> str:
    return json.dumps(_canonicalize(obj), ensure_ascii=False, separators=(",", ":"))


# ─── RFC 6962-style Merkle audit-path verification -- copied, not imported,
# from backend/app/integrity/merkle.py for the same reason. ─────────────────

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def _split_point(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def _verify_subtree(leaf: bytes, index: int, n: int, proof: list) -> bytes:
    if n == 1:
        return leaf
    k = _split_point(n)
    if index < k:
        return node_hash(_verify_subtree(leaf, index, k, proof[:-1]), proof[-1])
    return node_hash(proof[-1], _verify_subtree(leaf, index - k, n - k, proof[:-1]))


def verify_audit_path(leaf: bytes, index: int, tree_size: int, proof: list, expected_root: bytes) -> bool:
    if tree_size <= 0 or not (0 <= index < tree_size):
        return False
    if tree_size == 1:
        return not proof and leaf == expected_root
    return _verify_subtree(leaf, index, tree_size, proof) == expected_root


# ─── Verification ───────────────────────────────────────────────────────────

class Check:
    def __init__(self, name):
        self.name = name
        self.passed = None
        self.detail = ""

    def ok(self, detail=""):
        self.passed = True
        self.detail = detail

    def fail(self, detail=""):
        self.passed = False
        self.detail = detail


def verify_bundle(bundle_path: str, trusted_key_hex: str = None) -> list:
    checks = []

    with zipfile.ZipFile(bundle_path) as zf:
        names = set(zf.namelist())
        required = {"raw_event.txt", "normalized_event.json", "merkle_proof.json",
                    "chain_of_custody.json", "manifest.json"}
        missing = required - names
        c = Check("Bundle structure")
        if missing:
            c.fail(f"missing files: {sorted(missing)}")
            checks.append(c)
            return checks
        c.ok("all required files present")
        checks.append(c)

        raw_bytes = zf.read("raw_event.txt")
        normalized = json.loads(zf.read("normalized_event.json"))
        proof = json.loads(zf.read("merkle_proof.json"))
        custody = json.loads(zf.read("chain_of_custody.json"))
        manifest = json.loads(zf.read("manifest.json"))

    # 1. Raw content hash
    c = Check("Raw event SHA-256")
    actual_raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    expected = custody.get("raw_sha256")
    manifest_hash = manifest.get("files", {}).get("raw_event.txt")
    if actual_raw_sha256 == expected == manifest_hash:
        c.ok(f"{actual_raw_sha256}")
    else:
        c.fail(f"computed={actual_raw_sha256} custody={expected} manifest={manifest_hash}")
    checks.append(c)

    # 2. Normalized content hash (RFC 8785 canonical)
    c = Check("Normalized event SHA-256 (RFC 8785)")
    actual_norm_sha256 = hashlib.sha256(canonicalize(normalized).encode("utf-8")).hexdigest()
    expected_norm = custody.get("normalized_sha256")
    if actual_norm_sha256 == expected_norm:
        c.ok(f"{actual_norm_sha256}")
    else:
        c.fail(f"computed={actual_norm_sha256} custody={expected_norm}")
    checks.append(c)

    # 3. Merkle inclusion proof
    c = Check("Merkle inclusion proof")
    if not proof.get("included"):
        c.fail(f"bundle's own proof says not included: {proof.get('reason')}")
        checks.append(c)
    else:
        leaf = bytes.fromhex(proof["leaf_hash"])
        audit_path = [bytes.fromhex(h) for h in proof["audit_path"]]
        checkpoint = proof["checkpoint"]
        root = bytes.fromhex(checkpoint["root_hash"])
        index = proof["leaf_index"]
        tree_size = checkpoint["tree_size"]
        if verify_audit_path(leaf, index, tree_size, audit_path, root):
            c.ok(f"leaf at index {index} included in root {checkpoint['root_hash'][:16]}... (tree_size={tree_size})")
        else:
            c.fail("audit path does not reproduce the checkpoint root")
        checks.append(c)

        # 4. Checkpoint signature
        algorithm = checkpoint.get("algorithm") or "ed25519"
        c = Check(f"Checkpoint signature ({algorithm})")
        message = f"{checkpoint['tree_size']}:{checkpoint['root_hash']}".encode("utf-8")
        signature = bytes.fromhex(checkpoint["signature"])
        pubkey_hex = checkpoint["public_key"]
        sig_valid = _verify_signature(algorithm, pubkey_hex, message, signature)

        if sig_valid:
            if trusted_key_hex and trusted_key_hex.lower() != pubkey_hex.lower():
                c.fail(f"signature is valid, but signing key {pubkey_hex} does not match "
                       f"the trusted key you supplied ({trusted_key_hex})")
            elif trusted_key_hex:
                c.ok(f"valid, and matches your trusted key {pubkey_hex}")
            else:
                c.ok(f"valid for key {pubkey_hex} (no --trusted-key given -- you have NOT "
                     f"independently confirmed this is the right key)")
        else:
            c.fail("signature does not verify against the bundled public key")
        checks.append(c)

    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bundle", help="Path to an evidence_*.zip bundle")
    parser.add_argument("--trusted-key", help="Expected public key (hex, Ed25519 or ECDSA P-256 depending on the checkpoint's algorithm) -- obtained "
                                               "out-of-band, not from this bundle -- to confirm "
                                               "the checkpoint was signed by the right party")
    args = parser.parse_args()

    checks = verify_bundle(args.bundle, args.trusted_key)

    print(f"\nVerifying {args.bundle}\n" + "=" * 60)
    all_passed = True
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        if not c.passed:
            all_passed = False
        print(f"[{status}] {c.name}")
        if c.detail:
            print(f"       {c.detail}")

    print("=" * 60)
    if all_passed:
        print("RESULT: all checks passed.")
        if not args.trusted_key:
            print("NOTE: signature verified against the key found IN the bundle, not an "
                  "independently trusted key. Pass --trusted-key to confirm signer identity.")
        sys.exit(0)
    else:
        print("RESULT: one or more checks FAILED -- do not trust this evidence.")
        sys.exit(1)


if __name__ == "__main__":
    main()
