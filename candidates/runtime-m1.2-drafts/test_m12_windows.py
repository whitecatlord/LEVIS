"""Native coordinator/client process controls. All profiles disposable."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
import runtime_ipc_windows as win
import runtime_protocol as protocol
from runtime_client import Client

ROOT=Path(__file__).resolve().parent


class Running:
    def __init__(self,path,*,initialize=True,delay=0.1,adapter='fake',drain=600,child=None):
        self.path=Path(path)
        old=(self.path/'discovery.json').read_bytes() if (self.path/'discovery.json').exists() else None
        command=[sys.executable,str(ROOT/'runtime_coordinator.py'),'--profile',str(path),'--adapter',adapter,'--fake-delay',str(delay),'--drain-timeout',str(drain)]
        if initialize:command.append('--init')
        if child:command=[sys.executable,'-c',child,str(ROOT),str(path),str(delay)]
        self.process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            for _ in range(300):
                if self.process.poll() is not None:raise RuntimeError(self.process.communicate())
                if (self.path/'discovery.json').exists() and (self.path/'discovery.json').read_bytes()!=old:
                    self.client=Client(path,'test');self.client.request('status');return
                time.sleep(.02)
            raise TimeoutError('STARTUP')
        except BaseException:self.kill();raise
    def kill(self):
        if self.process.poll() is None:self.process.kill()
        self.process.communicate(timeout=10)
    def stop(self):
        if self.process.poll() is None:
            self.control('stop');out,err=self.process.communicate(timeout=15)
            if self.process.returncode:raise RuntimeError((out,err))
    def control(self,command):
        for _ in range(20):
            status=self.client.request('status',control=True)
            reply=self.client.request(command,status['revision'])
            if reply.get('error')!='REVISION_CONFLICT':return reply
        raise RuntimeError('CONTENTION')
    def jobs(self):return self.client.request('jobs')['draft']
    def submit(self,goal='Draft only',identity=None,client=None):
        client=client or self.client
        revision=client.request('jobs')['draft']['revision']
        payload=dict(goal=goal,inputs=[dict(name='fixture',text='Synthetic source',sha256=hashlib.sha256(b'Synthetic source').hexdigest())],authorization=dict(operator='caller-label',scope='DRAFT_ONLY'))
        reply=client.request('job-submit',revision,payload,identity)
        if reply['draft']['status']!='OK':raise RuntimeError(reply)
        return reply['draft']['result']['job']
    def wait_job(self,identity,state,timeout=10):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            job=next(j for j in self.jobs()['jobs'] if j['id']==identity)
            if job['state']==state:return job
            if self.process.poll() is not None:raise RuntimeError(self.process.communicate())
            time.sleep(.02)
        raise TimeoutError((state,self.jobs()))


class NativeM12Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ.get('LEVIS_TEST_PARENT',str(ROOT)))
        self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
    def run_runtime(self,**kwargs):
        runtime=Running(self.base/'profile',**kwargs);self.addCleanup(runtime.kill);return runtime

    def test_client_process_closure_does_not_stop_authorized_job(self):
        run=self.run_runtime(delay=.8)
        child="""import sys,hashlib,json
