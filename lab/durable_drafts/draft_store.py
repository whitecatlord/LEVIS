"""LAB ONLY: single-writer draft contracts, not a production runtime or IPC API.

No model, GUI, networking, source-file mutation or command executor is imported.
All callers are trusted harness code; operator attribution is not authentication.
"""
from concurrent.futures import Future
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import sqlite3
import tempfile
import threading
import uuid

MAX_REQUEST = 256 * 1024
STATES = ('QUEUED', 'RUNNING', 'NEEDS_ANSWER', 'DRAFT_READY', 'FAILED', 'INTERRUPTED', 'CANCELLED')
DDL = (
    'CREATE TABLE meta(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, generation TEXT NOT NULL, paused INTEGER NOT NULL CHECK(paused IN (0,1)))',
    'CREATE TABLE jobs(id TEXT PRIMARY KEY, goal TEXT NOT NULL, inputs TEXT NOT NULL, input_hash TEXT NOT NULL, state TEXT NOT NULL, created INTEGER NOT NULL, cancel_requested INTEGER NOT NULL CHECK(cancel_requested IN (0,1)))',
    'CREATE TABLE authorizations(job TEXT NOT NULL, revision INTEGER PRIMARY KEY, operator TEXT NOT NULL, scope TEXT NOT NULL)',
    'CREATE TABLE answers(job TEXT NOT NULL, revision INTEGER PRIMARY KEY, question_attempt TEXT NOT NULL, text TEXT NOT NULL, operator TEXT NOT NULL)',
    'CREATE TABLE attempts(id TEXT PRIMARY KEY, job TEXT NOT NULL, generation TEXT NOT NULL, state TEXT NOT NULL, started INTEGER NOT NULL, previous_attempt TEXT)',
    "CREATE UNIQUE INDEX one_running ON attempts((1)) WHERE state='RUNNING'",
    'CREATE TABLE artifacts(attempt TEXT PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT NOT NULL, kind TEXT NOT NULL)',
    'CREATE TABLE events(revision INTEGER PRIMARY KEY, kind TEXT NOT NULL, job TEXT, attempt TEXT, client TEXT, request_id TEXT, detail TEXT NOT NULL)',
    'CREATE TABLE receipts(client TEXT, request_id TEXT, body TEXT NOT NULL, body_hash TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(client,request_id))',
)


REFUSAL_CODES = frozenset('''ALREADY_TERMINAL ARTIFACT_COUNT_LIMIT ARTIFACT_QUOTA ATTEMPT_COUNT_LIMIT
AUTHORIZATION_REQUIRED CONTINUATION_LIMIT EVENT_PAGE_LIMIT INPUT_CHARACTER_LIMIT INPUT_COUNT_LIMIT
INPUT_HASH_MISMATCH INVALID_FIELDS INVALID_IDENTITY INVALID_PAYLOAD INVALID_SCOPE INVALID_TEXT INVALID_UTF8
JOB_COUNT_LIMIT JOB_PAGE_LIMIT LANE_BUSY NOT_WAITING_FOR_ANSWER NO_COMMITTED_ARTIFACT NO_ELIGIBLE_JOB
PAUSED QUESTION_UNAVAILABLE RETRY_REQUIRES_TERMINAL_FAILURE REVISION_CONFLICT STALE_ATTEMPT UNKNOWN_COMMAND
UNKNOWN_JOB UNSUPPORTED_OUTPUT_KIND'''.split())
MUTATIONS = frozenset('submit resume pause claim finish answer retry cancel'.split())


def artifact_bytes(path):
    if path.is_symlink() or not path.is_file():
        return None
    with path.open('rb') as source:
        raw = source.read(120001)
    return raw if len(raw) <= 120000 else None


class IntegrityError(RuntimeError):
    pass


class Refused(ValueError):
    pass


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise Refused('INVALID_FIELDS')


def text(value, limit, *, empty=False):
    if type(value) is not str or len(value) > limit or (not empty and not value.strip()) or '\x00' in value:
        raise Refused('INVALID_TEXT')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise Refused('INVALID_UTF8') from error
    return value


def identity(value):
    if type(value) is not str or re.fullmatch('[A-Za-z0-9_-]{1,64}', value) is None:
        raise Refused('INVALID_IDENTITY')
    return value


