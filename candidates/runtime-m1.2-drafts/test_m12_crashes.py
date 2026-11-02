"""Actual coordinator exits around draft/runtime atomic commit boundaries."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import unittest
from test_m12_windows import Running,ROOT

CHILD='''import sys,os
sys.path.insert(0,sys.argv[1])
import runtime_profile as profiles
import runtime_store as storage
import runtime_protocol as protocol
import draft_repository as repository
from runtime_coordinator import Coordinator
path,mode=sys.argv[2:4]
if mode=='claim-before-commit':
    original=storage.Store._event
    def event(store,state):
        original(store,state)
        if state=='WORKING':os._exit(71)
    storage.Store._event=event
elif mode=='finish-before-commit':
    original=storage.Store._event
    def event(store,state):
        original(store,state)
        if state=='READY' and store.db.execute("SELECT 1 FROM draft_attempts WHERE state='DRAFT_READY'").fetchone():os._exit(72)
    storage.Store._event=event
elif mode=='finish-after-commit':
    original=storage.Store._draft_request
    def request(store,body,raw,**kw):
        result=original(store,body,raw,**kw)
        if body['command']=='finish' and result.get('status')=='OK':os._exit(73)
        return result
    storage.Store._draft_request=request
elif mode=='submit-after-commit':
    original=protocol.Channel.send
    def send(channel,value):
        if isinstance(value,dict) and isinstance(value.get('draft'),dict) and value['draft'].get('result',{}).get('job'):
            os._exit(74)
        return original(channel,value)
    protocol.Channel.send=send
profile,who,secret=profiles.initialize(path)
def adapter(claim,cancel):return dict(kind='draft',text='Synthetic crash-boundary draft')
Coordinator(profile,who,secret,initialize=True,adapter=adapter).serve()
'''


class CoordinatorCrashTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('LEVIS_TEST_PARENT',str(ROOT)));self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'profile'
    def launch(self,mode):
        # Running's custom child path passes delay as argv[3]; use that slot as the mode.
        run=Running(self.path,child=CHILD,delay=mode);self.addCleanup(run.kill);return run
    def wait_exit(self,run,code):
        out,err=run.process.communicate(timeout=10);self.assertEqual(run.process.returncode,code,(out,err))
    def reopen(self):
        run=Running(self.path,initialize=False);self.addCleanup(run.kill);return run

    def test_claim_before_commit_has_no_attempt_and_stays_queued(self):
        run=self.launch('claim-before-commit');job=run.submit();run.control('resume');self.wait_exit(run,71)
        with closing(sqlite3.connect(self.path/'runtime.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM draft_attempts').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT state FROM runtime').fetchone()[0],'READY')
        reopened=self.reopen();self.assertEqual(reopened.jobs()['jobs'][0]['state'],'QUEUED');self.assertTrue(reopened.jobs()['paused']);reopened.stop()

    def test_finish_before_commit_leaves_interrupted_and_orphan(self):
        run=self.launch('finish-before-commit');job=run.submit();run.control('resume');self.wait_exit(run,72)
        with closing(sqlite3.connect(self.path/'runtime.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT state FROM runtime').fetchone()[0],'WORKING')
            self.assertEqual(db.execute('SELECT count(*) FROM draft_artifacts').fetchone()[0],0)
        reopened=self.reopen();row=reopened.jobs()['jobs'][0]
        self.assertEqual(row['state'],'INTERRUPTED');self.assertFalse(row['completed']);self.assertEqual(len(reopened.jobs()['orphans']),1);reopened.stop()

    def test_finish_after_commit_is_completed_without_second_attempt(self):
        run=self.launch('finish-after-commit');job=run.submit();run.control('resume');self.wait_exit(run,73)
        with closing(sqlite3.connect(self.path/'runtime.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT state FROM runtime').fetchone()[0],'READY')
            self.assertEqual(db.execute('SELECT count(*) FROM draft_artifacts').fetchone()[0],1)
        reopened=self.reopen();self.assertTrue(reopened.wait_job(job,'DRAFT_READY')['completed'])
        reopened.control('resume');time.sleep(.2)
        with closing(sqlite3.connect(self.path/'runtime.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM draft_attempts').fetchone()[0],1)
        reopened.stop()

    def test_submit_after_commit_lost_reply_is_recoverable(self):
        run=self.launch('submit-after-commit');revision=run.jobs()['revision']
        payload=dict(goal='Commit before reply',inputs=[],authorization=dict(operator='label',scope='DRAFT_ONLY'))
        from runtime_client import UnconfirmedRequest
        with self.assertRaises(UnconfirmedRequest):run.client.request('job-submit',revision,payload,'lost')
        self.wait_exit(run,74);reopened=self.reopen()
        reply=reopened.client.request('job-submit',revision,payload,'lost')
        self.assertEqual(reply['draft']['status'],'OK');self.assertEqual(reopened.jobs()['job_count'],1);reopened.stop()


if __name__=='__main__':unittest.main(verbosity=2)
