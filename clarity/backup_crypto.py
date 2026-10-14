"""Passphrase-authenticated backups; credentials remain excluded by backup.py."""
import base64
import json
import os
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from .guardrails import canonical, ValidationError
from .refine.contracts import fields, require

AAD = b'clarity-encrypted-backup-v1'


def key(password, salt):
    require(isinstance(password, str) and len(password) >= 12, 'Use a backup passphrase of at least 12 characters')
    return Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(password.encode())


def encrypt(envelope, password):
    salt, nonce = os.urandom(16), os.urandom(12)
    ciphertext = AESGCM(key(password, salt)).encrypt(nonce, canonical(envelope).encode(), AAD)
    encode = lambda x: base64.b64encode(x).decode()
    return {'format': 'clarity-encrypted-backup-v1', 'salt': encode(salt), 'nonce': encode(nonce), 'ciphertext': encode(ciphertext)}


def decrypt(value, password):
    fields(value, {'format', 'salt', 'nonce', 'ciphertext'}, 'encrypted backup')
    require(value['format'] == AAD.decode(), 'Unsupported encrypted backup format')
    try:
        salt, nonce, ciphertext = [base64.b64decode(value[k], validate=True) for k in ('salt', 'nonce', 'ciphertext')]
        require(len(salt) == 16 and len(nonce) == 12 and len(ciphertext) <= 20_000_300, 'Invalid encrypted backup dimensions')
        raw = AESGCM(key(password, salt)).decrypt(nonce, ciphertext, AAD)
        from .refine.worker import decode
        # Backup permits larger objects than model packets.
        from .guardrails import _unique
        return json.loads(raw, object_pairs_hook=_unique)
    except (InvalidTag, ValueError, TypeError):
        raise ValidationError('Backup authentication failed; check the passphrase and file') from None