def authorization(value):
    fields(value, 'operator scope')
    text(value['operator'], 128)
    if value['scope'] != 'DRAFT_ONLY':
        raise Refused('INVALID_SCOPE')


class WriterLock:
    """LAB advisory ownership. Keep the lock inode; never unlink it on close."""
    def __init__(self, path):
        self.file = open(path, 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0, 2)
                if self.file.tell() == 0:
                    self.file.write(b'0')
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.file.close()
            raise

    def close(self):
        self.file.close()


def schema(db):
    return db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()


def expected_schema():
    with sqlite3.connect(':memory:') as db:
        for statement in DDL:
            db.execute(statement)
        return schema(db)


class DraftStore:
    """Actor-owned SQLite and artifacts. Explicit claim is the fake scheduler ABI."""
    def __init__(self, profile, *, create=False):
        self.profile = Path(profile).absolute()
        if create:
            self.profile.mkdir(parents=False, exist_ok=False)
        if self.profile.is_symlink() or not self.profile.is_dir():
            raise Refused('ORDINARY_ISOLATED_PROFILE_REQUIRED')
        self.lock = WriterLock(self.profile/'writer.lock')
        self.generation = uuid.uuid4().hex
        self.ready = Future()
        self.queue = queue.Queue(maxsize=32)
        self.stopping = threading.Event()
        self.failed = threading.Event()
        self.thread = threading.Thread(target=self._run, args=(create,), name='LAB-draft-database-actor')
        try:
            self.thread.start()
            self.ready.result(timeout=10)
        except BaseException:
            self.close()
            raise

    def call(self, command, payload=None, *, client='operator-harness', request_id=None, revision=None):
        body = dict(version=1, command=command, payload={} if payload is None else payload,
                    client=client, request_id=request_id or uuid.uuid4().hex, expected_revision=revision)
        # Copy once: caller mutation cannot change an admitted request.
        raw = encode(body)
        if len(raw) > MAX_REQUEST:
            raise Refused('REQUEST_SIZE_LIMIT')
        body = decode(raw)
        identity(client)
        identity(body['request_id'])
        if command not in {'snapshot','events','artifact','submit','resume','pause','claim','finish','answer','retry','cancel'}:
            raise Refused('UNKNOWN_COMMAND')
        if type(body['payload']) is not dict:
            raise Refused('INVALID_PAYLOAD')
        if command not in ('snapshot', 'events', 'artifact') and (type(revision) is not int or revision < 0):
            raise Refused('REVISION_REQUIRED')
        if self.stopping.is_set() or self.failed.is_set() or not self.thread.is_alive():
            raise RuntimeError('ACTOR_CLOSED')
        future = Future()
        self.queue.put((body, raw, future), timeout=.25)
        return future.result(timeout=5)  # Timeout is UNKNOWN; retain identical identity/body.

    def close(self):
        if threading.current_thread() is self.thread:
            raise RuntimeError('actor cannot join itself')
        self.stopping.set()
        if self.thread.ident is not None:
            self.thread.join()
        self.lock.close()

    def _run(self, create):
        db = None
        try:
            path = self.profile/'drafts.sqlite3'
            artifacts = self.profile/'artifacts'
            if path.is_symlink() or artifacts.is_symlink():
                raise IntegrityError('LINKED_STORAGE_REFUSED')
            if create:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(fd)
                artifacts.mkdir(exist_ok=False)
            if not artifacts.is_dir():
                raise IntegrityError('ARTIFACT_DIRECTORY_MISSING')
            db = self.db = sqlite3.connect(path.as_uri()+'?mode=rw', uri=True, isolation_level=None, timeout=.25)
            db.execute('PRAGMA trusted_schema=OFF')
            if create:
                db.execute('BEGIN IMMEDIATE')
                for statement in DDL:
                    db.execute(statement)
                db.execute("INSERT INTO meta VALUES(1,0,'',1)")
                db.execute('PRAGMA user_version=1')
                db.execute('COMMIT')
            if db.execute('PRAGMA user_version').fetchone()[0] != 1 or schema(db) != expected_schema():
                raise IntegrityError('UNKNOWN_SCHEMA')
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise IntegrityError('SQLITE_INTEGRITY')
            if db.execute('PRAGMA page_size').fetchone()[0] != 4096:
                raise IntegrityError('UNSUPPORTED_PAGE_SIZE')
            self._validate()
            if db.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower() != 'wal':
                raise RuntimeError('WAL_REQUIRED')
            db.execute('PRAGMA synchronous=FULL')
            if db.execute('PRAGMA synchronous').fetchone()[0] != 2:
                raise RuntimeError('FULL_SYNC_REQUIRED')
            db.execute('PRAGMA max_page_count=16384')
            db.execute('PRAGMA journal_size_limit=4194304')
            db.execute('BEGIN IMMEDIATE')
            interrupted = db.execute("SELECT id,job FROM attempts WHERE state='RUNNING'").fetchall()
            for attempt, job in interrupted:
                db.execute("UPDATE attempts SET state='INTERRUPTED' WHERE id=?", (attempt,))
                db.execute("UPDATE jobs SET state='INTERRUPTED',cancel_requested=0 WHERE id=?", (job,))
            db.execute('UPDATE meta SET generation=?,paused=1', (self.generation,))
            self._event('RECOVERY', detail=dict(generation=self.generation, interrupted=[x[0] for x in interrupted], orphans=self._orphans()))
            db.execute('COMMIT')
            self.ready.set_result(True)
            while not self.stopping.is_set():
                try:
                    body, raw, future = self.queue.get(timeout=.05)
                except queue.Empty:
                    continue
                try:
                    future.set_result(self._request(body, raw))
                except Refused as error:
                    future.set_exception(error)
                except BaseException as error:
                    if db.in_transaction:
                        db.execute('ROLLBACK')
                    self.failed.set()
                    future.set_exception(error)
                    break
        except BaseException as error:
            self.failed.set()
            if not self.ready.done():
                self.ready.set_exception(error)
        finally:
            if db is not None:
                db.close()
            while True:
                try:
                    _, _, future = self.queue.get_nowait()
                    future.set_exception(RuntimeError('ACTOR_CLOSED'))
                except queue.Empty:
                    break

    def _revision(self):
        return self.db.execute('SELECT revision FROM meta WHERE id=1').fetchone()[0]

    def _event(self, kind, job=None, attempt=None, body=None, detail=None):
        self.db.execute('UPDATE meta SET revision=revision+1')
        revision = self._revision()
        self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)',
                        (revision, kind, job, attempt, body['client'] if body else None,
                         body['request_id'] if body else None, encode(detail or {}).decode()))
        return revision

    def _orphans(self):
        known = {row[0] for row in self.db.execute('SELECT name FROM artifacts')}
        result = []
        entries = sorted((self.profile/'artifacts').iterdir())
        if len(entries)>1024:
            raise IntegrityError('ARTIFACT_COUNT_LIMIT')
        for path in entries:
            if path.is_symlink() or not path.is_file():
                raise IntegrityError('UNSUPPORTED_ARTIFACT_ENTRY')
            if path.name not in known:
                raw = artifact_bytes(path)
                result.append(dict(name=path.name, sha256=digest(raw) if raw is not None else None))
        return result

    def _snapshot(self, after=0, limit=25):
        revision, generation, paused = self.db.execute('SELECT revision,generation,paused FROM meta').fetchone()
        jobs = []
        cursor = after
        for job, goal, state, cancel, created in self.db.execute('SELECT id,goal,state,cancel_requested,created FROM jobs WHERE created>? ORDER BY created LIMIT ?', (after,limit)):
            cursor = created
            artifacts = []
            for attempt, name, sha, kind in self.db.execute('SELECT a.attempt,a.name,a.sha256,a.kind FROM artifacts a JOIN attempts t ON t.id=a.attempt WHERE t.job=? ORDER BY t.started', (job,)):
                path = self.profile/'artifacts'/name
                content = artifact_bytes(path)
                valid = content is not None and digest(content) == sha
                artifacts.append(dict(attempt=attempt, kind=kind, sha256=sha,
                                      integrity='VALID' if valid else 'CORRUPT_OR_MISSING'))
            valid_completion = (state == 'DRAFT_READY' and bool(artifacts) and artifacts[-1]['kind'] == 'draft' and artifacts[-1]['integrity'] == 'VALID')
            display_state = state
            if state in ('DRAFT_READY','NEEDS_ANSWER') and (not artifacts or artifacts[-1]['integrity'] != 'VALID'):
                display_state = 'CORRUPT_OR_MISSING'
            jobs.append(dict(id=job, goal=goal, state=state, display_state=display_state, completed=valid_completion, cancel_requested=bool(cancel), artifacts=artifacts))
        active = self.db.execute("SELECT id FROM attempts WHERE state='RUNNING'").fetchone()
        return dict(revision=revision, generation=generation, paused=bool(paused), active_attempt=active[0] if active else None,
                    jobs=jobs, next_cursor=cursor, has_more=bool(self.db.execute('SELECT 1 FROM jobs WHERE created>?',(cursor,)).fetchone()), job_count=self.db.execute('SELECT count(*) FROM jobs').fetchone()[0],
                    orphans=self._orphans(), executor_enabled=False, model_enabled=False)

    def _request(self, body, raw):
        command, payload = body['command'], body['payload']
        if command in ('snapshot', 'events', 'artifact'):
            if command == 'snapshot':
                if not payload:
                    return self._snapshot()
                fields(payload, 'after limit')
                if type(payload['after']) is not int or payload['after']<0 or type(payload['limit']) is not int or not 1<=payload['limit']<=25:
                    raise Refused('JOB_PAGE_LIMIT')
                return self._snapshot(payload['after'],payload['limit'])
            if command == 'artifact':
                fields(payload, 'attempt')
                identity(payload['attempt'])
                row = self.db.execute('SELECT name,sha256,kind FROM artifacts WHERE attempt=?',(payload['attempt'],)).fetchone()
                if row is None:
                    raise Refused('NO_COMMITTED_ARTIFACT')
                path = self.profile/'artifacts'/row[0]
                content = artifact_bytes(path)
                valid = content is not None and digest(content)==row[1]
                return dict(attempt=payload['attempt'],kind=row[2],sha256=row[1],integrity='VALID' if valid else 'CORRUPT_OR_MISSING',text=content.decode('utf-8') if valid else None)
            fields(payload, 'after limit')
            if type(payload['after']) is not int or payload['after'] < 0 or type(payload['limit']) is not int or not 1 <= payload['limit'] <= 100:
                raise Refused('EVENT_PAGE_LIMIT')
            return [dict(revision=r, kind=k, job=j, attempt=a, detail=decode(d)) for r,k,j,a,d in
                    self.db.execute('SELECT revision,kind,job,attempt,detail FROM events WHERE revision>? ORDER BY revision LIMIT ?', (payload['after'],payload['limit']))]
        self.db.execute('BEGIN IMMEDIATE')
        saved = self.db.execute('SELECT body_hash,response FROM receipts WHERE client=? AND request_id=?', (body['client'],body['request_id'])).fetchone()
        if saved:
            self.db.execute('COMMIT')
            if saved[0] != digest(raw):
                return dict(status='REFUSED', error='REQUEST_ID_CONFLICT', revision=self._revision(), result={})
            return decode(saved[1])
        try:
            if body['expected_revision'] != self._revision():
                raise Refused('REVISION_CONFLICT')
            # Payload validation precedes every semantic write.
            result = self._mutate(body)
            reply = dict(status='OK', revision=self._revision(), result=result)
        except Refused as error:
            # Roll back any side effect of a refused command, retaining only its receipt.
            self.db.execute('ROLLBACK')
            self.db.execute('BEGIN IMMEDIATE')
            reply = dict(status='REFUSED', error=str(error), revision=self._revision(), result={})
        self.db.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',
                        (body['client'],body['request_id'],raw.decode(),digest(raw),encode(reply).decode()))
        self.db.execute('COMMIT')
        return reply

    def _job(self, job):
        identity(job)
        row = self.db.execute('SELECT state,cancel_requested FROM jobs WHERE id=?', (job,)).fetchone()
        if row is None:
            raise Refused('UNKNOWN_JOB')
        return row

    def _authorize(self, job, value, revision):
        self.db.execute('INSERT INTO authorizations VALUES(?,?,?,?)', (job,revision,value['operator'],value['scope']))

    def _mutate(self, body):
        command, p = body['command'], body['payload']
        if command in ('resume','pause'):
            fields(p, '')
            self.db.execute('UPDATE meta SET paused=?', (int(command == 'pause'),))
            self._event(command.upper(), body=body)
            active = self.db.execute("SELECT id FROM attempts WHERE state='RUNNING'").fetchone()
            return dict(dispatch='DRAINING' if command == 'pause' and active else ('PAUSED' if command == 'pause' else 'READY'))
        if command == 'submit':
            fields(p, 'goal inputs authorization')
            text(p['goal'],3000)
            authorization(p['authorization'])
            if type(p['inputs']) is not list or len(p['inputs']) > 32:
                raise Refused('INPUT_COUNT_LIMIT')
            total = 0
            for item in p['inputs']:
                fields(item, 'name text sha256')
                text(item['name'],256)
                text(item['text'],10000,empty=True)
                if item['sha256'] != digest(item['text'].encode('utf-8')):
                    raise Refused('INPUT_HASH_MISMATCH')
                total += len(item['text'])
            if total > 10000:
                raise Refused('INPUT_CHARACTER_LIMIT')
            if self.db.execute('SELECT count(*) FROM jobs').fetchone()[0]>=256:
                raise Refused('JOB_COUNT_LIMIT')
            job = uuid.uuid4().hex
            revision = self._event('SUBMITTED', job=job, body=body)
            raw = encode(p['inputs'])
            self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,0)', (job,p['goal'],raw.decode(),digest(raw),'QUEUED',revision))
            self._authorize(job,p['authorization'],revision)
            return dict(job=job)
        if command == 'claim':
            fields(p, '')
            if self.db.execute('SELECT paused FROM meta').fetchone()[0]:
                raise Refused('PAUSED')
            if self.db.execute("SELECT 1 FROM attempts WHERE state='RUNNING'").fetchone():
                raise Refused('LANE_BUSY')
            row = self.db.execute("SELECT id,goal,inputs FROM jobs WHERE state='QUEUED' ORDER BY created LIMIT 1").fetchone()
            if not row:
                raise Refused('NO_ELIGIBLE_JOB')
            job, goal, inputs = row
            if self.db.execute('SELECT count(*) FROM attempts WHERE job=?',(job,)).fetchone()[0]>=32:
                raise Refused('ATTEMPT_COUNT_LIMIT')
            if not self.db.execute("SELECT 1 FROM authorizations WHERE job=? AND scope='DRAFT_ONLY'",(job,)).fetchone():
                raise Refused('AUTHORIZATION_REQUIRED')
            attempt = uuid.uuid4().hex
            previous = self.db.execute('SELECT id FROM attempts WHERE job=? ORDER BY started DESC LIMIT 1',(job,)).fetchone()
            revision = self._event('CLAIMED',job,attempt,body)
            self.db.execute("INSERT INTO attempts VALUES(?,?,?,'RUNNING',?,?)",(attempt,job,self.generation,revision,previous[0] if previous else None))
            self.db.execute("UPDATE jobs SET state='RUNNING',cancel_requested=0 WHERE id=?",(job,))
            answers = self._answers(job)
            return dict(job=job,attempt=attempt,generation=self.generation,goal=goal,inputs=decode(inputs),answers=answers)
        if command == 'finish':
            fields(p, 'attempt generation kind text')
            identity(p['attempt']); identity(p['generation']); text(p['text'],30000)
            if p['kind'] not in ('draft','question','failure'):
                raise Refused('UNSUPPORTED_OUTPUT_KIND')
            if p['kind'] == 'question':
                text(p['text'],3000)
            row = self.db.execute('SELECT job,state,generation FROM attempts WHERE id=?',(p['attempt'],)).fetchone()
            if row is None or row[1] != 'RUNNING' or row[2] != self.generation or p['generation'] != self.generation:
                raise Refused('STALE_ATTEMPT')
            job = row[0]
            cancelled = self._job(job)[1]
            state = 'CANCELLED' if cancelled else {'draft':'DRAFT_READY','question':'NEEDS_ANSWER','failure':'FAILED'}[p['kind']]
            kind = 'cancelled-output' if cancelled else p['kind']
            raw = p['text'].encode('utf-8')
            name = self._write_artifact(p['attempt'],raw)
            self.db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(p['attempt'],name,digest(raw),kind))
            self.db.execute('UPDATE attempts SET state=? WHERE id=?',(state,p['attempt']))
            self.db.execute('UPDATE jobs SET state=?,cancel_requested=0 WHERE id=?',(state,job))
            self._event('FINISHED',job,p['attempt'],body,dict(state=state,kind=kind,sha256=digest(raw)))
            return dict(job=job,attempt=p['attempt'],state=state,sha256=digest(raw))
        if command in ('answer','retry'):
            fields(p, 'job authorization text' if command == 'answer' else 'job authorization')
            authorization(p['authorization'])
            state, _ = self._job(p['job'])
            if command == 'answer':
                text(p['text'],3000)
                if state != 'NEEDS_ANSWER':
                    raise Refused('NOT_WAITING_FOR_ANSWER')
                last = self.db.execute('SELECT id FROM attempts WHERE job=? ORDER BY started DESC LIMIT 1',(p['job'],)).fetchone()[0]
                question = self._question(last)
                used = sum(len(a['text'])+len(a['question']) for a in self._answers(p['job']))
                if used + len(question) + len(p['text']) > 6000:
                    raise Refused('CONTINUATION_LIMIT')
            elif state not in ('FAILED','INTERRUPTED','CANCELLED'):
                raise Refused('RETRY_REQUIRES_TERMINAL_FAILURE')
            revision = self._event(command.upper(),p['job'],body=body)
            self._authorize(p['job'],p['authorization'],revision)
            if command == 'answer':
                attempt = self.db.execute('SELECT id FROM attempts WHERE job=? ORDER BY started DESC LIMIT 1',(p['job'],)).fetchone()[0]
                self.db.execute('INSERT INTO answers VALUES(?,?,?,?,?)',(p['job'],revision,attempt,p['text'],p['authorization']['operator']))
            self.db.execute("UPDATE jobs SET state='QUEUED',cancel_requested=0 WHERE id=?",(p['job'],))
            return dict(job=p['job'],state='QUEUED')
        if command == 'cancel':
            fields(p, 'job')
            state, _ = self._job(p['job'])
            if state == 'DRAFT_READY' or state == 'CANCELLED':
                raise Refused('ALREADY_TERMINAL')
            if state == 'RUNNING':
                self.db.execute('UPDATE jobs SET cancel_requested=1 WHERE id=?',(p['job'],))
                result = 'CANCEL_PENDING'
            else:
                self.db.execute("UPDATE jobs SET state='CANCELLED',cancel_requested=0 WHERE id=?",(p['job'],))
                result = 'CANCELLED'
            self._event('CANCEL',p['job'],body=body)
            return dict(job=p['job'],state=result)
        raise Refused('UNKNOWN_COMMAND')

    def _question(self, attempt):
        row = self.db.execute("SELECT name,sha256 FROM artifacts WHERE attempt=? AND kind='question'",(attempt,)).fetchone()
        if row is None:
            raise Refused('QUESTION_UNAVAILABLE')
        path = self.profile/'artifacts'/row[0]
        if path.is_symlink() or not path.is_file():
            raise Refused('QUESTION_UNAVAILABLE')
        raw = artifact_bytes(path)
        if raw is None or digest(raw) != row[1]:
            raise Refused('QUESTION_UNAVAILABLE')
        return raw.decode('utf-8')

    def _answers(self, job):
        return [dict(question_attempt=a,question=self._question(a),text=t,operator=o) for a,t,o in self.db.execute('SELECT question_attempt,text,operator FROM answers WHERE job=? ORDER BY revision',(job,))]

    def _write_artifact(self, attempt, raw):
        folder = self.profile/'artifacts'
        entries = list(folder.iterdir())
        if len(entries)>=1024:
            raise Refused('ARTIFACT_COUNT_LIMIT')
        if sum(p.stat().st_size for p in entries) + len(raw) > 64*1024*1024:
            raise Refused('ARTIFACT_QUOTA')
        target = folder/(attempt+'.txt')
        if target.exists():
            raise IntegrityError('ATTEMPT_ARTIFACT_EXISTS')
        with tempfile.NamedTemporaryFile(dir=folder,prefix=attempt+'-',suffix='.pending',delete=False) as temporary:
            temporary.write(raw)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name,target)
        return target.name

    def _validate(self):
        """Defined detectable consistency floor; not an external trust anchor."""
        def require(condition):
            if not condition:
                raise IntegrityError('LEDGER_CONTENT_INCONSISTENCY')
        meta = self.db.execute('SELECT id,revision,generation,paused FROM meta').fetchall()
        require(len(meta)==1 and meta[0][0]==1 and type(meta[0][1]) is int and meta[0][1]>=0 and meta[0][3] in (0,1))
        events = self.db.execute('SELECT revision,kind,job,attempt,client,request_id,detail FROM events ORDER BY revision').fetchall()
        require(len(events) == meta[0][1] and all(e[0]==index for index,e in enumerate(events,1)))
        recoveries = [decode(e[6]) for e in events if e[1]=='RECOVERY']
        require((recoveries[-1]['generation'] if recoveries else '') == meta[0][2])
        for event in events:
            require(event[1] in ('RECOVERY','SUBMITTED','RESUME','PAUSE','CLAIMED','FINISHED','ANSWER','RETRY','CANCEL'))
            require(type(decode(event[6])) is dict)
            require((event[4] is None and event[5] is None) if event[1]=='RECOVERY' else (event[4] is not None and event[5] is not None))
        keys = {(e[4],e[5]):e[0] for e in events if e[4] is not None}
        keyed = [e for e in events if e[4] is not None]
        require(len(keys)==len(keyed))
        receipt_keys = set()
        for client, rid, body, sha, response in self.db.execute('SELECT * FROM receipts'):
            receipt_keys.add((client,rid))
            try:
                identity(client); identity(rid)
                parsed = decode(body); outcome = decode(response)
                fields(parsed, 'version command payload client request_id expected_revision')
                require(digest(body.encode())==sha and encode(parsed).decode()==body and parsed['client']==client and parsed['request_id']==rid and type(parsed['version']) is int and parsed['version']==1)
                fields(outcome, 'status revision result' if outcome.get('status')=='OK' else 'status error revision result')
                require(outcome['status'] in ('OK','REFUSED') and type(outcome['revision']) is int and 0<=outcome['revision']<=meta[0][1] and type(outcome['result']) is dict)
                require(type(parsed['command']) is str and parsed['command'] in MUTATIONS and type(parsed['payload']) is dict and type(parsed['expected_revision']) is int and parsed['expected_revision']>=0)
                require((keys.get((client,rid))==outcome['revision']) if outcome['status']=='OK' else (client,rid) not in keys)
                if outcome['status']=='REFUSED':
                    require(outcome['result']=={} and type(outcome['error']) is str and outcome['error'] in REFUSAL_CODES)
                else:
                    require(parsed['expected_revision']==outcome['revision']-1)
                    self._validate_outcome(parsed,outcome,events[outcome['revision']-1])
            except (ValueError,KeyError,TypeError,AttributeError) as error:
                raise IntegrityError('INVALID_RECEIPT') from error
        require(set(keys) <= receipt_keys)
        for job, goal, inputs, sha, state, created, cancel in self.db.execute('SELECT * FROM jobs'):
            require(state in STATES and cancel in (0,1) and digest(inputs.encode())==sha)
            require(not cancel or state=='RUNNING')
            submitted = next((e for e in events if e[0]==created),None)
            require(submitted is not None)
            original = self.db.execute('SELECT body FROM receipts WHERE client=? AND request_id=?',(submitted[4],submitted[5])).fetchone()
            require(original is not None)
            original = decode(original[0])['payload']
            require(original['goal']==goal and encode(original['inputs']).decode()==inputs)
            require(any(e[0]==created and e[1]=='SUBMITTED' and e[2]==job for e in events))
            require(bool(self.db.execute("SELECT 1 FROM authorizations WHERE job=? AND scope='DRAFT_ONLY'",(job,)).fetchone()))
            running = self.db.execute("SELECT id FROM attempts WHERE job=? AND state='RUNNING'",(job,)).fetchall()
            require((len(running)==1) == (state=='RUNNING'))
            if state in ('DRAFT_READY','NEEDS_ANSWER','FAILED','INTERRUPTED'):
                latest = self.db.execute('SELECT id,state FROM attempts WHERE job=? ORDER BY started DESC LIMIT 1',(job,)).fetchone()
                require(latest is not None and latest[1]==state)
                if state != 'INTERRUPTED':
                    output = self.db.execute('SELECT kind FROM artifacts WHERE attempt=?',(latest[0],)).fetchone()
                    require(output is not None and output[0]=={'DRAFT_READY':'draft','NEEDS_ANSWER':'question','FAILED':'failure'}[state])
        for attempt, job, generation, state, started, previous in self.db.execute('SELECT * FROM attempts'):
            identity(attempt); identity(job); identity(generation)
            require(state in STATES and state not in ('QUEUED',))
            require(bool(self.db.execute('SELECT 1 FROM jobs WHERE id=?',(job,)).fetchone()))
            if state=='RUNNING':
                require(generation==meta[0][2])
            require(any(e[0]==started and e[1]=='CLAIMED' and e[2]==job and e[3]==attempt for e in events))
            if previous:
                require(bool(self.db.execute('SELECT 1 FROM attempts WHERE id=? AND job=? AND started<?',(previous,job,started)).fetchone()))
        for attempt,name,sha,kind in self.db.execute('SELECT * FROM artifacts'):
            identity(attempt)
            require(name==attempt+'.txt' and re.fullmatch('[0-9a-f]{64}',sha) is not None and kind in ('draft','question','failure','cancelled-output'))
            require(bool(self.db.execute('SELECT 1 FROM attempts WHERE id=?',(attempt,)).fetchone()))

        for job,revision,operator,scope in self.db.execute('SELECT * FROM authorizations'):
            require(scope=='DRAFT_ONLY' and type(operator) is str and bool(operator.strip()))
            require(any(e[0]==revision and e[2]==job and e[1] in ('SUBMITTED','RETRY','ANSWER') for e in events))
        for job,revision,attempt,answer,operator in self.db.execute('SELECT * FROM answers'):
            require(any(e[0]==revision and e[2]==job and e[1]=='ANSWER' for e in events))
            require(bool(self.db.execute("SELECT 1 FROM attempts WHERE id=? AND job=? AND state='NEEDS_ANSWER'",(attempt,job)).fetchone()))

    def _validate_outcome(self, body, outcome, event):
        def require(value):
            if not value:
                raise IntegrityError('RECEIPT_OUTCOME_INCONSISTENCY')
        result = outcome['result']
        command = body['command']
        expected_kind = dict(submit='SUBMITTED',resume='RESUME',pause='PAUSE',claim='CLAIMED',finish='FINISHED',answer='ANSWER',retry='RETRY',cancel='CANCEL')[command]
        require(event[1]==expected_kind)
        shape = dict(submit='job',resume='dispatch',pause='dispatch',claim='job attempt generation goal inputs answers',finish='job attempt state sha256',answer='job state',retry='job state',cancel='job state')[command]
        fields(result, shape)
        if 'job' in result:
            require(result['job']==event[2])
            identity(result['job'])
        if command in ('resume','pause'):
            require(result['dispatch'] in (('READY',) if command=='resume' else ('PAUSED','DRAINING')))
        if command in ('answer','retry'):
            require(result['state']=='QUEUED' and result['job']==body['payload']['job'])
        if command=='cancel':
            require(result['state'] in ('CANCELLED','CANCEL_PENDING') and result['job']==body['payload']['job'])
        if command=='claim':
            row=self.db.execute('SELECT job,generation FROM attempts WHERE id=?',(result['attempt'],)).fetchone()
            require(row is not None and row==(result['job'],result['generation']) and result['attempt']==event[3])
            job=self.db.execute('SELECT goal,inputs FROM jobs WHERE id=?',(result['job'],)).fetchone()
            require(job is not None and job[0]==result['goal'] and decode(job[1])==result['inputs'])
            require(type(result['answers']) is list)
            answers=self.db.execute('SELECT question_attempt,text,operator FROM answers WHERE job=? AND revision<? ORDER BY revision',(result['job'],event[0])).fetchall()
            require(len(answers)==len(result['answers']))
            for supplied,stored in zip(result['answers'],answers):
                fields(supplied,'question_attempt question text operator')
                require((supplied['question_attempt'],supplied['text'],supplied['operator'])==stored)
                sha=self.db.execute("SELECT sha256 FROM artifacts WHERE attempt=? AND kind='question'",(stored[0],)).fetchone()
                require(sha is not None and type(supplied['question']) is str and digest(supplied['question'].encode())==sha[0])
        if command=='finish':
            require(result['attempt']==event[3] and result['state'] in ('DRAFT_READY','NEEDS_ANSWER','FAILED','CANCELLED'))
            artifact=self.db.execute('SELECT sha256 FROM artifacts WHERE attempt=?',(result['attempt'],)).fetchone()
            require(artifact is not None and artifact[0]==result['sha256'])
            detail=decode(event[6])
            require(detail['state']==result['state'] and detail['sha256']==result['sha256'])
