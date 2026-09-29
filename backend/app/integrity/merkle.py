"""RFC 6962-style Merkle tree: leaf hashing, root computation, and inclusion
(audit-path) proofs.

Uses the same domain-separated hashing as Certificate Transparency (leaf vs.
internal node prefixes) so an independent verifier only needs SHA-256 and this
file's ~30 lines to check a proof -- no dependency on this codebase at all.
"""
import hashlib

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(LEAF_PREFIX + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def _split_point(n: int) -> int:
    """Largest power of two strictly less than n (RFC 6962's split rule)."""
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def _subtree_root(leaves: list) -> bytes:
    n = len(leaves)
    if n == 1:
        return leaves[0]
    k = _split_point(n)
    return node_hash(_subtree_root(leaves[:k]), _subtree_root(leaves[k:]))


def merkle_root(leaves: list) -> bytes:
    """Root over a left-to-right list of already-leaf-hashed values."""
    if not leaves:
        return hashlib.sha256(b"").digest()
    return _subtree_root(leaves)


def _subtree_path(leaves: list, index: int) -> list:
    n = len(leaves)
    if n == 1:
        return []
    k = _split_point(n)
    if index < k:
        return _subtree_path(leaves[:k], index) + [_subtree_root(leaves[k:])]
    return _subtree_path(leaves[k:], index - k) + [_subtree_root(leaves[:k])]


def audit_path(leaves: list, index: int) -> list:
    """Inclusion proof for `leaves[index]`: sibling hashes ordered leaf-to-root."""
    if not (0 <= index < len(leaves)):
        raise IndexError("leaf index out of range")
    return _subtree_path(leaves, index)


def _verify_subtree(leaf: bytes, index: int, n: int, proof: list) -> bytes:
    if n == 1:
        return leaf
    k = _split_point(n)
    if index < k:
        return node_hash(_verify_subtree(leaf, index, k, proof[:-1]), proof[-1])
    return node_hash(proof[-1], _verify_subtree(leaf, index - k, n - k, proof[:-1]))


def verify_audit_path(leaf: bytes, index: int, tree_size: int, proof: list, expected_root: bytes) -> bool:
    """Recompute the root from a leaf + its audit path and compare to `expected_root`."""
    if tree_size <= 0 or not (0 <= index < tree_size):
        return False
    if tree_size == 1:
        return not proof and leaf == expected_root
    if len(proof) != _proof_length(index, tree_size):
        return False
    return _verify_subtree(leaf, index, tree_size, proof) == expected_root


def _proof_length(index: int, n: int) -> int:
    if n == 1:
        return 0
    k = _split_point(n)
    if index < k:
        return _proof_length(index, k) + 1
    return _proof_length(index - k, n - k) + 1


# ─── Consistency proofs (RFC 6962 section 2.1.2) ───────────────────
#
# An inclusion proof (above) proves one leaf is in a tree of a given size.
# A consistency proof instead proves that a LATER, bigger tree is a pure
# append-only extension of an EARLIER, smaller tree -- i.e. every leaf and
# every leaf's position from the earlier checkpoint is unchanged in the
# later one; nothing was reordered, edited, or removed. This is what closes
# the "only inclusion proofs exist" gap: two signed checkpoints alone don't
# prove one grew out of the other without this.

def _subproof(m: int, leaves: list, b: bool) -> list:
    n = len(leaves)
    if m == n:
        return [] if b else [_subtree_root(leaves)]
    k = _split_point(n)
    if m <= k:
        return _subproof(m, leaves[:k], b) + [_subtree_root(leaves[k:])]
    return _subproof(m - k, leaves[k:], False) + [_subtree_root(leaves[:k])]


def consistency_proof(leaves: list, first_size: int, second_size: int) -> list:
    """Proof that the first `first_size` leaves of `leaves[:second_size]` are
    an unchanged prefix. `leaves` must be at least `second_size` long, in
    the same left-to-right order used to compute both checkpoints' roots."""
    if not (0 <= first_size <= second_size <= len(leaves)):
        raise ValueError("invalid (first_size, second_size) for this leaf list")
    if first_size == 0 or first_size == second_size:
        return []
    return _subproof(first_size, leaves[:second_size], True)


def verify_consistency_proof(first_size: int, first_root: bytes, second_size: int, second_root: bytes, proof: list) -> bool:
    """Recomputes both roots from the proof alone (no access to the actual
    leaves) and checks them against the two checkpoints' stored roots.
    Standard RFC 6962 verification algorithm."""
    if first_size == 0:
        return True  # an empty tree is trivially a prefix of anything
    if first_size > second_size:
        return False
    if first_size == second_size:
        return not proof and first_root == second_root
    if not proof:
        return False

    node = first_size - 1
    last_node = second_size - 1
    while node % 2 == 1:
        node //= 2
        last_node //= 2

    proof_iter = iter(proof)
    try:
        if node > 0:
            new_fr = new_sr = next(proof_iter)
        else:
            new_fr = new_sr = first_root

        while node > 0:
            if node % 2 == 1:
                p = next(proof_iter)
                new_fr = node_hash(p, new_fr)
                new_sr = node_hash(p, new_sr)
            elif node < last_node:
                p = next(proof_iter)
                new_sr = node_hash(new_sr, p)
            node //= 2
            last_node //= 2

        while last_node > 0:
            p = next(proof_iter)
            new_sr = node_hash(new_sr, p)
            last_node //= 2
    except StopIteration:
        return False

    if list(proof_iter):
        return False  # extra, unconsumed proof elements -- not a valid proof

    return new_fr == first_root and new_sr == second_root
