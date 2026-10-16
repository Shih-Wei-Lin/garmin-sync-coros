"""Encrypt Garmin session state before saving it to the Actions cache."""

import argparse
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def transfer_session(action, tokenstore, cache_file, key):
    cipher = Fernet(key)
    token_file = Path(tokenstore) / 'garmin_tokens.json'
    cache_file = Path(cache_file)
    if action == 'restore':
        if not cache_file.exists():
            return
        try:
            payload = cipher.decrypt(cache_file.read_bytes())
        except InvalidToken:
            raise RuntimeError('Session cache cannot be decrypted; check GARMIN_SESSION_KEY or delete the cache.') from None
        token_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with os.fdopen(os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'wb') as stream:
            stream.write(payload)
        token_file.chmod(0o600)
    elif action == 'save':
        if token_file.exists():
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(cipher.encrypt(token_file.read_bytes()))
    else:
        raise ValueError('action must be restore or save')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['restore', 'save'])
    args = parser.parse_args()
    key = os.getenv('GARMIN_SESSION_KEY')
    if not key:
        parser.exit(1, 'Add GARMIN_SESSION_KEY to repository Actions secrets first (see README).\n')
    try:
        transfer_session(args.action, os.environ['GARMINTOKENS'], '.garmin-cache/session.enc', key)
    except (ValueError, RuntimeError):
        parser.exit(1, 'Session cache failed: check GARMIN_SESSION_KEY format/key or delete an old cache.\n')
