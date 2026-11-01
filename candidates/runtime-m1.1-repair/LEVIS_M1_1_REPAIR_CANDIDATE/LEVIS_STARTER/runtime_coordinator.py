"""Explicit non-elevated M1.1 process; never imports legacy GUI/model/job code."""
import argparse
import json
import sys
import threading
import uuid
import runtime_ipc_windows as win
import runtime_profile as profile_api
import runtime_protocol as protocol
from runtime_store import Store


class Coordinator:
    def __init__(self, profile, who, secret, *, initialize=False):
        self.profile, self.who, self.secret = profile, who, secret
        self.initialize = initialize
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
                               create=self.initialize, autostart=False)
            self.store.start()
            if self.initialize:
                profile_api.mark_ready(self.profile, self.who)
            profile_api.publish(self.profile, self.who, self.generation)
            for h, control in zip(self.pipes, (False, True)):
                t = threading.Thread(target=self._listen, args=(h, control), name='LEVIS-control' if control else 'LEVIS-data')
                self.workers.append(t);t.start()
            print(json.dumps({'status': 'LISTENING', 'generation': self.generation}), flush=True)
            while not self.stopping.wait(.1):
                if self.store.failed.is_set():
                    # Critical storage failure: close admission and terminate.
                    # Next startup must recover explicitly, always paused.
                    raise RuntimeError('Storage failure; dispatch closed')
            if self.failure.is_set():
                raise RuntimeError('IPC listener failure')
        finally:
            self.stopping.set()
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
    parser = argparse.ArgumentParser(description='M1.1 isolated coordinator; no executor/model')
    parser.add_argument('--profile', required=True)
    parser.add_argument('--init', action='store_true', help='Create a NEW nonexistent isolated profile')
    args = parser.parse_args()
    try:
        profile, who, secret = (profile_api.initialize if args.init else profile_api.load)(args.profile)
        Coordinator(profile, who, secret, initialize=args.init).serve()
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        print(f'STOP: {type(error).__name__}: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
