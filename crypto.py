import os
from pathlib import Path
from cryptography.fernet import Fernet

BASE_DIR = Path(__file__).resolve().parent
KEY_FILE = BASE_DIR / "fernet.key"

def get_or_create_key() -> bytes:
    env_key = os.environ.get("MINDMATE_FERNET_KEY")
    if env_key:
        return env_key.encode("utf-8")
    
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes().strip()
    
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key

_fernet_instance = None

def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        _fernet_instance = Fernet(get_or_create_key())
    return _fernet_instance

def encrypt_note(plain_text: str | None) -> str | None:
    if not plain_text:
        return None
    f = get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")

def decrypt_note(cipher_text: str | None) -> str | None:
    if not cipher_text:
        return None
    try:
        f = get_fernet()
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        return "[Decryption failed / Invalid key]"
