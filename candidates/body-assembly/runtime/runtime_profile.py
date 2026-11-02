"""Explicit isolated profile creation and fail-closed existing identity checks."""
import os
import secrets
import uuid
import runtime_ipc_windows as win
from runtime_protocol import encode, decode, fields

ALLOWED = {'profile.json', 'secret.dpapi', 'writer.lock', 'runtime.sqlite3',
           'runtime.sqlite3-wal', 'runtime.sqlite3-shm', 'discovery.json', 'discovery.tmp', 'profile.tmp','draft-artifacts'}
CONTINUITY_POLICY = 'SAME_LOGON_ONLY_UNQUALIFIED'


def bounded_read(path, maximum=8192):
    with path.open('rb') as f:
        value = f.read(maximum + 1)
    if len(value) > maximum:
        raise ValueError('Profile metadata size limit')
    return value


def load(path, *, allow_initializing=False):
    profile, who = win.canonical_profile(path), win.process_identity()
    win.verify_private(profile, who, protected=True)
    for child in profile.iterdir():
        if child.name not in ALLOWED or (child.is_dir() and child.name!='draft-artifacts'):
            raise ValueError('Profile contains unknown/legacy files')
        if win.attributes(str(child)) & 0x400:
            raise ValueError('Profile child reparse point refused')
        win.verify_private(child, who)
        if child.name=='draft-artifacts':
            if not child.is_dir():raise ValueError('Draft artifact directory required')
            entries=list(child.iterdir())
            if len(entries)>1024:raise ValueError('Draft artifact entry quota')
            for artifact in entries:
                if win.attributes(str(artifact)) & 0x400 or not artifact.is_file():
                    raise ValueError('Unsupported draft artifact entry')
                win.verify_private(artifact,who)
    metadata = decode(bounded_read(profile / 'profile.json'))
    fields(metadata, 'kind version profile_id identity phase continuity_policy')
    if metadata['kind'] != 'LEVIS-M1.2-draft-isolated' or metadata['version'] != 3:
        raise PermissionError('Unsupported profile version; no implicit migration')
    if metadata['continuity_policy'] != CONTINUITY_POLICY:
        raise PermissionError('Unsupported cross-logon policy')
    if metadata['identity'] != who:
        raise PermissionError('Cross-logon continuity disabled; profile preserved without rekeying')
    permitted_phase = 'INITIALIZING' if allow_initializing else 'READY'
    if metadata['phase'] != permitted_phase:
        raise RuntimeError('Profile initialization incomplete or incompatible with startup mode')
    if not allow_initializing:
        ledger = profile / 'runtime.sqlite3'
        if not ledger.is_file() or ledger.stat().st_size < 4096:
            raise RuntimeError('Established profile ledger missing or truncated; recovery required')
    if uuid.UUID(metadata['profile_id']).hex != metadata['profile_id']:
        raise ValueError('Profile identity invalid')
    secret = win.dpapi(bounded_read(profile / 'secret.dpapi'), decrypt=True)
    if len(secret) != 32:
        raise PermissionError('Profile secret invalid')
    return profile, who, secret


def initialize(path):
    profile, who = win.canonical_profile(path), win.process_identity()
    # mkdir is intentionally exclusive; never initialize over an old directory.
    profile.mkdir()
    win.private_path(profile, who)
    win.verify_private(profile, who, protected=True)
    write_metadata(profile, {'kind': 'LEVIS-M1.2-draft-isolated', 'version': 3,
                            'profile_id': uuid.uuid4().hex, 'identity': who,
                            'phase': 'INITIALIZING', 'continuity_policy': CONTINUITY_POLICY})
    (profile / 'secret.dpapi').write_bytes(win.dpapi(secrets.token_bytes(32)))
    return load(profile, allow_initializing=True)


def write_metadata(profile, value):
    temp = profile / 'profile.tmp'
    with temp.open('wb') as f:
        f.write(encode(value));f.flush();os.fsync(f.fileno())
    os.replace(temp, profile / 'profile.json')


def mark_ready(profile, who):
    # Called only with the OS writer lock held, after initialized store startup.
    metadata = decode(bounded_read(profile / 'profile.json'))
    if metadata['phase'] != 'INITIALIZING' or metadata['identity'] != who:
        raise RuntimeError('Invalid profile initialization phase')
    metadata['phase'] = 'READY'
    write_metadata(profile, metadata)


def publish(profile, who, generation):
    # Existing discovery may only be replaced while the exclusive writer owns
    # the profile. No secret is included. Atomic publication avoids partial JSON.
    path = profile / 'discovery.json'
    raw = encode({'version': 1, 'pid': os.getpid(), 'generation': generation, 'identity': who})
    # A fixed temp is safe under the profile lock; removed atomically on success.
    temp = profile / 'discovery.tmp'
    with temp.open('wb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(temp, path)


def discovery(profile, who):
    value = decode(bounded_read(profile / 'discovery.json'))
    fields(value, 'version pid generation identity')
    if value['version'] != 1 or value['identity'] != who or type(value['pid']) is not int or value['pid'] <= 0:
        raise PermissionError('Invalid discovery identity')
    if uuid.UUID(value['generation']).hex != value['generation']:
        raise ValueError('Invalid runtime generation')
    return value
