"""Bounded JSON, mutual proof, and authenticated sequenced frames."""
import hashlib
import hmac
import json
import math
import re
import secrets
import struct
import time
import runtime_ipc_windows as win

MAX_FRAME = 1024 * 1024
TIMEOUT = 3.0


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def decode(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('Duplicate JSON key')
            obj[key] = value
        return obj
    def invalid(value):
        raise ValueError('Nonfinite JSON value')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
    def bounded(v, depth=0):
        if depth > 12:
            raise ValueError('JSON nesting limit')
        if isinstance(v, (dict, list)):
            if len(v) > (64 if isinstance(v, dict) else 256):
                raise ValueError('JSON collection limit')
            for child in (v.values() if isinstance(v, dict) else v):
                bounded(child, depth + 1)
    bounded(value)
    return value


def fields(obj, names):
    if type(obj) is not dict or set(obj) != set(names.split()):
        raise ValueError('Invalid fields')


def hex64(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('Invalid nonce/proof')
    return value


def pack(h, data):
    if not 0 < len(data) <= MAX_FRAME:
        raise ValueError('Frame size limit')
    win.write_all(h, struct.pack('!I', len(data)) + data, time.monotonic() + TIMEOUT)


def unpack(h, limit=MAX_FRAME):
    deadline = time.monotonic() + TIMEOUT
    size = struct.unpack('!I', win.read_exact(h, 4, deadline))[0]
    if not 0 < size <= limit:
        raise ValueError('Frame size limit')
    return win.read_exact(h, size, deadline)


def proof(key, role, transcript):
    return hmac.digest(key, role + transcript, 'sha256')


def server_handshake(h, secret, generation, who):
    # Read initial byte before impersonation: Windows needs client data to have
    # been read for ImpersonateNamedPipeClient to identify the effective token.
    initial = decode(unpack(h, 4096))
    fields(initial, 'version')
    if type(initial['version']) is not int or initial['version'] != 1:
        raise ValueError('Protocol version')
    win.peer_identity(h, True, who)
    hello = {'version': 1, 'generation': generation, 'server_nonce': secrets.token_hex(32)}
    pack(h, encode(hello))
    client = decode(unpack(h, 4096))
    fields(client, 'client_nonce proof')
    hex64(client['client_nonce']);hex64(client['proof'])
    transcript = encode({**hello, 'client_nonce': client['client_nonce']})
    if not hmac.compare_digest(client['proof'], proof(secret, b'client', transcript).hex()):
        raise PermissionError('Client authentication failed')
    pack(h, encode({'proof': proof(secret, b'server', transcript).hex()}))
    return Channel(h, proof(secret, b'connection', transcript), b'S', b'C')


def client_handshake(h, secret, discovery, who):
    win.peer_identity(h, False, who, discovery['pid'])
    pack(h, encode({'version': 1}))
    hello = decode(unpack(h, 4096))
    fields(hello, 'version generation server_nonce')
    if hello['version'] != 1 or hello['generation'] != discovery['generation']:
        raise PermissionError('Stale discovery or protocol version')
    hex64(hello['server_nonce'])
    nonce = secrets.token_hex(32)
    transcript = encode({**hello, 'client_nonce': nonce})
    pack(h, encode({'client_nonce': nonce, 'proof': proof(secret, b'client', transcript).hex()}))
    reply = decode(unpack(h, 4096));fields(reply, 'proof');hex64(reply['proof'])
    if not hmac.compare_digest(reply['proof'], proof(secret, b'server', transcript).hex()):
        raise PermissionError('Server authentication failed')
    return Channel(h, proof(secret, b'connection', transcript), b'C', b'S')


class Channel:
    def __init__(self, h, key, outgoing, incoming):
        self.h, self.key, self.outgoing, self.incoming = h, key, outgoing, incoming
        self.sent = self.received = 0

    def frame(self, value):
        seq = struct.pack('!Q', self.sent)
        raw = encode(value)
        mac = proof(self.key, self.outgoing, seq + raw)
        self.sent += 1
        return seq + mac + raw

    def send(self, value):
        pack(self.h, self.frame(value))

    def verify(self, frame):
        if len(frame) < 41 or len(frame) > MAX_FRAME:
            raise ValueError('Invalid authenticated frame size')
        seq, mac, raw = frame[:8], frame[8:40], frame[40:]
        if struct.unpack('!Q', seq)[0] != self.received:
            raise PermissionError('Replay or sequence gap')
        if not hmac.compare_digest(mac, proof(self.key, self.incoming, seq + raw)):
            raise PermissionError('Frame authentication failed')
        # Authenticate raw bytes before decoding command JSON.
        value = decode(raw)
        self.received += 1
        return value

    def receive(self):
        return self.verify(unpack(self.h))


READS = {'status', 'snapshot', 'events', 'attach', 'detach'}
CONTROLS = {'pause', 'resume', 'stop'}


def validate_request(request):
    fields(request, 'protocol_version client_id request_id expected_revision command payload')
    if type(request['protocol_version']) is not int or request['protocol_version'] != 1:
        raise ValueError('Protocol version')
    for key in ('client_id', 'request_id'):
        if type(request[key]) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,64}', request[key]):
            raise ValueError('Invalid request identity')
    if type(request['command']) is not str or request['command'] not in READS | CONTROLS:
        raise ValueError('Unsupported command')
    revision = request['expected_revision']
    if revision is not None and (type(revision) is not int or not 0 <= revision < 2**63):
        raise ValueError('Invalid revision')
    if request['command'] in CONTROLS and revision is None:
        raise ValueError('Control requires expected_revision')
    payload = request['payload']
    if request['command'] == 'events':
        fields(payload, 'after limit')
        if type(payload['after']) is not int or not 0 <= payload['after'] < 2**63:
            raise ValueError('Invalid event cursor')
        if type(payload['limit']) is not int or not 1 <= payload['limit'] <= 100:
            raise ValueError('Invalid event limit')
    else:
        fields(payload, '')
    return request


def validate_response(reply, request):
    """Validate an authenticated outcome before ACK or presentation.

    Historical control receipts keep their original generation and revision.
    A transport reply is not evidence that a lost control did not commit.
    """
    def require(value):
        if not value:
            raise ValueError('Invalid response envelope')

    require(type(reply) is dict)
    require(reply.get('request_id') == request['request_id'])
    require(type(reply.get('runtime_generation')) is str and 0 < len(reply['runtime_generation']) <= 64)
    status = reply.get('status')
    require(status in ('OK', 'REFUSED', 'ERROR'))
    if status == 'ERROR':
        fields(reply, 'request_id status error runtime_generation')
        require(reply['error'] == 'STORAGE_FAILURE')
        return reply
    names = 'request_id status state revision runtime_generation event_cursor clean_shutdown startup_reason executor_enabled model_enabled'
    if status == 'REFUSED':
        names += ' error'
        require(request['command'] in CONTROLS)
        require(reply.get('error') in ('REVISION_CONFLICT', 'INVALID_LIFECYCLE', 'REQUEST_ID_CONFLICT'))
    elif request['command'] == 'events':
        names += ' events next_cursor'
    elif request['command'] in ('attach', 'detach'):
        names += ' attachment'
    fields(reply, names)
    require(reply['state'] in ('STARTING', 'RECOVERING', 'PAUSED', 'READY', 'STOPPING', 'STOPPED', 'ERROR'))
    for key in ('revision', 'event_cursor'):
        require(type(reply[key]) is int and 0 <= reply[key] < 2**63)
    require(type(reply['clean_shutdown']) is bool and reply['clean_shutdown'] == (reply['state'] == 'STOPPED'))
    require(reply['startup_reason'] in ('clean', 'unclean'))
    require(reply['executor_enabled'] is False and reply['model_enabled'] is False)
    if status == 'OK' and request['command'] in CONTROLS:
        require(reply['state'] == {'pause': 'PAUSED', 'resume': 'READY', 'stop': 'STOPPED'}[request['command']])
    if status == 'OK' and request['command'] in ('attach', 'detach'):
        require(reply['attachment'] == ('attached' if request['command'] == 'attach' else 'detached'))
    if status == 'OK' and request['command'] == 'events':
        rows = reply['events']
        require(type(rows) is list and len(rows) <= request['payload']['limit'])
        previous = request['payload']['after']
        previous_revision = -1
        for row in rows:
            fields(row, 'cursor generation state revision at')
            require(type(row['cursor']) is int and previous < row['cursor'] <= reply['event_cursor'])
            require(type(row['revision']) is int and previous_revision < row['revision'] <= reply['revision'])
            require(type(row['generation']) is str and 0 < len(row['generation']) <= 64)
            require(row['state'] in ('STARTING', 'RECOVERING', 'PAUSED', 'READY', 'STOPPING', 'STOPPED', 'ERROR'))
            require(type(row['at']) in (int, float) and math.isfinite(row['at']))
            previous, previous_revision = row['cursor'], row['revision']
        require(type(reply['next_cursor']) is int and reply['next_cursor'] == previous)
    return reply
