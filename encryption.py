import pandas as pd
import base64
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class EncryptionManager:
    def __init__(self, key: bytes = None):
        """
        Initializes the EncryptionManager with a Fernet key.
        If no key is provided, a new one is generated.
        In production, always persist and securely store the encryption key.
        """
        if key:
            self.key = key
            logger.info("Encryption manager initialized with provided key")
        else:
            self.key = Fernet.generate_key()
            logger.warning("Encryption manager generated a new key (not persistent)")

        self.cipher_suite = Fernet(self.key)

    def encrypt_value(self, value):
        """Encrypt a single value using Fernet"""
        try:
            if pd.isna(value):
                return value

            value_str = str(value)
            encrypted = self.cipher_suite.encrypt(value_str.encode('utf-8'))
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption error for value '{value}': {e}")
            return value  # Fallback to raw value on error

    def decrypt_value(self, encrypted_value):
        """Decrypt a previously encrypted value"""
        try:
            if pd.isna(encrypted_value) or not isinstance(encrypted_value, str):
                return encrypted_value

            decoded = base64.b64decode(encrypted_value.encode('utf-8'))
            decrypted = self.cipher_suite.decrypt(decoded)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption error for value '{encrypted_value}': {e}")
            return encrypted_value  # Fallback to raw value on error

    def get_key_info(self):
        """Return basic debug info about the encryption key"""
        return {
            'key_length': len(self.key),
            'key_type': 'Fernet (AES 128)',
            'key_encoded_preview': base64.b64encode(self.key).decode()[:20] + "..."
        }

    def get_key(self):
        """Returns the actual key (use with caution)"""
        return self.key
