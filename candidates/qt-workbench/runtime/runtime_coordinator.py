"""Explicit non-elevated M1.2 draft coordinator; no production profile migration."""
import argparse
import json
import sys
import threading
import uuid
import runtime_ipc_windows as win
import runtime_profile as profile_api
import runtime_protocol as protocol
from runtime_store import Store, LanePort
from draft_lane import DraftLane
import time


class Coordinator:
    def __init__(self, profile, who, secret, *, initialize=False, adapter=None, model_enabled=False, drain_timeout=600):
        self.profile, self.who, self.secret = profile, who, secret
        self.initialize = initialize
        self.adapter, self.model_enabled, self.drain_timeout = adapter, model_enabled, drain_timeout
        self.lane=None
        self.stop_seen=None
        self.stop_timeout_reported=False
        self.generation = uuid.uuid4().hex
        self.stopping = threading.Event()
        self.failure = threading.Event()
        self.pipes = []
        self.workers = []
        self.lock = self.store = None

    def serve(self):
        try:
            self.lock = win.ProfileLock(self.profile)
            # Revalidate phase/identity while owning the profile. Initialization
            # and established-profile reopening are separate, explicit paths.
            profile_api.load(self.profile, allow_initializing=self.initialize)
            # Establish both exclusive endpoints before opening the DB. A
            # squatted pipe cannot cause lifecycle mutations before refusal.
            for control in (False, True):
                self.pipes.append(win.new_pipe(win.pipe_name(self.profile, self.who, control), self.who))
            self.store = Store(self.profile / 'runtime.sqlite3', self.generation,
                               create=self.initialize, autostart=False, model_enabled=self.model_enabled, operator=self.who["user"],
                               provider=dict(kind='ollama',model=self.adapter.model,digest=self.adapter.expected_digest) if self.model_enabled else dict(kind='fake' if self.adapter is not None else 'none',model='',digest=''))
            self.store.start()
            if self.adapter is not None:
                self.lane=DraftLane(LanePort(self.store),self.adapter)
                self.lane.start()
            if self.initialize:
                profile_api.mark_ready(self.profile, self.who)
            profile_api.publish(self.profile, self.who, self.generation)
            for h, control in zip(self.pipes, (False, True)):
                t = threading.Thread(target=self._listen, args=(h, control), name='LEVIS-control' if control else 'LEVIS-data')
                self.workers.append(t);t.start()
            print(json.dumps({'status': 'LISTENING', 'generation': self.generation}), flush=True)
            while not self.stopping.wait(.1):
                observation=self.store.call(dict(protocol_version=1,client_id='coordinator-monitor',request_id=uuid.uuid4().hex,expected_revision=None,command='status',payload={}))
                if observation['status']!='OK':raise RuntimeError('Storage failure; dispatch closed')
                state=observation['state']
                if state=='STOPPED':self.stopping.set()
                if state=='STOPPING':
                    self.stop_seen=self.stop_seen or time.monotonic()
                    if time.monotonic()-self.stop_seen>self.drain_timeout and not self.stop_timeout_reported:
                        print('STOP_TIMEOUT: active attempt uncertain; ownership retained',file=sys.stderr,flush=True)
                        self.stop_timeout_reported=True
                        if self.lane:self.lane.cancel.set()
                if self.lane and self.lane.last_error:raise RuntimeError('Draft lane failure: '+self.lane.last_error)
                if self.store.failed.is_set():
                    # Critical storage failure: close admission and terminate.
                    # Next startup must recover explicitly, always paused.
                    raise RuntimeError('Storage failure; dispatch closed')
            if self.failure.is_set():
                raise RuntimeError('IPC listener failure')
        finally:
            self.stopping.set()
            if self.lane:
                self.lane.stopping.set();self.lane.cancel.set()
                # Keep the actor and OS writer lock until the lane actually exits.
                self.lane.thread.join()
            if self.store:
                self.store.cancel.set()
            for t in self.workers:
                t.join()
            for h in self.pipes:
                win.close(h)
            if self.store:
                self.store.close()
            if self.lock:
                self.lock.close()

    def _listen(self, h, control):
        try:
            while win.accept(h, self.stopping):
                stop_after_reply = False
                try:
                    channel = protocol.server_handshake(h, self.secret, self.generation, self.who)
                    # One request per connection is a fixed quota; no unbounded
                    # subscriber/client can occupy the actor or an endpoint.
                    request = protocol.validate_request(channel.receive())
                    if control and request['command'] not in protocol.CONTROLS | {'status'}:
                        raise ValueError('Reserved control endpoint')
                    response = self.store.call(request)
                    if (self.lane and request['command']=='job-cancel' and response.get('draft',{}).get('status')=='OK' and request['payload'].get('job')==self.lane._job):
                        self.lane.cancel.set()
                    stop_after_reply = (response.get('state') == 'STOPPED' and
                                        response.get('runtime_generation') == self.generation)
                    channel.send(response)
                    # DisconnectNamedPipe discards unread output: client ACK
                    # proves receipt before reusing the retained pipe handle.
                    ack = channel.receive()
                    protocol.fields(ack, 'ack')
                    if ack['ack'] != request['request_id']:
                        raise ValueError('Reply ACK mismatch')
                except (OSError, ValueError, PermissionError, TimeoutError, RecursionError):
                    # Deliberately no sensitive payload/proof logging.
                    pass
                finally:
                    win.disconnect_pipe(h)
                    if stop_after_reply:
                        self.stopping.set()
        except BaseException:
            self.failure.set()
            self.stopping.set()
            # A dead listener is a fatal IPC error, never an open fallback.
            print('IPC listener failed; coordinator stopped', file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description='M1.2 isolated coordinator; durable draft-only jobs, no code executor')
    parser.add_argument('--profile', required=True)
    parser.add_argument('--init', action='store_true', help='Create a NEW nonexistent isolated profile')
    parser.add_argument('--adapter',choices=['none','fake','ollama'],default='none')
    parser.add_argument('--fake-delay',type=float,default=.1)
    parser.add_argument('--model-lock',default=str(__import__('pathlib').Path(__file__).with_name('MODEL_LOCK.json')))
    parser.add_argument('--drain-timeout',type=float,default=600)
    args = parser.parse_args()
    try:
        profile, who, secret = (profile_api.initialize if args.init else profile_api.load)(args.profile)
        if not 0<=args.fake_delay<=30 or not 1<=args.drain_timeout<=600:raise ValueError('Invalid bounded adapter/drain settings')
        adapter=None
        if args.adapter=='fake':
            def adapter(claim,cancel):
                cancel.wait(args.fake_delay)
                return dict(kind='draft',text='FAKE ADAPTER DRAFT: '+claim['goal'])
        elif args.adapter=='ollama':
            from ollama_adapter import OllamaDraftAdapter
            from pathlib import Path
            pin=json.loads(Path(args.model_lock).read_text(encoding='utf-8'))
            adapter=OllamaDraftAdapter(pin['model'],pin['digest']);adapter.verify_model()
        Coordinator(profile, who, secret, initialize=args.init,adapter=adapter,model_enabled=args.adapter=='ollama',drain_timeout=args.drain_timeout).serve()
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        print(f'STOP: {type(error).__name__}: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
