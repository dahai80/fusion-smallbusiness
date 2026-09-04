import base64
import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)

_PREFIX = "fsbenc1:"
_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LEN = 32
_SCRYPT_MAXMEM = 64 * 1024 * 1024


def _derive_key(master: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        master.encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_LEN,
        maxmem=_SCRYPT_MAXMEM,
    )


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def encrypt_secret(plaintext: str, master_key: str) -> str:
    if not master_key:
        logger.debug("secret_crypto: no master key, storing plaintext")
        return plaintext
    if not plaintext:
        return plaintext
    salt = os.urandom(16)
    nonce = os.urandom(16)
    key = _derive_key(master_key, salt)
    data = plaintext.encode()
    stream = _keystream(key, nonce, len(data))
    ct = bytes(a ^ b for a, b in zip(data, stream, strict=True))
    mac = hmac.new(key, salt + nonce + ct, hashlib.sha256).digest()
    blob = base64.b64encode(salt + nonce + ct + mac).decode()
    return _PREFIX + blob


def decrypt_secret(stored: str, master_key: str) -> str:
    if not stored or not stored.startswith(_PREFIX):
        return stored
    if not master_key:
        logger.warning("secret_crypto: encrypted value but no master key set")
        return ""
    try:
        blob = base64.b64decode(stored[len(_PREFIX) :])
        salt = blob[:16]
        nonce = blob[16:32]
        mac = blob[-32:]
        ct = blob[32:-32]
        key = _derive_key(master_key, salt)
        expected = hmac.new(key, salt + nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected):
            logger.error("secret_crypto: MAC verification failed")
            return ""
        stream = _keystream(key, nonce, len(ct))
        pt = bytes(a ^ b for a, b in zip(ct, stream, strict=True))
        return pt.decode()
    except Exception as e:
        logger.error("secret_crypto: decrypt failed: %s", e)
        return ""


def is_encrypted(value: str) -> bool:
    return bool(value) and value.startswith(_PREFIX)
