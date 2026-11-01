"""Review-only reproductions. Does not patch candidate files or legacy profiles."""
from pathlib import Path
import hashlib
import json
import sqlite3
import sys
import tempfile
import threading
import uuid
from unittest.mock import patch
import zipfile

WORKSPACE=next(parent for parent in Path(__file__).resolve().parents
               if (parent/'outputs/LEVIS_M1_1_COORDINATOR_CANDIDATE.zip').is_file())
ROOT=WORKSPACE/'outputs/LEVIS_M1_1_COORDINATOR_CANDIDATE'
sys.path.insert(0,str(ROOT/'LEVIS_STARTER'))
import runtime_store
import runtime_profile
import runtime_ipc_windows as win
from runtime_coordinator import Coordinator


def req(command='status',revision=None):
    return {'protocol_version':1,'client_id':'review','request_id':uuid.uuid4().hex,
            'expected_revision':revision,'command':command,'payload':{}}


archive=WORKSPACE/'outputs/LEVIS_M1_1_COORDINATOR_CANDIDATE.zip'
print('ARCHIVE_SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for line in z.read(ROOT.name+'/MANIFEST_SHA256.txt').decode().splitlines():
        digest,name=line.split('  ',1)
        assert hashlib.sha256(z.read(ROOT.name+'/'+name)).hexdigest()==digest
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
print('ARCHIVE_AND_SOURCE_MANIFEST_MATCH')

with tempfile.TemporaryDirectory(prefix='M11-REVIEW-',dir=WORKSPACE/'work') as scratch:
    base=Path(scratch)
    # Missing DB after an established profile: connect() silently recreates it.
    profile,who,secret=runtime_profile.initialize(base/'lost-db')
    first=runtime_store.Store(profile/'runtime.sqlite3',uuid.uuid4().hex)
    first.call(req('resume',3));first.call(req('stop',4));first.close()
    old=sqlite3.connect(profile/'runtime.sqlite3')
    print('BEFORE_DB_LOSS',old.execute('SELECT revision FROM runtime').fetchone()[0],
          old.execute('SELECT count(*) FROM requests').fetchone()[0]);old.close()
    # Move the disposable test DB aside; never remove any candidate/real DB.
    preserved=base/'preserved-old-runtime.sqlite3'
    (profile/'runtime.sqlite3').rename(preserved)
    runtime_profile.load(profile)
    reopened=runtime_store.Store(profile/'runtime.sqlite3',uuid.uuid4().hex)
    view=reopened.call(req());reopened.close()
    db=sqlite3.connect(profile/'runtime.sqlite3')
    print('MISSING_DB_ACCEPTED',view['state'],view['revision'],'receipts',db.execute('SELECT count(*) FROM requests').fetchone()[0]);db.close()

    # Unknown schema object isn't detected; it can violate the state invariant.
    db_path=base/'unknown-schema.sqlite3'
    original=runtime_store.Store(db_path,uuid.uuid4().hex);original.close()
    db=sqlite3.connect(db_path)
    db.executescript("""CREATE TRIGGER unexpected_schema_trigger AFTER UPDATE OF state ON runtime
        WHEN NEW.state='READY' BEGIN UPDATE runtime SET state='WORKING'; END;""")
    print('UNKNOWN_SCHEMA_QUICK_CHECK',db.execute('PRAGMA quick_check').fetchone()[0]);db.close()
    reopened=runtime_store.Store(db_path,uuid.uuid4().hex)
    status=reopened.call(req());outcome=reopened.call(req('resume',status['revision']));reopened.close()
    print('UNKNOWN_TRIGGER_ACCEPTED',outcome['status'],outcome['state'])

    # Startup timeout releases the OS writer lock while its actor remains alive.
    profile,who,secret=runtime_profile.initialize(base/'startup-timeout')
    gate=threading.Event();actors=[]
    actual_run=runtime_store.Store._run
    actual_result=runtime_store.Future.result
    def delayed(self):
        actors.append(self)
        gate.wait(10)
        actual_run(self)
    def shorten(self,timeout=None):
        return actual_result(self,timeout=.01)
    try:
        with patch.object(runtime_store.Store,'_run',delayed),patch.object(runtime_store.Future,'result',shorten):
            try:Coordinator(profile,who,secret).serve()
            except RuntimeError as error:print('STARTUP_TIMEOUT',str(error))
        actor=actors[0]
        print('ACTOR_ALIVE_AFTER_COORDINATOR_UNWIND',actor.thread.is_alive())
        second_lock=win.ProfileLock(profile)
        try:
            gate.set();actual_result(actor.ready,timeout=5)
            print('OLD_ACTOR_COMMITTED_WHILE_SECOND_OWNER_HOLDS_LOCK',actor.call(req())['state'])
        finally:
            actor.close();second_lock.close()
    finally:
        gate.set()
        for actor in actors:
            actor.close()

print('REVIEW_REPRODUCTIONS_COMPLETED')
