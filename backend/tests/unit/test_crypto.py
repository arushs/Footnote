"""Tests for the crypto module."""

import os

import pytest

# Set test secret key before importing crypto module
os.environ["SECRET_KEY"] = "test-secret-key-for-crypto-tests"

from app.utils import decrypt_token, encrypt_token, is_encrypted


class TestEncryptToken:
    """Tests for token encryption."""

    def test_encrypt_empty_string(self):
        """Should return empty string for empty input."""
        result = encrypt_token("")
        assert result == ""

    def test_encrypt_returns_different_value(self):
        """Should return encrypted value different from input."""
        token = "ya29.test-access-token"
        result = encrypt_token(token)
        assert result != token
        assert len(result) > len(token)

    def test_encrypt_is_deterministic_per_session(self):
        """Encrypted values should be different each time (Fernet uses random IV)."""
        token = "test-token"
        result1 = encrypt_token(token)
        result2 = encrypt_token(token)
        # Fernet uses random IV, so each encryption is different
        assert result1 != result2

    def test_encrypt_produces_base64_output(self):
        """Encrypted output should be base64-encoded."""
        token = "test-token"
        result = encrypt_token(token)
        # Should be valid base64 (no exceptions when decoding)
        import base64

        base64.urlsafe_b64decode(result.encode())


class TestDecryptToken:
    """Tests for token decryption."""

    def test_decrypt_empty_string(self):
        """Should return empty string for empty input."""
        result = decrypt_token("")
        assert result == ""

    def test_decrypt_roundtrip(self):
        """Should decrypt to original value."""
        original = "ya29.test-access-token-12345"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        assert decrypted == original

    def test_decrypt_unicode(self):
        """Should handle unicode characters."""
        original = "token-with-émojis-🔐"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        assert decrypted == original

    def test_decrypt_long_token(self):
        """Should handle long tokens."""
        original = "a" * 1000
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        assert decrypted == original

    def test_decrypt_invalid_token_raises(self):
        """Should raise exception for invalid encrypted data."""
        from cryptography.fernet import InvalidToken

        with pytest.raises((ValueError, InvalidToken)):
            decrypt_token("not-valid-encrypted-data")


class TestIsEncrypted:
    """Tests for encryption detection."""

    def test_is_encrypted_empty_string(self):
        """Should return False for empty string."""
        assert is_encrypted("") is False

    def test_is_encrypted_plain_token(self):
        """Should return False for plain OAuth token."""
        plain_token = "ya29.a0test-oauth-token"
        assert is_encrypted(plain_token) is False

    def test_is_encrypted_encrypted_token(self):
        """Should return True for encrypted token."""
        encrypted = encrypt_token("test-token")
        assert is_encrypted(encrypted) is True

    def test_is_encrypted_random_base64(self):
        """Should return False for random base64 that isn't Fernet."""
        import base64

        random_b64 = base64.urlsafe_b64encode(b"random data").decode()
        assert is_encrypted(random_b64) is False

    def test_is_encrypted_invalid_base64(self):
        """Should return False for invalid base64."""
        assert is_encrypted("not!valid@base64") is False
