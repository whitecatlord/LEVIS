"""Review regressions. Native Windows; disposable profiles; no continuity claim."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

import runtime_ipc_windows as win
import runtime_profile as profiles
import runtime_store as storage
from runtime_coordinator import Coordinator
from test_runtime_windows import Runtime, request, ROOT, TEST_PARENT


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='M11-REPAIR-',dir=TEST_PARENT)
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)

    def runtime(self):
        run=Runtime(self.base/'profile');self.addCleanup(run.kill)
        return run

    def startup_refused_without_changes(self,path):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir() if p.is_file()}
        proc=subprocess.run([sys.executable,str(ROOT/'runtime_coordinator.py'),'--profile',str(path)],
                            capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,2,proc.stderr)
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir() if p.is_file()}
        self.assertEqual(before,after)

    def test_P1_delayed_startup_retains_writer_until_cancelled_actor_exits(self):
        path,who,secret=profiles.initialize(self.base/'profile')
        gate=threading.Event();entered=threading.Event();errors=[]
        original_run=storage.Store._run;original_start=storage.Store.start
        coordinator=Coordinator(path,who,secret,initialize=True)
        def delayed(store):
            entered.set();gate.wait();original_run(store)
        def short_start(store,timeout=10):
            return original_start(store,timeout=.03)
        def serve():
            try:coordinator.serve()
            except BaseException as error:errors.append(error)
        worker=threading.Thread(target=serve)
        try:
            with patch.object(storage.Store,'_run',delayed),patch.object(storage.Store,'start',short_start):
                worker.start();self.assertTrue(entered.wait(5))
                self.assertTrue(coordinator.store.cancel.wait(5))
                self.assertTrue(worker.is_alive());self.assertTrue(coordinator.store.thread.is_alive())
                with self.assertRaises(OSError):win.ProfileLock(path)
                gate.set();worker.join(5)
                self.assertFalse(worker.is_alive());self.assertFalse(coordinator.store.thread.is_alive())
        finally:
            gate.set();worker.join(5)
        self.assertTrue(errors);self.assertIsInstance(errors[0],RuntimeError)
        self.assertFalse((path/'runtime.sqlite3').exists())
        second=win.ProfileLock(path);second.close()
        # Partial init remains explicit ERROR/refusal, never an implicit retry.
        self.startup_refused_without_changes(path)

    def test_P1_missing_established_ledger_is_not_recreated(self):
        run=self.runtime();status=run.client.request('status')
        run.client.request('resume',status['revision']);run.stop()
        ledger=run.path/'runtime.sqlite3';preserved=self.base/'preserved.sqlite3';ledger.rename(preserved)
        self.startup_refused_without_changes(run.path)
        self.assertFalse(ledger.exists())
        db=sqlite3.connect(preserved)
        try:
            self.assertEqual(db.execute('SELECT revision FROM runtime').fetchone()[0],6)
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0],2)
        finally:db.close()

    def test_P1_timeout_during_startup_transaction_rolls_back_before_unlock(self):
        path,who,secret=profiles.initialize(self.base/'profile')
        gate=threading.Event();entered=threading.Event();errors=[]
        original_event=storage.Store._event;original_start=storage.Store.start
        coordinator=Coordinator(path,who,secret,initialize=True)
        def delayed_event(store,state):
            if state=='STARTING':entered.set();gate.wait()
            original_event(store,state)
        def short_start(store,timeout=10):return original_start(store,timeout=.03)
        def serve():
            try:coordinator.serve()
            except BaseException as error:errors.append(error)
        worker=threading.Thread(target=serve)
        try:
            with patch.object(storage.Store,'_event',delayed_event),patch.object(storage.Store,'start',short_start):
                worker.start();self.assertTrue(entered.wait(5));self.assertTrue(coordinator.store.cancel.wait(5))
                with self.assertRaises(OSError):win.ProfileLock(path)
                gate.set();worker.join(5)
        finally:gate.set();worker.join(5)
        self.assertFalse(worker.is_alive());self.assertTrue(errors)
        self.assertFalse(coordinator.store.thread.is_alive())
        db=sqlite3.connect(path/'runtime.sqlite3')
        try:
            self.assertEqual(db.execute('SELECT state,revision FROM runtime').fetchone(),('STOPPED',0))
            self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],0)
        finally:db.close()
        self.startup_refused_without_changes(path)
        second=win.ProfileLock(path);second.close()

    def test_P1_empty_and_truncated_ledgers_are_not_initialized(self):
        run=self.runtime();run.stop();ledger=run.path/'runtime.sqlite3'
        original=ledger.read_bytes()
        for content in (b'',original[:100],b'\0'*8192):
            with self.subTest(length=len(content)):
                ledger.write_bytes(content)
                self.startup_refused_without_changes(run.path)

    def test_initialization_crash_is_refused_without_secret_overwrite(self):
        path,who,secret=profiles.initialize(self.base/'profile')
        before=(path/'secret.dpapi').read_bytes()
        self.startup_refused_without_changes(path)
        self.assertEqual((path/'secret.dpapi').read_bytes(),before)
        # Even a complete schema left before READY publication stays gated.
        store=storage.Store(path/'runtime.sqlite3',uuid.uuid4().hex,create=True);store.close()
        self.startup_refused_without_changes(path)

    def test_creation_refuses_existing_ledger_and_reopen_requires_existing_file(self):
        path=self.base/'ledger.sqlite3'
        with self.assertRaises(RuntimeError):storage.Store(path,uuid.uuid4().hex)
        self.assertFalse(path.exists())
        store=storage.Store(path,uuid.uuid4().hex,create=True);store.close()
        before=path.read_bytes()
        with self.assertRaises(RuntimeError):storage.Store(path,uuid.uuid4().hex,create=True)
        self.assertEqual(path.read_bytes(),before)

    def test_P2_original_unexpected_trigger_refused_before_startup_mutation(self):
        run=self.runtime();run.stop();ledger=run.path/'runtime.sqlite3'
        db=sqlite3.connect(ledger)
        db.executescript("""CREATE TRIGGER unexpected_schema_trigger AFTER UPDATE OF state ON runtime
            WHEN NEW.state='READY' BEGIN UPDATE runtime SET state='WORKING'; END;""")
        self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0],'ok');db.close()
        self.startup_refused_without_changes(run.path)

    def test_P2_views_indices_columns_constraints_and_version_refused(self):
        run=self.runtime();run.stop();ledger=run.path/'runtime.sqlite3';original=ledger.read_bytes()
        changes=("CREATE VIEW unknown_view AS SELECT state FROM runtime",
                 "CREATE INDEX unknown_index ON controls(command)",
                 "ALTER TABLE controls ADD COLUMN unknown_column TEXT",
                 "PRAGMA user_version=99",
                 "DROP TABLE controls; CREATE TABLE controls(client TEXT,id TEXT,command TEXT,revision INTEGER)")
        for sql in changes:
            with self.subTest(sql=sql):
                ledger.write_bytes(original)
                db=sqlite3.connect(ledger);db.executescript(sql);db.close()
                self.startup_refused_without_changes(run.path)

    @unittest.skip('M1.1-only unreachable WORKING gate; replaced by M1.2 atomic authorized claim controls')
    def test_P2_database_constraints_and_actor_refuse_WORKING(self):
        # Observe actual actor rejection, including its guarded event path.
        class InvalidTransition(storage.Store):
            def _event(self,state):
                super()._event(state)
                if state=='READY':super()._event('WORKING')
        path=self.base/'state.sqlite3';store=InvalidTransition(path,uuid.uuid4().hex,create=True)
        self.addCleanup(store.close)
        with self.assertRaisesRegex(ValueError,'Prohibited'):
            store.call(request('resume',3))
        self.assertTrue(store.failed.is_set())
        db=sqlite3.connect(path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE runtime SET state='WORKING'")
            db.rollback()
            with self.assertRaises(sqlite3.IntegrityError):db.execute("INSERT INTO runtime VALUES(2,'STOPPED',0,'x',1)")
            db.rollback()
            self.assertEqual(db.execute('SELECT state FROM runtime').fetchone()[0],'PAUSED')
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0],0)
        finally:db.close()

    def test_parent_v1_ledger_is_refused_without_implicit_migration(self):
        path=self.base/'parent-v1.sqlite3';db=sqlite3.connect(path)
        db.executescript("""CREATE TABLE runtime(state TEXT NOT NULL,revision INTEGER NOT NULL,generation TEXT NOT NULL,clean INTEGER NOT NULL);
            INSERT INTO runtime VALUES('STOPPED',0,'',1);
            CREATE TABLE events(cursor INTEGER PRIMARY KEY AUTOINCREMENT,generation TEXT,state TEXT,revision INTEGER,at REAL);
            CREATE TABLE requests(client TEXT,id TEXT,body_hash TEXT,response TEXT,PRIMARY KEY(client,id));
            CREATE TABLE controls(client TEXT,id TEXT,command TEXT,revision INTEGER); PRAGMA user_version=1;""")
        db.close();before=path.read_bytes()
        with self.assertRaises(RuntimeError):storage.Store(path,uuid.uuid4().hex)
        self.assertEqual(path.read_bytes(),before)

    def test_cross_logon_policy_gate_no_rekey_or_ledger_write(self):
        run=self.runtime();run.stop()
        metadata=json.loads((run.path/'profile.json').read_bytes())
        self.assertEqual(metadata['continuity_policy'],'SAME_LOGON_ONLY_UNQUALIFIED')
        actual=win.process_identity()
        for who in ({**actual,'logon':'S-1-5-5-99999-99999'}, {**actual,'user':'S-1-5-18'}):
            before={p.name:p.read_bytes() for p in run.path.iterdir() if p.is_file()}
            # Fixture-only identity mismatch; no claim of an actual second logon.
            with patch.object(win,'process_identity',return_value=who):
                if who['user']==actual['user']:
                    with self.assertRaisesRegex(PermissionError,'Cross-logon continuity disabled'):profiles.load(run.path)
                else:
                    with self.assertRaises(PermissionError):profiles.load(run.path)
            self.assertEqual(before,{p.name:p.read_bytes() for p in run.path.iterdir() if p.is_file()})
        metadata['continuity_policy']='AUTO_REKEY'
        profiles.write_metadata(run.path,metadata)
        self.startup_refused_without_changes(run.path)

    def test_same_logon_reopen_preserves_profile_secret_and_receipts(self):
        run=self.runtime();secret=(run.path/'secret.dpapi').read_bytes()
        status=run.client.request('status');receipt=run.client.request('resume',status['revision'],request_id='stable')
        run.stop();metadata=(run.path/'profile.json').read_bytes()
        again=Runtime(run.path,False);self.addCleanup(again.kill)
        self.assertEqual(again.client.request('status')['state'],'PAUSED')
        self.assertEqual(again.client.request('resume',status['revision'],request_id='stable'),receipt)
        self.assertEqual((run.path/'secret.dpapi').read_bytes(),secret)
        self.assertEqual((run.path/'profile.json').read_bytes(),metadata)
        again.stop()


if __name__=='__main__':unittest.main(verbosity=2)
