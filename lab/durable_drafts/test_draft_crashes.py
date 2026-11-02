"""Whole-process exits; process loss is not hardware power-loss testing."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from draft_store import DraftStore
AUTH=dict(operator='test-operator',scope='DRAFT_ONLY')


def operation(store,command,payload=None,request_id=None):
    return store.call(command,payload,revision=store.call('snapshot')['revision'],request_id=request_id)


def child(profile,phase):
    store=DraftStore(profile,create=True)
    operation(store,'submit',dict(goal='Draft only',inputs=[],authorization=AUTH))
    operation(store,'resume')
    claim=operation(store,'claim')['result']
    if phase=='after-claim':os._exit(73)
    if phase=='pending-file':
        def write(attempt,raw):
            path=store.profile/'artifacts'/(attempt+'.pending')
            with path.open('xb') as output:
                output.write(raw);output.flush();os.fsync(output.fileno())
            os._exit(73)
        store._write_artifact=write
    if phase=='after-rename':
        original=store._write_artifact
        def write(attempt,raw):
            original(attempt,raw);os._exit(73)
        store._write_artifact=write
    if phase=='before-commit':
        original=store._request
        def request(body,raw):
            if body['command']=='finish':
                def trace(sql):
                    if sql=='COMMIT':os._exit(73)
                store.db.set_trace_callback(trace)
            return original(body,raw)
        store._request=request
    if phase=='after-commit':
        original=store._request
        def request(body,raw):
            result=original(body,raw)
            if body['command']=='finish':os._exit(73)
            return result
        store._request=request
    operation(store,'finish',dict(attempt=claim['attempt'],generation=claim['generation'],kind='draft',text='immutable child output'),request_id='finish')
    os._exit(74)


class ProcessCrashTests(unittest.TestCase):
    def scenario(self,phase):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        profile=Path(temporary.name)/'profile'
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--child',str(profile),phase],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,73,result.stderr)
        store=DraftStore(profile);self.addCleanup(store.close)
        return profile,store

    def interrupted(self,phase,orphans):
        _,store=self.scenario(phase);view=store.call('snapshot')
        self.assertTrue(view['paused']);self.assertIsNone(view['active_attempt'])
        self.assertEqual(view['jobs'][0]['state'],'INTERRUPTED')
        self.assertFalse(view['jobs'][0]['completed']);self.assertEqual(len(view['orphans']),orphans)
        operation(store,'resume')
        self.assertEqual(operation(store,'claim')['error'],'NO_ELIGIBLE_JOB')
        with closing(sqlite3.connect(store.profile/'drafts.sqlite3')) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM receipts WHERE request_id='finish'").fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM artifacts').fetchone()[0],0)

    def test_exit_after_claim_requires_explicit_retry(self):self.interrupted('after-claim',0)
    def test_exit_after_pending_file_preserves_orphan(self):self.interrupted('pending-file',1)
    def test_exit_after_rename_does_not_adopt_artifact(self):self.interrupted('after-rename',1)
    def test_exit_before_commit_rolls_back_finalization(self):self.interrupted('before-commit',1)
    def test_exit_after_commit_replays_exact_committed_result(self):
        profile,store=self.scenario('after-commit')
        with closing(sqlite3.connect(profile/'drafts.sqlite3')) as db:
            body,response=db.execute("SELECT body,response FROM receipts WHERE request_id='finish'").fetchone()
        body=json.loads(body);response=json.loads(response);before=store.call('snapshot')
        self.assertTrue(before['paused']);self.assertTrue(before['jobs'][0]['completed'])
        actual=store.call(body['command'],body['payload'],client=body['client'],request_id=body['request_id'],revision=body['expected_revision'])
        self.assertEqual(actual,response);self.assertEqual(store.call('snapshot'),before)
        self.assertEqual(len(list((profile/'artifacts').iterdir())),1)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':child(sys.argv[2],sys.argv[3])
    else:unittest.main(verbosity=2)
