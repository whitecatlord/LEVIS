"""Explicit structure-only snapshots. Restoring rooms never restores grants."""
import json
import os
from pathlib import Path
import tempfile
from .base import BaseRuntime, Room, ModuleSlot

MAX_SNAPSHOT_BYTES = 1024 * 1024


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate snapshot key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def _identifier(value):
    if type(value) is not str or not 0 < len(value) <= 128 or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid room/slot/capability identity')
    return value


def restore_rooms(raw):
    if type(raw) is not bytes or len(raw) > MAX_SNAPSHOT_BYTES: raise ValueError('Snapshot size limit')
    try: data = _decode(raw.decode('utf-8'))
    except (UnicodeError, RecursionError) as error: raise ValueError('Invalid room snapshot') from error
    if type(data) is not dict or set(data) != {'version', 'rooms'} or type(data['version']) is not int or data['version'] != 1:
        raise ValueError('Unsupported room snapshot')
    if type(data['rooms']) is not list or len(data['rooms']) > 256: raise ValueError('Room count limit')
    rooms = []
    for room in data['rooms']:
        if type(room) is not dict or set(room) != {'room_id', 'purpose', 'slots'}: raise ValueError('Room fields')
        _identifier(room['room_id'])
        if type(room['purpose']) is not str or len(room['purpose']) > 4096: raise ValueError('Room purpose')
        if type(room['slots']) is not list or len(room['slots']) > 64: raise ValueError('Slot count limit')
        restored = Room(room['room_id'], room['purpose'])
        for slot in room['slots']:
            if type(slot) is not dict or set(slot) != {'slot_id', 'required_capabilities'}: raise ValueError('Slot fields')
            _identifier(slot['slot_id']); capabilities = slot['required_capabilities']
            if type(capabilities) is not list or len(capabilities) > 64: raise ValueError('Capability count limit')
            for value in capabilities: _identifier(value)
            if len(set(capabilities)) != len(capabilities): raise ValueError('Duplicate capability')
            restored = restored.with_slot(ModuleSlot(slot['slot_id'], frozenset(capabilities)))
        rooms.append(restored)
    return BaseRuntime(tuple(rooms))


def snapshot_rooms(base):
    data = dict(version=1, rooms=[dict(room_id=r.room_id, purpose=r.purpose,
                slots=[dict(slot_id=s.slot_id, required_capabilities=sorted(s.required_capabilities)) for s in r.slots])
                for r in base.rooms])
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    restore_rooms(raw)  # The writer and reader agree on all shape/size limits.
    return raw


def save_rooms(base, path):
    """Explicit operator persistence, atomic replacement; no OS ownership claim."""
    raw = snapshot_rooms(base); path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.rooms-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(raw); output.flush(); os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_rooms(path):
    with Path(path).open('rb') as source: raw = source.read(MAX_SNAPSHOT_BYTES + 1)
    return restore_rooms(raw)
