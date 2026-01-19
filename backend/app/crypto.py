"""Cryptographic utilities for encrypting sensitive data at rest."""

import base64
from functools import lru_cache

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Get or create a Fernet instance using the secret key.

    Derives a proper 32-byte key from the secret key using PBKDF2.
    The salt is derived from the secret key itself for determinism.
    """
    secret = settings.secret_key.encode()

    # Use a deterministic salt derived from the secret key
    # This ensures the same key is derived each time
    salt = secret[:16].ljust(16, b"\x00")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return Fernet(key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token for storage.

    Args:
        plaintext: The token to encrypt

    Returns:
        Base64-encoded encrypted token
    """
    if not plaintext:
        return ""

    fernet = _get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt an encrypted token.

    Args:
        ciphertext: Base64-encoded encrypted token

    Returns:
        The decrypted token

    Raises:
        Exception: If decryption fails (invalid token or wrong key)
    """
    if not ciphertext:
        return ""

    fernet = _get_fernet()
    encrypted = base64.urlsafe_b64decode(ciphertext.encode())
    return fernet.decrypt(encrypted).decode()


def is_encrypted(token: str) -> bool:
    """Check if a token appears to be encrypted.

    Encrypted tokens are double base64-encoded (Fernet output is base64,
    then we encode again for storage). After one decode, we get bytes
    starting with 'gAAAAA' (the base64 representation of Fernet's 0x80 version byte).
    """
    if not token:
        return False

    try:
        # First decode: removes our outer base64 encoding
        decoded = base64.urlsafe_b64decode(token.encode())
        # Fernet base64 output starts with 'gAAAAA' (encodes 0x80 0x00 0x00 0x00...)
        # Check for the 'gAAAAA' prefix which indicates Fernet format
        return len(decoded) >= 100 and decoded[:6] == b"gAAAAA"
    except Exception:
        return False
