"""Real actor/storage controls; no model, GUI, IPC or execution qualification."""
import hashlib
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from draft_store import DraftStore, IntegrityError, Refused, digest
AUTH=dict(operator='test-operator',scope='DRAFT_ONLY')
def sample(value='original input'):return dict(name='source.py',text=value,sha256=digest(value.encode()))

class DraftTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'profile';self.store=DraftStore(self.path,create=True)
        self.addCleanup(lambda:self.store.close())
    def op(self,command,payload=None,**kwargs):
        revision=kwargs.pop('revision',self.store.call('snapshot')['revision'])
        return self.store.call(command,payload,revision=revision,**kwargs)
    def submit(self,**kwargs):
        result=self.op('submit',dict(goal='Review selected source',inputs=[sample()],authorization=AUTH),**kwargs)
        self.assertEqual(result['status'],'OK',result);return result['result']['job']
    def claim(self):
        self.op('resume');reply=self.op('claim');self.assertEqual(reply['status'],'OK',reply);return reply['result']
    def finish(self,claim,kind='draft',text='proposed change',**kwargs):
        return self.op('finish',dict(attempt=claim['attempt'],generation=claim['generation'],kind=kind,text=text),**kwargs)
    def reopen(self):
        self.store.close();self.store=DraftStore(self.path)
    def test_submission_stays_paused(self):
        self.submit();state=self.store.call('snapshot');self.assertTrue(state['paused'])
        self.assertIsNone(state['active_attempt']);self.assertEqual(self.op('claim')['error'],'PAUSED')
        self.assertFalse(state['model_enabled']);self.assertFalse(state['executor_enabled'])
    def test_input_snapshot_cannot_be_changed_by_caller(self):
        item=sample();self.op('submit',dict(goal='Read',inputs=[item],authorization=dict(AUTH)))
        item['text']='edited';self.assertEqual(self.claim()['inputs'],[sample()])
    def test_input_hash_scope_and_budget_refusals(self):
        for payload in (dict(goal='Read',inputs=[dict(sample(),sha256='0'*64)],authorization=AUTH),
                        dict(goal='Read',inputs=[],authorization=dict(AUTH,scope='EXECUTE')),
                        dict(goal='Read',inputs=[sample('a'*10001)],authorization=AUTH)):
            with self.subTest(payload=str(payload)[:80]):self.assertEqual(self.op('submit',payload)['status'],'REFUSED')
        self.assertEqual(self.store.call('snapshot')['jobs'],[])
    def test_unknown_fields_leave_no_partial_change(self):
        before=self.store.call('snapshot')['revision']
        result=self.op('submit',dict(goal='Read',inputs=[],authorization=AUTH,execute=True))
        self.assertEqual(result['status'],'REFUSED');self.assertEqual(self.store.call('snapshot')['revision'],before)
    def test_single_lane_and_fifo(self):
        first=self.submit();second=self.submit();claim=self.claim();self.assertEqual(claim['job'],first)
        self.assertEqual(self.op('claim')['error'],'LANE_BUSY');self.finish(claim)
        self.assertEqual(self.op('claim')['result']['job'],second)
    def test_draft_commit_and_hash_checked_read(self):
        self.submit();claim=self.claim();self.finish(claim,text='print("draft only")')
        job=self.store.call('snapshot')['jobs'][0];self.assertTrue(job['completed'])
        self.assertEqual(self.store.call('artifact',dict(attempt=claim['attempt']))['text'],'print("draft only")')
        self.assertEqual(len(list((self.path/'artifacts').glob('*.txt'))),1)
    def test_model_output_cannot_request_execution(self):
        self.submit();claim=self.claim();self.assertEqual(self.finish(claim,kind='execute')['error'],'UNSUPPORTED_OUTPUT_KIND')
        self.assertEqual(self.store.call('snapshot')['active_attempt'],claim['attempt'])
        self.assertEqual(list((self.path/'artifacts').iterdir()),[])
    def test_duplicate_submission_and_conflicting_body(self):
        rev=self.store.call('snapshot')['revision'];first=self.submit(request_id='same',revision=rev)
        self.assertEqual(first,self.submit(request_id='same',revision=rev))
        self.assertEqual(len(self.store.call('snapshot')['jobs']),1)
        self.assertEqual(self.store.call('pause',revision=rev,request_id='same')['error'],'REQUEST_ID_CONFLICT')
    def test_completion_receipt_replays_after_restart(self):
        self.submit();claim=self.claim();rev=self.store.call('snapshot')['revision']
        result=self.finish(claim,request_id='finish-receipt',revision=rev);self.reopen();before=self.store.call('snapshot')
        self.assertEqual(self.finish(claim,request_id='finish-receipt',revision=rev),result)
        self.assertEqual(self.store.call('snapshot'),before)
    def test_stale_revision_has_no_event(self):
        self.assertEqual(self.op('resume',revision=0)['error'],'REVISION_CONFLICT')
        self.assertEqual(len(self.store.call('events',dict(after=0,limit=100))),1)
    def test_pause_closes_next_claim_while_draining(self):
        self.submit();self.submit();claim=self.claim()
        self.assertEqual(self.op('pause')['result']['dispatch'],'DRAINING');self.finish(claim)
        self.assertTrue(self.store.call('snapshot')['paused']);self.assertEqual(self.op('claim')['error'],'PAUSED')
        self.assertEqual(self.store.call('snapshot')['jobs'][1]['state'],'QUEUED')
    def test_restart_interrupts_without_automatic_rerun(self):
        self.submit();claim=self.claim();self.reopen();view=self.store.call('snapshot')
        self.assertTrue(view['paused']);self.assertIsNone(view['active_attempt'])
        self.assertEqual(view['jobs'][0]['state'],'INTERRUPTED');self.op('resume')
        self.assertEqual(self.op('claim')['error'],'NO_ELIGIBLE_JOB');self.assertEqual(self.finish(claim)['error'],'STALE_ATTEMPT')
    def test_retry_links_new_attempt_preserving_previous(self):
        job=self.submit();first=self.claim();self.finish(first,kind='failure',text='offline')
        self.op('retry',dict(job=job,authorization=AUTH));second=self.op('claim')['result']
        self.assertNotEqual(first['attempt'],second['attempt'])
        with closing(sqlite3.connect(self.path/'drafts.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT previous_attempt FROM attempts WHERE id=?',(second['attempt'],)).fetchone()[0],first['attempt'])
        self.assertEqual(self.finish(first)['error'],'STALE_ATTEMPT')
    def test_question_restart_retains_exact_question_and_answer(self):
        job=self.submit();first=self.claim();self.finish(first,kind='question',text='Which version?');self.reopen()
        self.assertEqual(self.op('answer',dict(job=job,authorization=AUTH,text='Version two.'))['status'],'OK')
        self.assertTrue(self.store.call('snapshot')['paused']);second=self.claim()
        self.assertEqual(second['answers'],[dict(question_attempt=first['attempt'],question='Which version?',text='Version two.',operator=AUTH['operator'])])
        self.assertEqual(second['inputs'],[sample()])
    def test_continuation_budget_refuses_without_truncation(self):
        job=self.submit();first=self.claim();self.finish(first,kind='question',text='q'*3000)
        self.op('answer',dict(job=job,authorization=AUTH,text='a'*3000));second=self.op('claim')['result']
        self.finish(second,kind='question',text='another?')
        self.assertEqual(self.op('answer',dict(job=job,authorization=AUTH,text='yes'))['error'],'CONTINUATION_LIMIT')
    def test_active_cancellation_is_pending_until_outcome(self):
        first=self.submit();second=self.submit();claim=self.claim()
        self.assertEqual(self.op('cancel',dict(job=second))['result']['state'],'CANCELLED')
        self.assertEqual(self.op('cancel',dict(job=first))['result']['state'],'CANCEL_PENDING')
        self.assertEqual(self.store.call('snapshot')['active_attempt'],claim['attempt'])
        self.assertEqual(self.finish(claim,text='late output')['result']['state'],'CANCELLED')
        job=self.store.call('snapshot')['jobs'][0];self.assertFalse(job['completed'])
        self.assertEqual(job['artifacts'][0]['kind'],'cancelled-output')
    def test_corrupt_or_missing_draft_never_displayed_as_completed(self):
        self.submit();claim=self.claim();self.finish(claim);path=next((self.path/'artifacts').glob('*.txt'))
        path.write_text('tampered');self.reopen();job=self.store.call('snapshot')['jobs'][0]
        self.assertFalse(job['completed']);self.assertEqual(job['display_state'],'CORRUPT_OR_MISSING')
        self.assertIsNone(self.store.call('artifact',dict(attempt=claim['attempt']))['text']);path.unlink()
        self.assertEqual(self.store.call('snapshot')['jobs'][0]['display_state'],'CORRUPT_OR_MISSING')
    def test_missing_question_refuses_answer(self):
        job=self.submit();claim=self.claim();self.finish(claim,kind='question',text='Which version?')
        next((self.path/'artifacts').glob('*.txt')).unlink()
        self.assertEqual(self.op('answer',dict(job=job,authorization=AUTH,text='two'))['error'],'QUESTION_UNAVAILABLE')
    def test_real_second_process_cannot_acquire_writer(self):
        code='from draft_store import DraftStore; import sys; s=DraftStore(sys.argv[1]); s.close()'
        result=subprocess.run([sys.executable,'-c',code,str(self.path)],cwd=Path(__file__).parent,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0);self.assertIn('Error',result.stderr)
        self.assertFalse(self.store.failed.is_set())
    def test_client_thread_can_detach_without_stopping_actor(self):
        jobs=[];thread=threading.Thread(target=lambda:jobs.append(self.submit()));thread.start();thread.join(5)
        self.assertFalse(thread.is_alive());self.assertEqual(len(jobs),1)
        claim=self.claim();self.finish(claim);self.assertTrue(self.store.call('snapshot')['jobs'][0]['completed'])
    def test_invalid_read_does_not_kill_actor(self):
        with self.assertRaises(Refused):self.store.call('events',dict(after=-1,limit=100))
        self.assertTrue(self.store.call('snapshot')['paused'])
    def test_unknown_command_and_oversize_refuse(self):
        with self.assertRaises(Refused):self.store.call('execute',revision=1)
        with self.assertRaises(Refused):self.store.call('submit',dict(text='x'*(256*1024)),revision=1)
        self.assertTrue(self.store.call('snapshot')['paused'])
    def test_orphan_remains_visible_without_adoption(self):
        orphan=self.path/'artifacts'/'uncommitted.txt';orphan.write_text('uncommitted');self.reopen()
        self.assertEqual(self.store.call('snapshot')['jobs'],[])
        self.assertEqual(self.store.call('snapshot')['orphans'],[dict(name=orphan.name,sha256=digest(orphan.read_bytes()))])
        self.assertTrue(orphan.exists())
    def corrupt(self,sql):
        self.store.close()
        with closing(sqlite3.connect(self.path/'drafts.sqlite3')) as db:
            db.execute(sql);db.commit()
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.path.iterdir() if p.is_file()}
        with self.assertRaises((IntegrityError,Refused)):DraftStore(self.path)
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.path.iterdir() if p.is_file()}
        self.assertEqual(before,after)
    def test_revision_rollback_refuses_without_mutation(self):self.submit();self.corrupt('UPDATE meta SET revision=0')
    def test_damaged_receipt_refuses_without_mutation(self):self.submit();self.corrupt("UPDATE receipts SET response='{}'")
    def test_input_tamper_refuses_without_mutation(self):self.submit();self.corrupt("UPDATE jobs SET goal='changed'")
    def test_missing_authorization_refuses_without_mutation(self):self.submit();self.corrupt('DELETE FROM authorizations')
    def test_unknown_schema_refuses_without_mutation(self):self.corrupt('CREATE TABLE unexpected(value TEXT)')
    def test_supported_envelope_with_empty_success_result_is_refused(self):
        self.submit();self.corrupt("UPDATE receipts SET response=json_set(response,'$.result',json('{}'))")
    def test_unknown_refusal_outcome_is_refused(self):
        self.op('resume',revision=0)
        self.corrupt("UPDATE receipts SET response=json_set(response,'$.error','UNKNOWN')")
    def test_duplicate_history_revision_or_event_loss_is_refused(self):
        self.submit();self.corrupt('DELETE FROM events WHERE revision=1')
    def test_missing_database_not_recreated(self):
        self.store.close();path=self.path/'drafts.sqlite3';path.rename(self.path/'preserved.sqlite3')
        with self.assertRaises(sqlite3.OperationalError):DraftStore(self.path)
        self.assertFalse(path.exists())
    def test_job_snapshot_pagination_preserves_global_state(self):
        first=self.submit();second=self.submit()
        page=self.store.call('snapshot',dict(after=0,limit=1))
        self.assertEqual([j['id'] for j in page['jobs']],[first]);self.assertTrue(page['has_more'])
        next_page=self.store.call('snapshot',dict(after=page['next_cursor'],limit=1))
        self.assertEqual([j['id'] for j in next_page['jobs']],[second]);self.assertFalse(next_page['has_more'])
        self.assertEqual(page['job_count'],2);self.assertEqual(page['revision'],next_page['revision'])
    def test_two_concurrent_claims_cannot_open_two_attempts(self):
        self.submit();self.submit();self.op('resume');revision=self.store.call('snapshot')['revision']
        gate=threading.Barrier(3);results=[]
        def claim():
            gate.wait();results.append(self.store.call('claim',revision=revision))
        threads=[threading.Thread(target=claim) for _ in range(2)]
        for thread in threads:thread.start()
        gate.wait()
        for thread in threads:thread.join(5);self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(r['status'] for r in results),['OK','REFUSED'])
        with closing(sqlite3.connect(self.path/'drafts.sqlite3')) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM attempts WHERE state='RUNNING'").fetchone()[0],1)
    def test_concurrent_identical_request_replays_once(self):
        revision=self.store.call('snapshot')['revision'];gate=threading.Barrier(3);results=[]
        payload=dict(goal='Read',inputs=[sample()],authorization=AUTH)
        def submit():
            gate.wait();results.append(self.store.call('submit',payload,revision=revision,request_id='same-concurrent'))
        threads=[threading.Thread(target=submit) for _ in range(2)]
        for thread in threads:thread.start()
        gate.wait()
        for thread in threads:thread.join(5);self.assertFalse(thread.is_alive())
        self.assertEqual(len(results),2);self.assertEqual(results[0],results[1]);self.assertEqual(self.store.call('snapshot')['job_count'],1)
    def test_commit_failure_never_acknowledges_completion(self):
        self.submit();claim=self.claim();original=self.store._mutate
        def inject(body):
            result=original(body)
            if body['command']=='finish':
                def deny(action,arg1,arg2,database,source):
                    return sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_TRANSACTION and arg1=='COMMIT' else sqlite3.SQLITE_OK
                self.store.db.set_authorizer(deny)
            return result
        self.store._mutate=inject
        with self.assertRaises(sqlite3.DatabaseError):self.finish(claim)
        self.assertTrue(self.store.failed.is_set());self.reopen();view=self.store.call('snapshot')
        self.assertEqual(view['jobs'][0]['state'],'INTERRUPTED');self.assertEqual(len(view['orphans']),1)
        self.assertFalse(view['jobs'][0]['completed'])

if __name__=='__main__':unittest.main(verbosity=2)
