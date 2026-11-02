"""LAB fake-adapter lane. Trusted injected Python only; no model/tool loader.

The database actor remains responsive while an adapter is running. No adapter
is installed by this module and construction never resumes the queue.
"""
import threading
import uuid
from draft_store import decode, encode


class DraftLane:
    def __init__(self, store, adapter, *, interval=.1):
        self.store = store
        self.adapter = adapter
        self.interval = interval
        self.stopping = threading.Event()
        self.cancel = threading.Event()
        self.running = threading.Event()
        self.last_error = None
        self.pending_receipt = None
        self._job = None
        self.thread = threading.Thread(target=self._loop, name='LAB-fake-adapter-lane')

    def start(self):
        self.thread.start()

    def control(self, command, payload=None):
        # A conflict is returned to the harness, never treated as approval.
        revision = self.store.call('snapshot')['revision']
        result = self.store.call(command,payload,revision=revision,client='lane-control')
        if command == 'cancel' and result['status']=='OK' and payload['job']==self._job:
            self.cancel.set()  # Advisory: never claim the adapter actually stopped.
        return result

    def stop(self, timeout=1):
        result = self.control('pause')
        if result['status'] != 'OK':
            return dict(state='STOP_REFUSED',outcome=result)
        self.stopping.set()
        self.cancel.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=timeout)
        if self.thread.is_alive():
            return dict(state='STOP_TIMEOUT',active_job=self._job,outcome='UNCERTAIN')
        return dict(state='STOPPED' if self.last_error is None else 'ERROR',error=self.last_error)

    def recover_pending(self):
        """Query the identical completion receipt; never rerun the adapter."""
        if self.thread.is_alive():
            raise RuntimeError('LANE_STILL_RUNNING')
        if self.pending_receipt is None:
            return None
        reply = self.store.call(**self.pending_receipt)
        if reply['status']=='OK':
            self.pending_receipt = None
            self.last_error = None
        return reply

    def _eligible(self):
        after = 0
        while True:
            state = self.store.call('snapshot',dict(after=after,limit=25))
            if state['paused'] or state['active_attempt'] is not None:
                return None
            if any(job['state']=='QUEUED' for job in state['jobs']):
                return state['revision']
            if not state['has_more']:
                return None
            after = state['next_cursor']

    def _finish(self, claim, output):
        payload = dict(attempt=claim['attempt'],generation=claim['generation'],**output)
        # Revision conflicts may be retried without rerunning the adapter.
        for _ in range(5):
            revision = self.store.call('snapshot')['revision']
            identity = uuid.uuid4().hex
            self.pending_receipt = dict(command='finish',payload=payload,revision=revision,
                                        client='fake-adapter-lane',request_id=identity)
            reply = self.store.call(**self.pending_receipt)
            if reply['status']=='OK':
                self.pending_receipt = None
                return
            if reply.get('error') != 'REVISION_CONFLICT':
                raise RuntimeError('FINALIZATION_REFUSED:'+reply.get('error','UNKNOWN'))
        raise RuntimeError('FINALIZATION_REVISION_CONTENTION')

    def _loop(self):
        try:
            while not self.stopping.is_set():
                revision = self._eligible()
                if revision is None:
                    self.stopping.wait(self.interval)
                    continue
                reply = self.store.call('claim',revision=revision,client='fake-adapter-lane')
                if reply['status'] != 'OK':
                    self.stopping.wait(self.interval)
                    continue
                claim = reply['result']
                # Capture provenance separately from the mutable adapter argument.
                fixed = dict(attempt=claim['attempt'],generation=claim['generation'])
                self._job = claim['job']
                self.cancel.clear()
                self.running.set()
                try:
                    output = self.adapter(decode(encode(claim)),self.cancel)
                    if (type(output) is not dict or set(output)!={'kind','text'} or
                            output['kind'] not in ('draft','question','failure') or
                            type(output['text']) is not str or not output['text'].strip() or '\x00' in output['text'] or
                            len(output['text'])>(3000 if output['kind']=='question' else 30000)):
                        raise ValueError('INVALID_ADAPTER_OUTPUT')
                    # UTF-8 validation happens before submitting a terminal result.
                    output = decode(encode(output))
                except Exception as error:
                    output = dict(kind='failure',text='ADAPTER_FAILED:'+type(error).__name__)
                self._finish(fixed,output)
                self._job = None
                self.running.clear()
        except BaseException as error:
            self.last_error = type(error).__name__+':'+str(error)
            try:
                self.control('pause')
            except Exception:
                pass  # A failed/closed actor cannot acknowledge pause.
            self.stopping.set()
            self.running.clear()