sys.path.insert(0,sys.argv[1]);from runtime_client import Client
c=Client(sys.argv[2],'detaching-client');v=c.request('jobs')['draft']['revision']
p=dict(goal='Survive client exit',inputs=[],authorization=dict(operator='child',scope='DRAFT_ONLY'))
j=c.request('job-submit',v,p)['draft']['result']['job'];s=c.request('status');c.request('resume',s['revision']);c.request('detach');print(j)
"""
        result=subprocess.run([sys.executable,'-c',child,str(ROOT),str(run.path)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);job=result.stdout.strip()
        row=run.wait_job(job,'DRAFT_READY');self.assertTrue(row['completed'])
        self.assertIsNone(run.process.poll());self.assertEqual(len(row['artifacts']),1);run.stop()

    def test_pause_drains_and_prevents_second_job(self):
        run=self.run_runtime(delay=1)
        first=run.submit();second=run.submit('Second job');run.control('resume');run.wait_job(first,'RUNNING')
        self.assertEqual(run.control('pause')['state'],'WORKING')
        run.wait_job(first,'DRAFT_READY');time.sleep(.2)
        self.assertEqual(next(j for j in run.jobs()['jobs'] if j['id']==second)['state'],'QUEUED')
        self.assertEqual(run.client.request('status')['state'],'PAUSED');run.stop()

    def test_stop_drains_then_exits_with_draft(self):
        run=self.run_runtime(delay=1)
        job=run.submit();run.control('resume');run.wait_job(job,'RUNNING')
        self.assertEqual(run.control('stop')['state'],'STOPPING')
        out,err=run.process.communicate(timeout=10);self.assertEqual(run.process.returncode,0,(out,err))
        reopened=Running(run.path,initialize=False);self.addCleanup(reopened.kill)
        self.assertTrue(reopened.jobs()['paused']);self.assertTrue(reopened.wait_job(job,'DRAFT_READY')['completed']);reopened.stop()

    def test_active_cancel_retains_output_as_cancelled_not_completed(self):
        run=self.run_runtime(delay=2);job=run.submit();run.control('resume');run.wait_job(job,'RUNNING')
        reply=run.client.request('job-cancel',run.jobs()['revision'],dict(job=job))
        self.assertEqual(reply['draft']['result']['state'],'CANCEL_PENDING')
        row=run.wait_job(job,'CANCELLED');self.assertFalse(row['completed']);self.assertEqual(row['artifacts'][0]['kind'],'cancelled-output');run.stop()

    def test_killed_coordinator_recovers_interrupted_without_rerun(self):
        run=self.run_runtime(delay=10);job=run.submit();run.control('resume');old=run.wait_job(job,'RUNNING');run.kill()
        restarted=Running(run.path,initialize=False);self.addCleanup(restarted.kill)
        row=restarted.wait_job(job,'INTERRUPTED');self.assertFalse(row['completed']);self.assertTrue(restarted.jobs()['paused'])
        restarted.control('resume');time.sleep(.3);self.assertEqual(restarted.wait_job(job,'INTERRUPTED')['artifacts'],[])
        result=restarted.client.request('job-retry',restarted.jobs()['revision'],dict(job=job,authorization=dict(operator='test',scope='DRAFT_ONLY')))
        self.assertEqual(result['draft']['status'],'OK');self.assertTrue(restarted.wait_job(job,'DRAFT_READY')['completed']);restarted.stop()

    def test_second_coordinator_denied_while_attempt_active(self):
        run=self.run_runtime(delay=1);job=run.submit();run.control('resume');run.wait_job(job,'RUNNING')
        second=subprocess.run([sys.executable,str(ROOT/'runtime_coordinator.py'),'--profile',str(run.path)],capture_output=True,text=True,timeout=10)
        self.assertEqual(second.returncode,2);self.assertIn('32',second.stderr);run.wait_job(job,'DRAFT_READY');run.stop()

    def test_internal_commands_and_jobs_on_control_endpoint_refused(self):
        run=self.run_runtime()
        with self.assertRaises((OSError,ValueError,TimeoutError)):run.client.request('jobs',control=True)
        for command in ('claim','finish','job-finish','execute'):
            with self.assertRaises(ValueError):run.client.request(command,0)
        self.assertEqual(run.client.request('status',control=True)['state'],'PAUSED');run.stop()

    def test_completed_receipt_survives_restart_and_artifact_hash_matches(self):
        run=self.run_runtime();job=run.submit(identity='once');run.control('resume');row=run.wait_job(job,'DRAFT_READY')
        artifact=run.client.request('job-artifact',payload=dict(attempt=row['artifacts'][0]['attempt']))['draft']
        self.assertEqual(hashlib.sha256(artifact['text'].encode()).hexdigest(),artifact['sha256'])
        run.stop();reopened=Running(run.path,initialize=False);self.addCleanup(reopened.kill)
        self.assertEqual(reopened.client.request('job-artifact',payload=dict(attempt=artifact['attempt']))['draft'],artifact)
        self.assertEqual(reopened.jobs()['job_count'],1);reopened.stop()

    def test_corrupt_job_receipt_is_refused_before_recovery(self):
        run=self.run_runtime();run.submit();run.stop()
        with closing(sqlite3.connect(run.path/'runtime.sqlite3')) as db,db:db.execute("UPDATE draft_receipts SET response='{}'")
        before=(run.path/'runtime.sqlite3').read_bytes()
        result=subprocess.run([sys.executable,str(ROOT/'runtime_coordinator.py'),'--profile',str(run.path)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,2);self.assertEqual((run.path/'runtime.sqlite3').read_bytes(),before)

    def test_lost_submit_reply_replays_one_job(self):
        run=self.run_runtime();revision=run.jobs()['revision']
        request=dict(protocol_version=1,client_id='test',request_id='lost-submit',expected_revision=revision,command='job-submit',payload=dict(goal='Lost reply',inputs=[],authorization=dict(operator='label',scope='DRAFT_ONLY')))
        handle,channel=run.client.connect(False);channel.send(request);win.close(handle)
        deadline=time.monotonic()+5
        while run.jobs()['job_count']<1 and time.monotonic()<deadline:time.sleep(.03)
        response=run.client.request('job-submit',revision,request['payload'],'lost-submit')
        self.assertEqual(response['draft']['status'],'OK');self.assertEqual(run.jobs()['job_count'],1);run.stop()

    def test_stop_timeout_keeps_writer_lock_until_lane_exits(self):
        # Ignore advisory cancellation deliberately. This trusted test adapter
        # models a blocking external call without killing a shared model service.
        child="""import sys,time
sys.path.insert(0,sys.argv[1]);import runtime_profile as p;from runtime_coordinator import Coordinator
profile,who,secret=p.initialize(sys.argv[2])
def adapter(claim,cancel):time.sleep(4);return dict(kind='draft',text='Late bounded draft')
Coordinator(profile,who,secret,initialize=True,adapter=adapter,drain_timeout=1).serve()
"""
        run=self.run_runtime(child=child);job=run.submit();run.control('resume');run.wait_job(job,'RUNNING');run.control('stop')
        time.sleep(1.4);self.assertIsNone(run.process.poll())
        with self.assertRaises(OSError) as raised:win.ProfileLock(run.path)
        self.assertEqual(raised.exception.winerror,32)
        out,err=run.process.communicate(timeout=8);self.assertEqual(run.process.returncode,0,(out,err));self.assertIn('STOP_TIMEOUT',err)


if __name__=='__main__':unittest.main(verbosity=2)
