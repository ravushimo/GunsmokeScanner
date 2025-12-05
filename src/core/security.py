import base64
import platform
import uuid
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def get_encryption_key() -> bytes:
    """Generate encryption key from machine-specific identifier"""
    # Use a combination of machine-specific identifiers
    machine_id = f"{platform.node()}-{uuid.getnode()}"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'gunsmoke_scanner_salt',  # Static salt (acceptable for machine-specific encryption)
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
    return key

def encrypt_password(password: str) -> str:
    """Encrypt password for storage"""
    if not password:
        return ""
    try:
        key = get_encryption_key()
        cipher = Fernet(key)
        return cipher.encrypt(password.encode()).decode()
    except Exception as e:
        print(f"Encryption error: {e}")
        return ""

def decrypt_password(encrypted_password: str) -> str:
    """Decrypt password from storage"""
    if not encrypted_password:
        return ""
    try:
        key = get_encryption_key()
        cipher = Fernet(key)
        return cipher.decrypt(encrypted_password.encode()).decode()
    except Exception as e:
        print(f"Decryption error: {e}")
        return ""
