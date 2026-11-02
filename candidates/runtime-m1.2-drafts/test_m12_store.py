"""Single actor/connection integration; stopped disposable ledgers only."""
from contextlib import closing
import ast
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch
import runtime_protocol as protocol
import runtime_store as storage
from runtime_store import Store
import draft_repository as repository


class IntegratedStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('LEVIS_TEST_PARENT'))
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'runtime.sqlite3'
        self.store=Store(self.path,'first',create=True,operator='authenticated-test-identity')
        self.addCleanup(lambda:self.store.close())

    def request(self,command,revision=None,payload=None,identity=None):
        return self.store.call(dict(protocol_version=1,client_id='test',request_id=identity or uuid.uuid4().hex,command=command,expected_revision=revision,payload=payload or {}))

    def jobs(self):return self.request('jobs')['draft']
    def op(self,command,payload=None,identity=None,revision=None):
        return self.request(command,self.jobs()['revision'] if revision is None else revision,payload,identity)['draft']
    def control(self,command,identity=None):
        return self.request(command,self.request('status')['revision'],identity=identity)
    def submit(self,goal='Draft a review'):
        payload=dict(goal=goal,inputs=[dict(name='source',text='exact\r\n| source',sha256=hashlib.sha256(b'exact\r\n| source').hexdigest())],authorization=dict(operator='caller-label',scope='DRAFT_ONLY'))
        return self.op('job-submit',payload)['result']['job']
    def claim(self):return self.store.call_internal_draft('claim',revision=self.jobs()['revision'])
    def finish(self,claim,kind='draft',text='Draft only',identity=None):
        return self.store.call_internal_draft('finish',dict(attempt=claim['attempt'],generation=claim['generation'],kind=kind,text=text),revision=self.jobs()['revision'],request_id=identity)

    def test_single_database_and_actor_no_lab_writer(self):
        self.submit()
        self.assertEqual(list(self.path.parent.glob('*.sqlite3')),[self.path])
        self.assertFalse((self.path.parent/'writer.lock').exists())
        tree=ast.parse(Path(repository.__file__).read_text())
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('connect','Thread','WriterLock') for n in ast.walk(tree)))
        threads=set();original=repository.DraftRepository._mutate
        def record(repo,body):threads.add(threading.current_thread().ident);return original(repo,body)
        with patch.object(repository.DraftRepository,'_mutate',record):self.submit()
        self.assertEqual(threads,{self.store.thread.ident})

    def test_paused_submission_and_explicit_resume(self):
        self.submit();self.assertEqual(self.claim()['error'],'PAUSED')
        self.assertTrue(self.jobs()['paused'])
        self.control('resume');claim=self.claim()['result']
        self.assertEqual(self.request('status')['state'],'WORKING')
        self.assertEqual(claim['inputs'][0]['text'],'exact\r\n| source')
        self.finish(claim);self.assertEqual(self.request('status')['state'],'READY')

    def test_pause_drains_active_attempt_and_closes_admission(self):
        self.submit();self.submit('second');self.control('resume');claim=self.claim()['result']
        reply=self.control('pause');self.assertEqual(reply['state'],'WORKING')
        self.assertTrue(self.jobs()['paused']);self.finish(claim)
        self.assertEqual(self.request('status')['state'],'PAUSED')
        self.assertEqual(self.claim()['error'],'PAUSED')

    def test_stop_intent_and_finalization_are_separate(self):
        self.submit();self.control('resume');claim=self.claim()['result']
        original_revision=self.request('status')['revision']
        reply=self.request('stop',original_revision,identity='stop-intent');self.assertEqual(reply['state'],'STOPPING')
        self.assertFalse(reply['clean_shutdown']);self.assertTrue(self.jobs()['paused'])
        self.finish(claim);self.assertEqual(self.request('status')['state'],'STOPPED')
        # The historical stop intent remains STOPPING, never reexecutes a stop.
        self.assertEqual(self.request('stop',original_revision,identity='stop-intent'),reply)
        self.assertEqual(self.request('stop',reply['revision'],identity='stop-intent')['error'],'REQUEST_ID_CONFLICT')

    def test_cancel_late_output_is_not_completed(self):
        job=self.submit();self.control('resume');claim=self.claim()['result']
        self.assertEqual(self.op('job-cancel',dict(job=job))['result']['state'],'CANCEL_PENDING')
        self.finish(claim);row=self.jobs()['jobs'][0]
        self.assertFalse(row['completed']);self.assertEqual(row['state'],'CANCELLED')
        self.assertEqual(row['artifacts'][0]['kind'],'cancelled-output')

    def test_questions_answers_and_provenance_survive_restart(self):
        job=self.submit();self.control('resume');claim=self.claim()['result'];self.finish(claim,'question','Which constraint?')
        self.control('stop');self.store.close();self.store=Store(self.path,'second',operator='authenticated-test-identity')
        self.op('job-answer',dict(job=job,text='Preserve the exact source.',authorization=dict(operator='untrusted-label',scope='DRAFT_ONLY')))
        self.control('resume');next_claim=self.claim()['result']
        self.assertEqual(next_claim['answers'][0]['question'],'Which constraint?')
        self.assertEqual(next_claim['answers'][0]['operator'],'authenticated-test-identity')
        self.finish(next_claim)

    def test_unclean_restart_interrupts_and_requires_retry(self):
        job=self.submit();self.control('resume');old=self.claim()['result'];self.store.close()
        self.store=Store(self.path,'second',operator='authenticated-test-identity')
        self.assertTrue(self.jobs()['paused']);self.assertEqual(self.jobs()['jobs'][0]['state'],'INTERRUPTED')
        self.control('resume');self.assertEqual(self.claim()['error'],'NO_ELIGIBLE_JOB')
        self.op('job-retry',dict(job=job,authorization=dict(operator='label',scope='DRAFT_ONLY')))
        fresh=self.claim()['result'];self.assertNotEqual(fresh['attempt'],old['attempt'])
        self.assertEqual(self.finish(old)['error'],'STALE_ATTEMPT');self.finish(fresh)

    def test_exact_receipt_replay_and_conflicting_body(self):
        payload=dict(goal='One job',inputs=[],authorization=dict(operator='label',scope='DRAFT_ONLY'))
        revision=self.jobs()['revision'];first=self.op('job-submit',payload,'one',revision)
        self.assertEqual(self.op('job-submit',payload,'one',revision),first)
        changed={**payload,'authorization':dict(operator='changed-label',scope='DRAFT_ONLY')}
        self.assertEqual(self.op('job-submit',changed,'one',revision)['error'],'REQUEST_ID_CONFLICT')
        self.assertEqual(self.jobs()['job_count'],1)

    def test_replayed_finish_does_not_repeat_lifecycle(self):
        self.submit();self.control('resume');claim=self.claim()['result'];revision=self.jobs()['revision']
        payload=dict(attempt=claim['attempt'],generation=claim['generation'],kind='draft',text='result')
        first=self.store.call_internal_draft('finish',payload,revision=revision,request_id='finish')
        before=self.request('status',identity='fixed-status')
        self.assertEqual(self.store.call_internal_draft('finish',payload,revision=revision,request_id='finish'),first)
        self.assertEqual(self.request('status',identity='fixed-status'),before)

    def test_external_claim_finish_and_arbitrary_commands_refused(self):
        for command in ('claim','finish','draft-internal','execute','job-claim','job-finish'):
            with self.subTest(command=command),self.assertRaises(ValueError):self.request(command,0)

    def test_invalid_payloads_do_not_kill_actor(self):
        for command,payload in [('job-submit',{}),('job-artifact',{'attempt':'missing'}),('jobs',{'bad':True}),('job-events',{'after':-1,'limit':1})]:
            result=self.request(command,0,payload)
            self.assertEqual(result['draft']['status'],'REFUSED')
            self.assertFalse(self.store.failed.is_set())
        self.assertEqual(self.request('job-events',payload={'after':0,'limit':100})['draft'][0]['kind'],'RECOVERY')

    def test_authorization_is_bound_to_authenticated_identity(self):
        self.submit();self.store.close()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT operator FROM draft_authorizations').fetchone()[0],'authenticated-test-identity')
            self.assertIn('caller-label',db.execute("SELECT body FROM draft_receipts WHERE client LIKE 'ipc_%'").fetchone()[0])
        self.store=Store(self.path,'second')

    def test_oversized_payload_refused_before_writing(self):
        before=self.jobs()['revision']
        with self.assertRaises(ValueError):self.op('job-submit',dict(text='x'*(129*1024)))
        self.assertEqual(self.jobs()['revision'],before)

    def test_atomic_pause_rollback_leaves_runtime_and_jobs_enabled(self):
        self.control('resume');before=self.request('status',identity='fixed')
        original=self.store._set_draft_dispatch
        def fail(*args):original(*args);raise sqlite3.OperationalError('injected commit path')
        with patch.object(self.store,'_set_draft_dispatch',fail):
            result=self.control('pause');self.assertEqual(result['status'],'ERROR')
        self.store.close()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT state,revision FROM runtime').fetchone(),('READY',before['revision']))
            self.assertEqual(db.execute('SELECT paused FROM draft_meta').fetchone()[0],0)

    def test_claim_lifecycle_failure_rolls_back_attempt(self):
        self.submit();self.control('resume');original=self.store._event
        def fail(state):
            if state=='WORKING':raise sqlite3.OperationalError('injected claim boundary')
            return original(state)
        with patch.object(self.store,'_event',fail):result=self.claim()
        self.assertEqual(result['status'],'ERROR');self.store.close()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM draft_attempts').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT state FROM draft_jobs').fetchone()[0],'QUEUED')

    def test_finished_file_without_commit_is_orphan_not_success(self):
        self.submit();self.control('resume');claim=self.claim()['result'];original=self.store._event
        def fail(state):
            if state=='READY':raise sqlite3.OperationalError('injected finish boundary')
            return original(state)
        with patch.object(self.store,'_event',fail):self.finish(claim)
        self.store.close();self.store=Store(self.path,'second')
        jobs=self.jobs();self.assertEqual(jobs['jobs'][0]['state'],'INTERRUPTED')
        self.assertFalse(jobs['jobs'][0]['completed']);self.assertEqual(len(jobs['orphans']),1)

    def test_detectable_cross_ledger_corruption_refuses_without_recovery(self):
        self.control('resume');self.store.close()
        with closing(sqlite3.connect(self.path)) as db,db:db.execute('UPDATE draft_meta SET paused=1')
        before=self.path.read_bytes()
        with self.assertRaises(RuntimeError):Store(self.path,'second')
        self.assertEqual(self.path.read_bytes(),before)

    def test_revision_namespaces_are_explicit(self):
        runtime_revision=self.request('status')['revision'];self.submit()
        self.assertEqual(self.request('status')['revision'],runtime_revision)
        self.assertNotEqual(self.jobs()['revision'],runtime_revision)

    def test_stop_closes_new_submission_but_retains_refusal_receipt(self):
        self.submit();self.control('resume');claim=self.claim()['result'];self.control('stop')
        payload=dict(goal='Too late',inputs=[],authorization=dict(operator='label',scope='DRAFT_ONLY'))
        revision=self.jobs()['revision'];reply=self.op('job-submit',payload,'late',revision)
        self.assertEqual(reply['error'],'INVALID_LIFECYCLE')
        self.finish(claim)
        self.assertEqual(self.op('job-submit',payload,'late',revision),reply)
        self.assertEqual(self.jobs()['job_count'],1)

    def test_attempt_provider_is_historical_after_restart_with_different_configuration(self):
        self.submit();self.control('resume');claim=self.claim()['result'];self.finish(claim);self.control('stop');self.store.close()
        provider=dict(kind='ollama',model='synthetic-model:fixed',digest='a'*64)
        self.store=Store(self.path,'second',provider=provider)
        self.assertTrue(self.request('status')['model_enabled'])
        artifact=self.request('job-artifact',payload=dict(attempt=claim['attempt']))['draft']
        self.assertEqual(artifact['provider'],dict(kind='none',model='',digest=''))


if __name__=='__main__':unittest.main(verbosity=2)
