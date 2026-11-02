"""Background lane uses controlled fake adapters, never a live model."""
from pathlib import Path
import tempfile
import threading
import time
import unittest
from draft_store import DraftStore
from draft_lane import DraftLane
AUTH=dict(operator='test-operator',scope='DRAFT_ONLY')

class LaneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=DraftStore(Path(self.temp.name)/'profile',create=True);self.addCleanup(self.store.close)
        self.lanes=[];self.gates=[];self.addCleanup(self.cleanup)
    def cleanup(self):
        for gate in self.gates:gate.set()
        for lane in self.lanes:
            lane.stop(timeout=5)
            self.assertFalse(lane.thread.is_alive())
    def op(self,command,payload=None):return self.store.call(command,payload,revision=self.store.call('snapshot')['revision'])
    def submit(self):return self.op('submit',dict(goal='Draft only',inputs=[],authorization=AUTH))['result']['job']
    def lane(self,adapter):
        lane=DraftLane(self.store,adapter,interval=.01);self.lanes.append(lane);lane.start();return lane
    def blocked(self):
        gate=threading.Event();self.gates.append(gate)
        def adapter(claim,cancel):
            if not gate.wait(5):raise TimeoutError('test gate')
            return dict(kind='draft',text='fake adapter output')
        return gate,adapter
    def wait(self,predicate):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if predicate():return
            time.sleep(.01)
        self.fail('bounded condition wait expired')
    def test_start_while_paused_never_calls_adapter(self):
        self.submit();calls=[];lane=self.lane(lambda *args:calls.append(args))
        # Synchronize on the actor after the lane has been started.
        self.assertTrue(self.store.call('snapshot')['paused']);self.assertEqual(calls,[])
        self.assertEqual(lane.stop()['state'],'STOPPED');self.assertEqual(calls,[])
    def test_actor_responds_while_fake_adapter_runs(self):
        self.submit();gate,adapter=self.blocked();lane=self.lane(adapter);self.op('resume')
        self.assertTrue(lane.running.wait(5));start=time.monotonic()
        self.assertIsNotNone(self.store.call('snapshot')['active_attempt'])
        self.assertLess(time.monotonic()-start,1)
        gate.set();self.wait(lambda:self.store.call('snapshot')['jobs'][0]['completed'])
    def test_pause_drains_without_starting_next_authorized_job(self):
        self.submit();self.submit();gate,adapter=self.blocked();lane=self.lane(adapter);self.op('resume')
        self.assertTrue(lane.running.wait(5));self.assertEqual(lane.control('pause')['result']['dispatch'],'DRAINING')
        gate.set();self.wait(lambda:self.store.call('snapshot')['jobs'][0]['completed'])
        lane.stop();self.assertEqual(self.store.call('snapshot')['jobs'][1]['state'],'QUEUED')
    def test_cancel_signal_is_advisory_and_late_output_is_not_completed(self):
        job=self.submit();gate,adapter=self.blocked();lane=self.lane(adapter);self.op('resume')
        self.assertTrue(lane.running.wait(5));result=lane.control('cancel',dict(job=job))
        self.assertEqual(result['result']['state'],'CANCEL_PENDING');self.assertTrue(lane.cancel.is_set())
        self.assertIsNotNone(self.store.call('snapshot')['active_attempt']);gate.set()
        self.wait(lambda:self.store.call('snapshot')['jobs'][0]['state']=='CANCELLED')
        self.assertFalse(self.store.call('snapshot')['jobs'][0]['completed'])
    def test_unresponsive_adapter_reports_stop_timeout_without_releasing_store(self):
        self.submit();gate,adapter=self.blocked();lane=self.lane(adapter);self.op('resume')
        self.assertTrue(lane.running.wait(5));result=lane.stop(timeout=.01)
        self.assertEqual(result['state'],'STOP_TIMEOUT');self.assertEqual(result['outcome'],'UNCERTAIN')
        self.assertIsNotNone(self.store.call('snapshot')['active_attempt'])
        with self.assertRaises(OSError):DraftStore(self.store.profile)
        gate.set();self.wait(lambda:not lane.thread.is_alive())
        self.assertEqual(self.store.call('snapshot')['jobs'][0]['state'],'DRAFT_READY')
    def test_invalid_adapter_output_becomes_failure_without_execution(self):
        self.submit();lane=self.lane(lambda *args:dict(kind='execute',text='touch forbidden'))
        self.op('resume');self.wait(lambda:self.store.call('snapshot')['jobs'][0]['state']=='FAILED')
        self.assertFalse(self.store.call('snapshot')['executor_enabled']);self.assertIsNone(lane.last_error)
    def test_adapter_exception_preserves_typed_failure(self):
        def fail(*args):raise RuntimeError('private adapter details')
        self.submit();lane=self.lane(fail);self.op('resume')
        self.wait(lambda:self.store.call('snapshot')['jobs'][0]['state']=='FAILED')
        artifact=self.store.call('snapshot')['jobs'][0]['artifacts'][0]
        text=self.store.call('artifact',dict(attempt=artifact['attempt']))['text']
        self.assertEqual(text,'ADAPTER_FAILED:RuntimeError')
    def test_adapter_cannot_replace_completion_identity(self):
        def mutate(claim,cancel):
            claim['generation']='forged';claim['attempt']='forged'
            return dict(kind='draft',text='still draft only')
        self.submit();lane=self.lane(mutate);self.op('resume')
        self.wait(lambda:self.store.call('snapshot')['jobs'][0]['completed'])
        self.assertIsNone(lane.last_error)
    def test_lost_completion_reply_is_recovered_without_adapter_rerun(self):
        calls=[]
        def adapter(*args):
            calls.append('once');return dict(kind='draft',text='committed before lost reply')
        original=self.store.call;lost=[]
        def call(command,*args,**kwargs):
            result=original(command,*args,**kwargs)
            if command=='finish' and not lost:
                lost.append(True);raise TimeoutError('injected lost reply after commit')
            return result
        self.store.call=call
        self.submit();lane=self.lane(adapter);self.op('resume')
        self.wait(lambda:lane.last_error is not None)
        self.wait(lambda:not lane.thread.is_alive())
        before=self.store.call('snapshot');self.assertTrue(before['paused']);self.assertTrue(before['jobs'][0]['completed'])
        self.assertIsNotNone(lane.pending_receipt)
        self.assertEqual(lane.recover_pending()['status'],'OK')
        self.assertEqual(self.store.call('snapshot'),before);self.assertEqual(calls,['once'])
        self.assertIsNone(lane.pending_receipt);self.assertIsNone(lane.last_error)
    def test_invalid_nul_output_becomes_failed_attempt(self):
        self.submit();lane=self.lane(lambda *args:dict(kind='draft',text='invalid\x00text'))
        self.op('resume');self.wait(lambda:self.store.call('snapshot')['jobs'][0]['state']=='FAILED')
        self.assertIsNone(lane.last_error)
    def test_two_lane_instances_still_have_one_active_attempt(self):
        self.submit();self.submit();gate,adapter=self.blocked();one=self.lane(adapter);two=self.lane(adapter)
        self.op('resume');self.wait(lambda:one.running.is_set() or two.running.is_set())
        self.assertNotEqual(one.running.is_set(),two.running.is_set())
        self.op('pause');gate.set();self.wait(lambda:self.store.call('snapshot')['active_attempt'] is None)
        self.assertEqual(self.store.call('snapshot')['jobs'][1]['state'],'QUEUED')

if __name__=='__main__':unittest.main(verbosity=2)
