import hashlib
import secrets
from typing import Tuple


def hash_api_key(raw_key: str) -> str:
    """Hash an API key using SHA-256 for secure database lookup."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key(prefix: str = "ag_live") -> Tuple[str, str, str]:
    """Generate a new secure API key.
    
    Returns:
        (raw_key, key_prefix, key_hash)
        
    Only the raw_key is returned to the user once upon creation.
    Only key_prefix and key_hash are stored in the database.
    """
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{prefix}_{random_part}"
    key_prefix = raw_key[:12]
    key_hash = hash_api_key(raw_key)
    return raw_key, key_prefix, key_hash
