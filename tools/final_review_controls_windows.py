"""Final review controls; candidate immutable, disposable profiles only.

Failures are left as failures. No candidate repair is performed.
"""
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

WORKSPACE=Path(os.environ['LEVIS_REVIEW_OUTPUT']).resolve()
WORKSPACE.mkdir(parents=True,exist_ok=True)
(WORKSPACE/'work').mkdir(exist_ok=True)
ROOT=Path(__file__).resolve().parents[1]/'candidates/runtime-m1.1-b0/LEVIS_STARTER'
sys.path.insert(0,str(ROOT))
import runtime_store as storage
import runtime_profile as profiles
import runtime_protocol as protocol
import runtime_ipc_windows as win
from runtime_client import Client
from runtime_coordinator import Coordinator
from test_runtime_windows import Runtime,request

OBSERVATIONS={}


def file_hashes(path):return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir() if p.is_file()}


class FinalControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='M11-FINAL-',dir=WORKSPACE/'work')
        self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)

    def runtime(self):
        r=Runtime(self.base/'profile');self.addCleanup(r.kill);return r

    def test_DB01_established_start_timeout_blocks_real_second_process(self):
        r=self.runtime();r.stop()
        path,who,secret=profiles.load(r.path)
        gate=threading.Event();entered=threading.Event();errors=[]
        original=storage.Store._run;start=storage.Store.start
        c=Coordinator(path,who,secret)
        def delayed(actor):entered.set();gate.wait();original(actor)
        def short(actor,timeout=10):return start(actor,timeout=.05)
        def launch():
            try:c.serve()
            except BaseException as e:errors.append(e)
        t=threading.Thread(target=launch)
        try:
            with patch.object(storage.Store,'_run',delayed),patch.object(storage.Store,'start',short):
                t.start();self.assertTrue(entered.wait(5));self.assertTrue(c.store.cancel.wait(5))
                self.assertTrue(c.store.thread.is_alive());self.assertTrue(t.is_alive())
                with self.assertRaises(OSError) as denied:win.ProfileLock(path)
                self.assertEqual(denied.exception.winerror,32)
                second=subprocess.run([sys.executable,str(ROOT/'runtime_coordinator.py'),'--profile',str(path)],
                                      capture_output=True,text=True,timeout=10)
                self.assertEqual(second.returncode,2);self.assertIn('32',second.stderr)
                gate.set();t.join(5)
        finally:gate.set();t.join(5)
        self.assertFalse(t.is_alive());self.assertFalse(c.store.thread.is_alive());self.assertTrue(errors)
        lock=win.ProfileLock(path);lock.close()
        OBSERVATIONS['DB01']={'second_process_exit':second.returncode,'native_sharing_error':32,'actor_dead_before_reacquire':True}

    def test_DB01_cancel_at_schema_COMMIT_retains_lock(self):
        path,who,secret=profiles.initialize(self.base/'profile')
        gate=threading.Event();entered=threading.Event();errors=[]
        connect=sqlite3.connect;start=storage.Store.start
        def trace(sql):
            if sql.strip().upper()=='COMMIT' and not entered.is_set():entered.set();gate.wait()
        def intercepted(*args,**kwargs):
            db=connect(*args,**kwargs)
            if args and args[0]!=':memory:':db.set_trace_callback(trace)
            return db
        def short(actor,timeout=10):return start(actor,timeout=.05)
        c=Coordinator(path,who,secret,initialize=True)
        def launch():
            try:c.serve()
            except BaseException as e:errors.append(e)
        t=threading.Thread(target=launch)
        try:
            with patch.object(storage.sqlite3,'connect',intercepted),patch.object(storage.Store,'start',short):
                t.start();self.assertTrue(entered.wait(5));self.assertTrue(c.store.cancel.wait(5))
                with self.assertRaises(OSError) as denied:win.ProfileLock(path)
                self.assertEqual(denied.exception.winerror,32)
                gate.set();t.join(5)
        finally:gate.set();t.join(5)
        self.assertFalse(t.is_alive());self.assertFalse(c.store.thread.is_alive());self.assertTrue(errors)
        lock=win.ProfileLock(path);lock.close()
        self.assertEqual(json.loads((path/'profile.json').read_bytes())['phase'],'INITIALIZING')
        with self.assertRaises(RuntimeError):profiles.load(path)
        OBSERVATIONS['schema_commit_cancel']='ownership retained until actual actor exit; incomplete profile refused'

    def test_IPC_truncated_frames_do_not_mutate_and_control_survives(self):
        r=self.runtime();initial=r.client.request('status')
        h=win.open_pipe(win.pipe_name(r.path,r.client.who))
        win.write_all(h,b'\x00\x00',time.monotonic()+1);win.close(h)
        self.assertEqual(r.client.request('status',control=True)['revision'],initial['revision'])
        h,ch=r.client.connect()
        win.write_all(h,struct.pack('!I',1000)+b'partial',time.monotonic()+1);win.close(h)
        self.assertEqual(r.client.request('status')['revision'],initial['revision'])
        # Complete authenticated scalar JSON passes MAC but must fail schema.
        h,ch=r.client.connect()
        try:
            raw=b'null';seq=struct.pack('!Q',0)
            protocol.pack(h,seq+protocol.proof(ch.key,b'C',seq+raw)+raw)
            with self.assertRaises((OSError,TimeoutError)):ch.receive()
        finally:win.close(h)
        self.assertEqual(r.client.request('status')['revision'],initial['revision']);r.stop()

    def test_disconnect_after_stop_commit_without_ACK_exits_and_receipt_survives(self):
        r=self.runtime();revision=r.client.request('status')['revision']
        req=request('stop',revision,'disconnect-stop')
        h,ch=r.client.connect(True);ch.send(req);committed=ch.receive();win.close(h)
        self.assertEqual(committed['state'],'STOPPED')
        r.process.wait(timeout=10);self.assertEqual(r.process.returncode,0)
        again=Runtime(r.path,False);self.addCleanup(again.kill)
        result=again.client.request('stop',revision,request_id='disconnect-stop')
        self.assertEqual(result,committed)
        self.assertEqual(again.client.request('status')['state'],'PAUSED')
        again.stop()

    def test_ids_stale_revisions_and_event_receipt_consistency_after_restart(self):
        r=self.runtime();status=r.client.request('status');old_revision=status['revision']
        resume=r.client.request('resume',old_revision,request_id='once')
        self.assertEqual(r.client.request('resume',old_revision,request_id='once'),resume)
        self.assertEqual(r.client.request('pause',old_revision,request_id='once')['error'],'REQUEST_ID_CONFLICT')
        self.assertEqual(r.client.request('pause',old_revision,request_id='stale')['error'],'REVISION_CONFLICT')
        self.assertEqual(r.client.request('status')['revision'],resume['revision'])
        r.kill();again=Runtime(r.path,False);self.addCleanup(again.kill)
        current=again.client.request('status');self.assertGreater(current['revision'],resume['revision'])
        self.assertEqual(again.client.request('resume',old_revision,request_id='once'),resume)
        self.assertEqual(again.client.request('status')['revision'],current['revision'])
        again.stop()
        db=sqlite3.connect(r.path/'runtime.sqlite3')
        try:
            rows=db.execute('SELECT cursor,revision FROM events ORDER BY cursor').fetchall()
            self.assertEqual([x[0] for x in rows],list(range(1,len(rows)+1)))
            self.assertEqual([x[1] for x in rows],list(range(1,len(rows)+1)))
            rev=db.execute('SELECT revision FROM runtime').fetchone()[0];self.assertEqual(rev,rows[-1][1])
            self.assertEqual(db.execute("SELECT count(*) FROM controls WHERE id='once'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT count(*) FROM requests WHERE id='once'").fetchone()[0],1)
        finally:db.close()

    def test_crash_before_control_commit_rolls_back_then_explicit_retry(self):
        marker=self.base/'inside-transaction'
        code=r'''
import os,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import runtime_store as s
import runtime_coordinator as c
original=s.Store._event
marker_path=sys.argv[3]
def event(self,state):
    original(self,state)
    if state=='READY':
        Path(marker_path).write_text('uncommitted lifecycle/event writes')
        while True:time.sleep(.02)
s.Store._event=event
profile=sys.argv[2]
sys.argv=['runtime_coordinator.py','--profile',profile,'--init']
sys.exit(c.main())
'''
        path=self.base/'profile'
        p=subprocess.Popen([sys.executable,'-c',code,str(ROOT),str(path),str(marker)],
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            for _ in range(200):
                if (path/'discovery.json').exists():break
                if p.poll() is not None:raise RuntimeError(p.communicate())
                time.sleep(.02)
            c=Client(path,'test');h,ch=c.connect(True);req=request('resume',3,'precommit')
            ch.send(req)
            for _ in range(200):
                if marker.exists():break
                time.sleep(.02)
            self.assertTrue(marker.exists());p.kill();p.communicate(timeout=10);win.close(h)
        finally:
            if p.poll() is None:p.kill();p.communicate()
        again=Runtime(path,False);self.addCleanup(again.kill)
        current=again.client.request('status');self.assertEqual(current['state'],'PAUSED')
        self.assertEqual(current['revision'],6)
        db=sqlite3.connect(path/'runtime.sqlite3')
        try:
            self.assertEqual(db.execute("SELECT count(*) FROM requests WHERE id='precommit'").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE state='READY'").fetchone()[0],0)
        finally:db.close()
        # Original revision is stale after recovery: an uncommitted request
        # must not become an implicit resume when its lost reply is retried.
        result=again.client.request('resume',3,request_id='precommit')
        self.assertEqual(result['error'],'REVISION_CONFLICT')
        self.assertEqual(again.client.request('status')['state'],'PAUSED');again.stop()

    def test_revision_rollback_with_valid_schema_must_be_refused(self):
        r=self.runtime();r.stop();db=sqlite3.connect(r.path/'runtime.sqlite3')
        try:
            old=db.execute('SELECT revision FROM runtime').fetchone()[0]
            highest=db.execute('SELECT max(revision) FROM events').fetchone()[0]
            db.execute('UPDATE runtime SET revision=0');db.commit()
            self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0],'ok')
        finally:db.close()
        proc=subprocess.Popen([sys.executable,str(ROOT/'runtime_coordinator.py'),'--profile',str(r.path)],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            for _ in range(200):
                if proc.poll() is not None:break
                try:
                    c=Client(r.path,'test');status=c.request('status')
                    if status['runtime_generation']!=json.loads((r.path/'discovery.json').read_bytes())['generation']:continue
                    OBSERVATIONS['revision_corruption']={'before':old,'prior_max_event_revision':highest,'accepted_startup':status}
                    result=c.request('resume',3,request_id='old-snapshot')
                    OBSERVATIONS['revision_corruption']['stale_revision_3_resume']=result
                    break
                except (OSError,RuntimeError,ValueError):time.sleep(.02)
            self.assertIsNotNone(proc.poll(),'Corrupted revision was accepted and stale revision reused: '+json.dumps(OBSERVATIONS.get('revision_corruption')))
            self.assertEqual(proc.returncode,2)
        finally:
            if proc.poll() is None:proc.kill()
            proc.communicate(timeout=10)

    def test_corrupt_receipt_outcome_must_be_refused_before_ready(self):
        r=self.runtime();before=r.client.request('status')
        r.client.request('resume',before['revision'],request_id='receipt-damaged');r.stop()
        db=sqlite3.connect(r.path/'runtime.sqlite3')
        try:
            db.execute("UPDATE requests SET response='{}' WHERE id='receipt-damaged'");db.commit()
            self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0],'ok')
        finally:db.close()
        proc=subprocess.Popen([sys.executable,str(ROOT/'runtime_coordinator.py'),'--profile',str(r.path)],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            for _ in range(200):
                if proc.poll() is not None:break
                try:
                    c=Client(r.path,'test');status=c.request('status')
                    replay=c.request('resume',before['revision'],request_id='receipt-damaged')
                    OBSERVATIONS['receipt_corruption']={'startup':status,'replayed_outcome':replay}
                    cli=subprocess.run([sys.executable,str(ROOT/'runtime_cli.py'),'--profile',str(r.path),
                        '--client-id','test','--request-id','receipt-damaged','--revision',str(before['revision']),'resume'],
                        capture_output=True,text=True,timeout=10)
                    OBSERVATIONS['receipt_corruption']['cli']={'exit':cli.returncode,'stdout':cli.stdout,'stderr':cli.stderr}
                    break
                except (OSError,RuntimeError,ValueError):time.sleep(.02)
            self.assertIsNotNone(proc.poll(),'Corrupted receipt accepted and replayed: '+json.dumps(OBSERVATIONS.get('receipt_corruption')))
            self.assertEqual(proc.returncode,2)
        finally:
            if proc.poll() is None:proc.kill()
            proc.communicate(timeout=10)

    def test_singleton_invalid_state_and_revision_content_are_refused(self):
        r=self.runtime();r.stop();ledger=r.path/'runtime.sqlite3';original=ledger.read_bytes()
        for sql in ('DELETE FROM runtime',"UPDATE runtime SET state='WORKING'",'UPDATE runtime SET revision=-1',
                    "UPDATE runtime SET revision='invalid'",'UPDATE runtime SET id=2'):
            with self.subTest(sql=sql):
                ledger.write_bytes(original);db=sqlite3.connect(ledger)
                db.execute('PRAGMA ignore_check_constraints=ON');db.execute(sql);db.commit();db.close()
                proc=subprocess.run([sys.executable,str(ROOT/'runtime_coordinator.py'),'--profile',str(r.path)],
                                    capture_output=True,text=True,timeout=10)
                self.assertEqual(proc.returncode,2,proc.stderr)


if __name__=='__main__':
    try:unittest.main(verbosity=2)
    finally:
        (WORKSPACE/'work/M1_1_FINAL_OBSERVATIONS.json').write_text(json.dumps(OBSERVATIONS,indent=2)+'\n',encoding='utf-8')
