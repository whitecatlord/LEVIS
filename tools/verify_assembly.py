"""Verify a candidate's complete SHA-256 inventory; never executes its code."""
import argparse
import hashlib
from pathlib import Path, PurePosixPath
import sys


def verify(root):
    root = Path(root).resolve()
    entries = {}
    for line in (root/'MANIFEST_SHA256.txt').read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        path = PurePosixPath(name)
        if (len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest) or
                path.is_absolute() or '..' in path.parts or name in entries or '\\' in name):
            raise ValueError('Invalid inventory entry')
        entries[name] = digest
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p != root/'MANIFEST_SHA256.txt'}
    if set(entries) != actual: raise ValueError('Inventory membership mismatch')
    for name, expected in entries.items():
        path = root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root): raise ValueError('Linked entry refused')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected: raise ValueError('Hash mismatch: '+name)
    print(f'PASS: {len(entries)} files match {root.name} inventory')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    try: verify(args.candidate)
    except (OSError, ValueError) as error:
        print(f'REFUSED: {error}', file=sys.stderr); sys.exit(2)
