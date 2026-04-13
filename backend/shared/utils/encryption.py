"""
Token encryption utilities for securing OAuth tokens
"""

import logging
from typing import Optional

from cryptography.fernet import Fernet

from shared.config import settings

logger = logging.getLogger(__name__)


class TokenEncryption:
    """Utility class for encrypting and decrypting OAuth tokens"""

    _cipher: Optional[Fernet] = None

    @classmethod
    def _get_cipher(cls) -> Fernet:
        """Get or create the Fernet cipher instance"""
        if cls._cipher is None:
            if not settings.encryption_key:
                raise ValueError(
                    "ENCRYPTION_KEY is not set in environment variables. "
                    "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )
            try:
                cls._cipher = Fernet(settings.encryption_key.encode())
            except Exception as e:
                logger.error(f"Failed to initialize encryption cipher: {e}")
                raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")
        return cls._cipher

    @classmethod
    def encrypt_token(cls, token: str) -> str:
        """
        Encrypt a token string

        Args:
            token: Plain text token

        Returns:
            Encrypted token as string

        Raises:
            ValueError: If encryption fails
        """
        if not token:
            return ""

        try:
            cipher = cls._get_cipher()
            encrypted_bytes = cipher.encrypt(token.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Token encryption failed: {e}")
            raise ValueError(f"Failed to encrypt token: {e}")

    @classmethod
    def decrypt_token(cls, encrypted_token: str) -> str:
        """
        Decrypt an encrypted token

        Args:
            encrypted_token: Encrypted token string

        Returns:
            Decrypted token as plain text

        Raises:
            ValueError: If decryption fails
        """
        if not encrypted_token:
            return ""

        try:
            cipher = cls._get_cipher()
            decrypted_bytes = cipher.decrypt(encrypted_token.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            raise ValueError(f"Failed to decrypt token: {e}")

    @classmethod
    def generate_key(cls) -> str:
        """
        Generate a new encryption key

        Returns:
            New Fernet key as string

        Usage:
            key = TokenEncryption.generate_key()
            print(f"Add to .env: ENCRYPTION_KEY={key}")
        """
        return Fernet.generate_key().decode()
