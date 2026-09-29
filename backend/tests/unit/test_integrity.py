"""Unit tests for the Merkle tree, Ed25519 checkpoint signing, RFC 8785
canonical JSON, and the source-pack field-mapping engine."""
import random
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.integrity import merkle, signing
from app.integrity.canonical_json import canonicalize
from app.parsers.mapping_engine import apply_source_pack
from app.parsers.deterministic import parse_xml
from app.core.processing import _flatten_dict, normalize_parsed_data


class TestMerkleTree:
    def test_inclusion_proof_verifies(self):
        random.seed(42)
        for _ in range(50):
            n = random.randint(1, 40)
            leaves = [merkle.leaf_hash(f"item-{i}".encode()) for i in range(n)]
            root = merkle.merkle_root(leaves)
            idx = random.randrange(n)
            proof = merkle.audit_path(leaves, idx)
            assert merkle.verify_audit_path(leaves[idx], idx, n, proof, root)

    def test_tampered_leaf_fails_verification(self):
        leaves = [merkle.leaf_hash(f"item-{i}".encode()) for i in range(10)]
        root = merkle.merkle_root(leaves)
        proof = merkle.audit_path(leaves, 3)
        bad_leaf = merkle.leaf_hash(b"not-the-real-item")
        assert not merkle.verify_audit_path(bad_leaf, 3, 10, proof, root)

    def test_tampered_root_fails_verification(self):
        leaves = [merkle.leaf_hash(f"item-{i}".encode()) for i in range(10)]
        proof = merkle.audit_path(leaves, 3)
        wrong_root = merkle.merkle_root([merkle.leaf_hash(b"x")])
        assert not merkle.verify_audit_path(leaves[3], 3, 10, proof, wrong_root)

    def test_single_leaf_tree(self):
        leaves = [merkle.leaf_hash(b"only-item")]
        root = merkle.merkle_root(leaves)
        proof = merkle.audit_path(leaves, 0)
        assert proof == []
        assert merkle.verify_audit_path(leaves[0], 0, 1, proof, root)


class TestEd25519Signing:
    def test_valid_signature_verifies(self):
        msg = b"5:deadbeefcafe"
        sig = signing.sign_checkpoint(msg)
        pub = signing.public_key_hex()
        assert signing.verify_checkpoint(msg, sig, pub)

    def test_tampered_message_fails(self):
        msg = b"5:deadbeefcafe"
        sig = signing.sign_checkpoint(msg)
        pub = signing.public_key_hex()
        assert not signing.verify_checkpoint(b"6:deadbeefcafe", sig, pub)

    def test_wrong_key_fails(self):
        msg = b"5:deadbeefcafe"
        sig = signing.sign_checkpoint(msg)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        other_pub = Ed25519PrivateKey.generate().public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        ).hex()
        assert not signing.verify_checkpoint(msg, sig, other_pub)


class TestCanonicalJson:
    def test_keys_sorted_regardless_of_input_order(self):
        assert canonicalize({"b": 1, "a": 2}) == canonicalize({"a": 2, "b": 1})

    def test_no_insignificant_whitespace(self):
        out = canonicalize({"a": [1, 2, 3]})
        assert " " not in out

    def test_stable_hash_for_reordered_dict(self):
        import hashlib
        h1 = hashlib.sha256(canonicalize({"a": 1, "b": {"y": 2, "x": 1}}).encode()).hexdigest()
        h2 = hashlib.sha256(canonicalize({"b": {"x": 1, "y": 2}, "a": 1}).encode()).hexdigest()
        assert h1 == h2


class TestMappingEngine:
    def test_coalesce_picks_first_present(self):
        parsed = {"fields": {"suser": None, "duser": "alice"}}
        config = {"field_mappings": [
            {"raw_field": ["fields.suser", "fields.duser"], "canonical_field": "user_name"}
        ]}
        assert apply_source_pack(parsed, config)["user_name"] == "alice"

    def test_join_concatenates_list_value(self):
        parsed = {"fields": {"tags": ["a", "b", "c"]}}
        config = {"field_mappings": [
            {"raw_field": "fields.tags", "canonical_field": "message", "list_mode": "join", "join_delimiter": "|"}
        ]}
        assert apply_source_pack(parsed, config)["message"] == "a|b|c"

    def test_static_values_applied(self):
        config = {"static": {"device_vendor": "PaloAlto"}}
        assert apply_source_pack({}, config)["device_vendor"] == "PaloAlto"

    def test_nested_canonical_field_path(self):
        parsed = {"sev": "high"}
        config = {"field_mappings": [{"raw_field": "sev", "canonical_field": "event_data.severity"}]}
        assert apply_source_pack(parsed, config)["event_data"]["severity"] == "high"

    def test_regex_extraction_from_free_text(self):
        parsed = {"message": "%ASA-6-302013: Built outbound TCP connection 123 for outside:203.0.113.5/443 to inside:10.0.0.7/51000"}
        config = {"field_mappings": [
            {"raw_field": "message", "canonical_field": "source_ip", "regex": r"outside:(\d{1,3}(?:\.\d{1,3}){3})"},
            {"raw_field": "message", "canonical_field": "dest_ip", "regex": r"inside:(\d{1,3}(?:\.\d{1,3}){3})"},
        ]}
        result = apply_source_pack(parsed, config)
        assert result["source_ip"] == "203.0.113.5"
        assert result["dest_ip"] == "10.0.0.7"

    def test_regex_no_match_omits_field(self):
        parsed = {"message": "nothing relevant here"}
        config = {"field_mappings": [{"raw_field": "message", "canonical_field": "source_ip", "regex": r"outside:(\d+\.\d+\.\d+\.\d+)"}]}
        assert "source_ip" not in apply_source_pack(parsed, config)


class TestXmlRepeatedSiblings:
    """Regression tests for a real bug found via real Windows Event Log XML
    testing (2026-09-25): parse_xml overwrote same-tag siblings, so only the
    LAST <Data Name="X"> under <EventData> ever survived -- meaning Windows
    Event Log normalization silently lost every field but one for any event
    with more than one Data element."""

    def test_repeated_siblings_all_preserved(self):
        xml = (
            '<Event><EventData>'
            '<Data Name="SourceAddress">10.0.0.1</Data>'
            '<Data Name="DestAddress">10.0.0.2</Data>'
            '<Data Name="DestPort">443</Data>'
            '</EventData></Event>'
        )
        flat = _flatten_dict(parse_xml(xml))
        assert any(v == "10.0.0.1" for v in flat.values()), "SourceAddress was dropped"
        assert any(v == "10.0.0.2" for v in flat.values()), "DestAddress was dropped"
        assert any(v == "443" for v in flat.values()), "DestPort was dropped"

    def test_named_fields_reach_normalization(self):
        xml = (
            '<Event><EventData>'
            '<Data Name="SourceAddress">10.0.0.1</Data>'
            '<Data Name="DestAddress">10.0.0.2</Data>'
            '</EventData></Event>'
        )
        norm = normalize_parsed_data(parse_xml(xml), "XML", xml)
        assert norm["source_ip"] == "10.0.0.1"
        assert norm["dest_ip"] == "10.0.0.2"

    def test_single_child_tag_still_works_unchanged(self):
        """Non-repeated tags (the common case for other formats) must be
        unaffected by the list-collection change."""
        xml = '<Event><System><Computer>HOST01</Computer></System></Event>'
        flat = _flatten_dict(parse_xml(xml))
        assert any(v == "HOST01" for v in flat.values())
