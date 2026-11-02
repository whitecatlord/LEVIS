"""One actor, one SQLite connection; no worker/IPC thread opens writable SQLite."""
from concurrent.futures import Future
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import sqlite3
import threading
import time
import runtime_protocol as protocol

STATES = ('STARTING', 'RECOVERING', 'PAUSED', 'READY', 'STOPPING', 'STOPPED', 'ERROR')
STATE_SQL = "('STARTING','RECOVERING','PAUSED','READY','STOPPING','STOPPED','ERROR')"
SCHEMA_VERSION = 2
DDL = (
    f"CREATE TABLE runtime(id INTEGER PRIMARY KEY CHECK(id=1),state TEXT NOT NULL CHECK(state IN {STATE_SQL}),"
    "revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>=0),generation TEXT NOT NULL,"
    "clean INTEGER NOT NULL CHECK(clean IN (0,1) AND clean=(state='STOPPED')))",
    f"CREATE TABLE events(cursor INTEGER PRIMARY KEY AUTOINCREMENT,generation TEXT,state TEXT CHECK(state IN {STATE_SQL}),revision INTEGER,at REAL)",
    "CREATE TABLE requests(client TEXT,id TEXT,body_hash TEXT,response TEXT,PRIMARY KEY(client,id))",
    "CREATE TABLE controls(client TEXT,id TEXT,command TEXT CHECK(command IN ('pause','resume','stop')),revision INTEGER)",
)


def schema_inventory(db):
    # Include all objects, including generated indices and sqlite_sequence.
    return [(kind, name, table, ' '.join(sql.split()) if sql else None)
            for kind, name, table, sql in db.execute(
                'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name')]


def expected_schema():
    db = sqlite3.connect(':memory:')
    try:
        for sql in DDL:
            db.execute(sql)
        return schema_inventory(db)
    finally:
        db.close()


class LedgerIntegrityError(RuntimeError):
    """Detectable content inconsistency; original evidence must be preserved."""
    code = 'LEDGER_INTEGRITY'


def validate_contents(db, runtime):
    def require(condition):
        if not condition:
            raise LedgerIntegrityError('LEDGER_INTEGRITY: inconsistent runtime history')

    events = db.execute('SELECT cursor,generation,state,revision,at FROM events ORDER BY cursor').fetchall()
    by_cursor = {}
    previous = None
    generations = set()
    exits = {'STARTING': {'RECOVERING'}, 'RECOVERING': {'PAUSED'},
             'PAUSED': {'READY', 'STOPPING'}, 'READY': {'PAUSED', 'STOPPING'},
             'STOPPING': {'STOPPED'}, 'STOPPED': set(), 'ERROR': set()}
    for index, event in enumerate(events, 1):
        cursor, generation, state, revision, at = event
        require(type(cursor) is int and cursor == index and type(revision) is int and revision == index)
        require(type(generation) is str and bool(generation) and state in STATES)
        require(type(at) in (int, float) and math.isfinite(at))
        if state == 'STARTING':
            require(generation not in generations)
            generations.add(generation)
        else:
            require(previous is not None and generation == previous[1] and state in exits[previous[2]])
        previous = event
        by_cursor[cursor] = event
    if previous:
        require((runtime[1], runtime[2], runtime[3]) == (previous[2], previous[3], previous[1]))
    else:
        require(runtime == (1, 'STOPPED', 0, '', 1))
    controls = {}
    for client, identity, command, revision in db.execute('SELECT client,id,command,revision FROM controls'):
        require((client, identity) not in controls and command in protocol.CONTROLS)
        controls[client, identity] = (command, revision)
    for client, identity, digest, raw in db.execute('SELECT client,id,body_hash,response FROM requests'):
        try:
            protocol.hex64(digest)
            require(type(raw) is str and len(raw.encode('utf-8')) <= protocol.MAX_FRAME)
            reply = protocol.decode(raw.encode('utf-8'))
            fields = 'request_id status state revision runtime_generation event_cursor clean_shutdown startup_reason executor_enabled model_enabled'
            require(type(reply) is dict and reply.get('status') in ('OK', 'REFUSED'))
            protocol.fields(reply, fields + (' error' if reply['status'] == 'REFUSED' else ''))
            require(reply['request_id'] == identity)
            protocol.validate_request(dict(protocol_version=1, client_id=client, request_id=identity,
                                           expected_revision=0, command='pause', payload={}))
            cursor, revision = reply['event_cursor'], reply['revision']
            require(type(cursor) is int and type(revision) is int and cursor in by_cursor)
            event = by_cursor[cursor]
            require((reply['state'], revision, reply['runtime_generation']) == (event[2], event[3], event[1]))
            require(type(reply['clean_shutdown']) is bool and reply['clean_shutdown'] == (event[2] == 'STOPPED'))
            require(reply['startup_reason'] in ('clean', 'unclean'))
            require(reply['executor_enabled'] is False and reply['model_enabled'] is False)
            control = controls.pop((client, identity), None)
            if reply['status'] == 'OK':
                require(control is not None and type(control[1]) is int and control[1] == revision)
                require(reply['state'] == {'pause': 'PAUSED', 'resume': 'READY', 'stop': 'STOPPED'}[control[0]])
            else:
                require(control is None and reply['error'] in ('REVISION_CONFLICT', 'INVALID_LIFECYCLE'))
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError) as error:
            raise LedgerIntegrityError('LEDGER_INTEGRITY: invalid stored receipt') from error
    require(not controls)


