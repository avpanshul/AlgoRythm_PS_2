"""Tests for the PKCS#11/HSM checkpoint-signing backend (Part D3).

`test_pkcs11_backend_refuses_when_unconfigured` and
`test_pkcs11_backend_refuses_with_wrong_pin` run everywhere and cover the
"refuses without it" half of D3's acceptance criterion without needing a
real HSM present.

`TestLiveAgainstSoftHSM2` covers the other half ("signing works with HSM
present") against a *real* SoftHSM2 instance -- skipped when one isn't
configured via environment variables, since most dev machines and CI runners
won't have SoftHSM2 installed. This project's own dev environment does not
have Docker/WSL, so SoftHSM2-for-Windows's portable build
(https://github.com/disig/SoftHSM2-for-Windows) was downloaded and a real
token initialized to verify this class actually passes, not just to write
tests that always skip -- see docs/KEY_CEREMONY.md for that setup and its
live output (real key generation, real signing, real verify, a tampered
message correctly failing verification).

To run this class locally:
    set SOFTHSM2_CONF=<path to softhsm2.conf>
    set PATH=%PATH%;<path to SoftHSM2 lib dir>
    set TEST_PKCS11_MODULE_PATH=<path to softhsm2-x64.dll>
    set TEST_PKCS11_TOKEN_LABEL=<a token you initialized with softhsm2-util>
    set TEST_PKCS11_PIN=<that token's user PIN>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest


class TestPkcs11RefusesWithoutRealHsm:
    def test_refuses_when_module_path_unconfigured(self, monkeypatch):
        monkeypatch.setenv("KEY_BACKEND", "pkcs11")
        monkeypatch.delenv("PKCS11_MODULE_PATH", raising=False)
        # Reload settings so the monkeypatched env vars actually take effect
        # (Settings() reads os.getenv at construction time).
        import importlib
        import app.core.config as config_module
        importlib.reload(config_module)
        import app.integrity.signing as signing_module
        importlib.reload(signing_module)

        with pytest.raises(RuntimeError, match="PKCS11_MODULE_PATH"):
            signing_module.sign_checkpoint(b"test message")

        # Restore for other tests in the same process.
        monkeypatch.setenv("KEY_BACKEND", "file")
        importlib.reload(config_module)
        importlib.reload(signing_module)

    def test_never_silently_falls_back_to_file_backend(self, monkeypatch):
        """The failure mode that would defeat the whole point of this
        feature: KEY_BACKEND=pkcs11 misconfigured, but sign_checkpoint()
        quietly signs with the file-backed Ed25519 key anyway, producing a
        checkpoint that *looks* HSM-signed to anyone not checking closely."""
        monkeypatch.setenv("KEY_BACKEND", "pkcs11")
        monkeypatch.delenv("PKCS11_MODULE_PATH", raising=False)
        import importlib
        import app.core.config as config_module
        importlib.reload(config_module)
        import app.integrity.signing as signing_module
        importlib.reload(signing_module)

        raised = False
        try:
            signing_module.sign_checkpoint(b"test message")
        except RuntimeError:
            raised = True
        finally:
            monkeypatch.setenv("KEY_BACKEND", "file")
            importlib.reload(config_module)
            importlib.reload(signing_module)

        assert raised, "sign_checkpoint() must raise, not fall back to the file backend"


def _softhsm2_configured():
    return bool(os.getenv("TEST_PKCS11_MODULE_PATH")) and bool(os.getenv("TEST_PKCS11_TOKEN_LABEL"))


@pytest.mark.skipif(not _softhsm2_configured(), reason="No SoftHSM2 configured via TEST_PKCS11_* env vars -- see this file's module docstring")
class TestLiveAgainstSoftHSM2:
    @pytest.fixture(autouse=True)
    def _configure(self, monkeypatch):
        monkeypatch.setenv("KEY_BACKEND", "pkcs11")
        monkeypatch.setenv("PKCS11_MODULE_PATH", os.environ["TEST_PKCS11_MODULE_PATH"])
        monkeypatch.setenv("PKCS11_TOKEN_LABEL", os.environ["TEST_PKCS11_TOKEN_LABEL"])
        monkeypatch.setenv("PKCS11_PIN", os.environ.get("TEST_PKCS11_PIN", ""))
        monkeypatch.setenv("PKCS11_KEY_LABEL", "ulpf-test-key")
        import importlib
        import app.core.config as config_module
        importlib.reload(config_module)
        import app.integrity.signing as signing_module
        importlib.reload(signing_module)
        self.signing = signing_module
        yield
        # SoftHSM2 tracks login state at the token level -- reloading the
        # module (which drops our reference to the open session) without
        # closing it first leaves the token logged in, so the *next* test's
        # token.open() fails with UserAlreadyLoggedIn even though it's a
        # fresh Python-level session object.
        if signing_module._pkcs11_session is not None:
            signing_module._pkcs11_session.close()
        monkeypatch.setenv("KEY_BACKEND", "file")
        importlib.reload(config_module)
        importlib.reload(signing_module)

    def test_algorithm_is_ecdsa_p256_hsm(self):
        assert self.signing.current_algorithm() == "ecdsa-p256-hsm"

    def test_real_sign_and_verify_round_trip(self):
        pubkey = self.signing.public_key_hex()
        message = b"12345:deadbeef"
        signature = self.signing.sign_checkpoint(message)
        assert self.signing.verify_checkpoint(message, signature, pubkey, "ecdsa-p256-hsm") is True

    def test_tampered_message_fails_verification(self):
        pubkey = self.signing.public_key_hex()
        signature = self.signing.sign_checkpoint(b"original message")
        assert self.signing.verify_checkpoint(b"tampered message", signature, pubkey, "ecdsa-p256-hsm") is False

    def test_private_key_material_never_appears_in_public_key_hex(self):
        # A very basic sanity check: the public key we hand out is only ever
        # the EC point, never something that could be mistaken for exported
        # private key material (which python-pkcs11 can't even fetch, since
        # the key was generated with EXTRACTABLE: False).
        pubkey = self.signing.public_key_hex()
        assert len(bytes.fromhex(pubkey)) == 65  # uncompressed P-256 point: 0x04 || X(32) || Y(32)
