"""Pure unit tests for AgentGuard security utilities (Phase 3).

Exercises pure logic with zero database or network dependencies:
  - Password hashing, verification, and complexity validation (bcrypt)
  - JWT creation, decoding, expiration claims, and tamper resistance
  - API key generation, prefixing, and SHA-256 hashing
"""
import pytest

pytestmark = pytest.mark.unit

from app.security.api_key import generate_api_key, hash_api_key
from app.security.jwt import create_access_token, decode_access_token
from app.security.password import (
    hash_password,
    validate_password_strength,
    verify_password,
)


# ===========================================================================
# 1. Password Security (Pure Logic)
# ===========================================================================

class TestPasswordSecurityUnit:
    def test_hash_differs_from_plaintext(self):
        h = hash_password("MySecret1!")
        assert h != "MySecret1!"

    def test_verify_correct_password(self):
        h = hash_password("ValidPass9")
        assert verify_password("ValidPass9", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("ValidPass9")
        assert verify_password("BadPass99", h) is False

    def test_same_password_produces_different_hash(self):
        h1 = hash_password("SamePass1")
        h2 = hash_password("SamePass1")
        assert h1 != h2  # bcrypt salts each hash

    def test_validate_too_short(self):
        with pytest.raises(ValueError, match="8 characters"):
            validate_password_strength("Ab1")

    def test_validate_no_uppercase(self):
        with pytest.raises(ValueError, match="uppercase"):
            validate_password_strength("password1")

    def test_validate_no_lowercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            validate_password_strength("PASSWORD1")

    def test_validate_no_digit(self):
        with pytest.raises(ValueError, match="digit"):
            validate_password_strength("Password!")

    def test_validate_valid_password(self):
        # Should not raise
        validate_password_strength("ValidPassword123!")


# ===========================================================================
# 2. JWT Encoding & Decoding (Pure Logic)
# ===========================================================================

class TestJWTUnit:
    def test_encode_decode_roundtrip(self):
        data = {"sub": "user-123", "org_id": "org-456", "role": "ADMIN"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user-123"
        assert decoded["org_id"] == "org-456"
        assert decoded["role"] == "ADMIN"

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_access_token("not-a-valid-token")

    def test_tampered_token_raises(self):
        token = create_access_token({"sub": "legit-user"})
        tampered = token[:-4] + "abcd"
        with pytest.raises(Exception):
            decode_access_token(tampered)

    def test_token_contains_exp(self):
        token = create_access_token({"sub": "user-exp"})
        decoded = decode_access_token(token)
        assert "exp" in decoded


# ===========================================================================
# 3. API Key Generation & Hashing (Pure Logic)
# ===========================================================================

class TestAPIKeyUnit:
    def test_generate_returns_triple(self):
        raw, prefix, key_hash = generate_api_key(prefix="ag_test")
        assert raw.startswith(prefix)
        assert len(prefix) >= 7
        assert len(key_hash) == 64  # SHA-256 hex string

    def test_hash_is_not_raw(self):
        raw, _, key_hash = generate_api_key()
        assert raw != key_hash

    def test_same_key_same_hash(self):
        raw, _, hash1 = generate_api_key()
        hash2 = hash_api_key(raw)
        assert hash1 == hash2

    def test_different_keys_different_hashes(self):
        raw1, _, hash1 = generate_api_key()
        raw2, _, hash2 = generate_api_key()
        assert hash1 != hash2

    def test_prefix_format(self):
        raw, prefix, _ = generate_api_key(prefix="custom_agent")
        assert prefix.startswith("custom_agent")
        assert raw.startswith(prefix)