class Store:
    def __init__(self, path, generation, *, create=False, autostart=True):
        self.path, self.generation = Path(path), generation
        self.create = create
        self.queue = queue.Queue(maxsize=32)
        self.ready = Future()
        self.failed = threading.Event()
        self.cancel = threading.Event()
        self.thread = threading.Thread(target=self._run, name='LEVIS-database-actor')
        if autostart:
            try:
                self.start()
            except BaseException:
                self.close()
                raise

    def start(self, timeout=10):
        self.thread.start()
        try:
            self.ready.result(timeout=timeout)
        except Exception as error:
            # Caller retains this Store before starting it. Cleanup MUST wait
            # for the actor to exit before relinquishing profile ownership.
            self.cancel.set()
            if isinstance(error, LedgerIntegrityError):
                raise
            raise RuntimeError('Runtime storage startup refused') from error

    def _check_cancel(self):
        if self.cancel.is_set():
            raise RuntimeError('Runtime storage startup cancelled')

    def _event(self, state):
        self._check_cancel()
        previous = self.db.execute('SELECT state FROM runtime WHERE id=1').fetchone()[0]
        exits = {'STARTING': {'RECOVERING'}, 'RECOVERING': {'PAUSED'},
                 'PAUSED': {'READY', 'STOPPING'}, 'READY': {'PAUSED', 'STOPPING'},
                 'STOPPING': {'STOPPED'}, 'STOPPED': set(), 'ERROR': set()}
        if state not in STATES or (state != 'STARTING' and state not in exits[previous]):
            raise ValueError('Prohibited M1.1 lifecycle transition')
        self.db.execute('UPDATE runtime SET state=?, revision=revision+1, clean=?', (state, int(state == 'STOPPED')))
        revision = self.db.execute('SELECT revision FROM runtime').fetchone()[0]
        self.db.execute('INSERT INTO events(generation,state,revision,at) VALUES(?,?,?,?)', (self.generation, state, revision, time.time()))

    def _run(self):
        try:
            self._check_cancel()
            if self.create:
                # Exclusive creation is only allowed by explicit profile init.
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            # mode=rw never fabricates a missing established ledger.
            self.db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=rw', uri=True, timeout=.25, isolation_level=None)
            self.db.execute('PRAGMA busy_timeout=250')
            self.db.execute('PRAGMA trusted_schema=OFF')
            self._check_cancel()
            if self.create:
                self.db.execute('BEGIN IMMEDIATE')
                for sql in DDL:
                    self.db.execute(sql)
                self.db.execute("INSERT INTO runtime VALUES(1,'STOPPED',0,'',1)")
                self.db.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
                self._check_cancel()
                self.db.execute('COMMIT')
            # Reject valid-SQLite but unsupported structure before any lifecycle
            # UPDATE or journaling-mode change can invoke its schema objects.
            if (self.db.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION or
                    schema_inventory(self.db) != expected_schema()):
                raise RuntimeError('Unsupported runtime schema')
            if self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise RuntimeError('Runtime integrity check failed')
            rows = self.db.execute('SELECT id,state,revision,generation,clean FROM runtime').fetchall()
            if (len(rows) != 1 or rows[0][0] != 1 or rows[0][1] not in STATES or
                    type(rows[0][2]) is not int or rows[0][2] < 0 or
                    rows[0][4] != int(rows[0][1] == 'STOPPED')):
                raise RuntimeError('Invalid runtime singleton')
            validate_contents(self.db, rows[0])
            self._check_cancel()
            if self.db.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower() != 'wal':
                raise RuntimeError('WAL unavailable')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA wal_autocheckpoint=100')
            # No evidence eviction: filling this bounded 64 MiB store closes
            # dispatch with SQLITE_FULL instead of growing without a quota.
            if self.db.execute('PRAGMA page_size').fetchone()[0] != 4096:
                raise RuntimeError('Unsupported SQLite page size')
            self.db.execute('PRAGMA max_page_count=16384')
            self.db.execute('PRAGMA journal_size_limit=4194304')
            if self.db.execute('PRAGMA synchronous').fetchone()[0] != 2:
                raise RuntimeError('FULL synchronous unavailable')
            self.db.execute('BEGIN IMMEDIATE')
            previous = self.db.execute('SELECT state,clean FROM runtime').fetchone()
            if previous is None or self.db.execute('SELECT count(*) FROM runtime').fetchone()[0] != 1:
                raise RuntimeError('Invalid runtime singleton')
            self.startup_reason = 'clean' if previous[1] else 'unclean'
            self.db.execute('UPDATE runtime SET generation=?', (self.generation,))
            for state in ('STARTING', 'RECOVERING', 'PAUSED'):
                self._event(state)
            self._check_cancel()
            self.db.execute('COMMIT')
            self.ready.set_result(True)
            while not self.cancel.is_set():
                try:
                    item = self.queue.get(timeout=.1)
                except queue.Empty:
                    continue
                if item is None:
                    break
                request, future = item
                try:
                    future.set_result(self._request(request))
                except sqlite3.Error:
                    # No success receipt on commit failure. In-memory ERROR
                    # closes controls even if the disk cannot journal an error.
                    if self.db.in_transaction:
                        self.db.execute('ROLLBACK')
                    self.failed.set()
                    future.set_result({'request_id': request['request_id'], 'status': 'ERROR', 'error': 'STORAGE_FAILURE', 'runtime_generation': self.generation})
                except BaseException as error:
                    if self.db.in_transaction:
                        self.db.execute('ROLLBACK')
                    self.failed.set()
                    future.set_exception(error)
        except BaseException as error:
            self.failed.set()
            if not self.ready.done():
                self.ready.set_exception(error)
        finally:
            if hasattr(self, 'db'):
                self.db.close()
            # A cancelled startup cannot leave admitted callers waiting forever.
            while True:
                try:
                    item = self.queue.get_nowait()
                except queue.Empty:
                    break
                if item is not None and not item[1].done():
                    item[1].set_exception(RuntimeError('Database actor stopped'))

    def _view(self):
        state, revision, generation, clean = self.db.execute('SELECT state,revision,generation,clean FROM runtime WHERE id=1').fetchone()
        if state not in STATES or clean != int(state == 'STOPPED'):
            raise RuntimeError('Invalid lifecycle observation')
        cursor = self.db.execute('SELECT coalesce(max(cursor),0) FROM events').fetchone()[0]
        return {'state': state, 'revision': revision, 'runtime_generation': generation, 'event_cursor': cursor,
                'clean_shutdown': bool(clean), 'startup_reason': self.startup_reason, 'executor_enabled': False, 'model_enabled': False}

    def _request(self, request):
        # This check precedes validation/SQL: no internal arbitrary command API.
        protocol.validate_request(request)
        if self.failed.is_set():
            return {'request_id': request['request_id'], 'status': 'ERROR', 'error': 'STORAGE_FAILURE', 'runtime_generation': self.generation}
        command = request['command']
        self.db.execute('BEGIN IMMEDIATE' if command in protocol.CONTROLS else 'BEGIN')
        view = self._view()
        response = {'request_id': request['request_id'], 'status': 'OK', **view}
        if command in protocol.READS:
            if command == 'events':
                payload = request['payload']
                rows = self.db.execute('SELECT cursor,generation,state,revision,at FROM events WHERE cursor>? ORDER BY cursor LIMIT ?',
                                       (payload['after'], payload['limit'])).fetchall()
                response['events'] = [dict(zip(('cursor','generation','state','revision','at'), row)) for row in rows]
                response['next_cursor'] = rows[-1][0] if rows else payload['after']
            # Attach/detach are observations only: no dispatch or durable writes.
            if command in ('attach', 'detach'):
                response['attachment'] = 'attached' if command == 'attach' else 'detached'
            self.db.execute('COMMIT')
            return response
        body_hash = hashlib.sha256(protocol.encode(request)).hexdigest()
        key = (request['client_id'], request['request_id'])
        receipt = self.db.execute('SELECT body_hash,response FROM requests WHERE client=? AND id=?', key).fetchone()
        if receipt:
            self.db.execute('COMMIT')
            if receipt[0] != body_hash:
                return {**response, 'status': 'REFUSED', 'error': 'REQUEST_ID_CONFLICT'}
            return json.loads(receipt[1])
        # All receipts retain the generation they committed under. A replay
        # after restart returns historical outcome, never applies it again.
        if request['expected_revision'] != view['revision']:
            response.update(status='REFUSED', error='REVISION_CONFLICT')
        elif view['state'] not in ('PAUSED', 'READY'):
            response.update(status='REFUSED', error='INVALID_LIFECYCLE')
        else:
            target = {'pause': 'PAUSED', 'resume': 'READY', 'stop': 'STOPPING'}[command]
            if target != view['state']:
                self._event(target)
            if command == 'stop':
                self._event('STOPPED')
            response.update(self._view())
            self.db.execute('INSERT INTO controls VALUES(?,?,?,?)', (*key, command, response['revision']))
        self.db.execute('INSERT INTO requests VALUES(?,?,?,?)', (*key, body_hash, protocol.encode(response).decode()))
        self.db.execute('COMMIT')
        return response

    def call(self, request):
        protocol.validate_request(request)
        if threading.current_thread() is self.thread:
            raise RuntimeError('Actor cannot call itself')
        if self.cancel.is_set() or not self.thread.is_alive():
            raise RuntimeError('Database actor is not available')
        if self.failed.is_set():
            return {'request_id': request['request_id'], 'status': 'ERROR', 'error': 'STORAGE_FAILURE', 'runtime_generation': self.generation}
        future = Future()
        self.queue.put((request, future), timeout=.25)
        # A timeout is an unknown outcome, not proof of rollback. The client
        # retains the request identity and must query the identical receipt.
        return future.result(timeout=5)

    def close(self):
        if threading.current_thread() is self.thread:
            raise RuntimeError('Actor cannot join itself')
        self.cancel.set()
        if self.thread.ident is not None:
            # Deliberately no timeout: a hung native operation retains the
            # writer lock until this thread exits or the OS ends the process.
            self.thread.join()
