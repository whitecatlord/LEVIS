"""Authenticated attach/detach client; no writable database connections."""
import uuid
import runtime_ipc_windows as win
import runtime_profile as profile_api
import runtime_protocol as protocol


class UnconfirmedRequest(RuntimeError):
    def __init__(self, request):
        self.request = request
        super().__init__(f"Outcome unknown for request {request['request_id']}; retry the identical command, "
                         f"client_id={request['client_id']}, request_id={request['request_id']}, "
                         f"expected_revision={request['expected_revision']}")


class Client:
    def __init__(self, path, client_id='operator-cli'):
        self.profile, self.who, self.secret = profile_api.load(path)
        self.client_id = client_id

    def connect(self, control=False):
        discovery = profile_api.discovery(self.profile, self.who)
        h = win.open_pipe(win.pipe_name(self.profile, self.who, control))
        try:
            return h, protocol.client_handshake(h, self.secret, discovery, self.who)
        except BaseException:
            win.close(h)
            raise

    def request(self, command, revision=None, payload=None, request_id=None, control=None):
        request = {'protocol_version': 1, 'client_id': self.client_id,
                   'request_id': request_id or uuid.uuid4().hex, 'expected_revision': revision,
                   'command': command, 'payload': payload if payload is not None else {}}
        protocol.validate_request(request)
        h, channel = self.connect(command in protocol.CONTROLS if control is None else control)
        try:
            channel.send(request)
            reply = channel.receive()
            if reply.get('request_id') not in (None, request['request_id']):
                raise ValueError('Reply request identity mismatch')
            try:
                channel.send({'ack': request['request_id']})
            except (OSError, TimeoutError):
                pass  # Already received the authenticated committed outcome.
            return reply
        except (OSError, TimeoutError, ValueError) as error:
            if command in protocol.CONTROLS:
                raise UnconfirmedRequest(request) from error
            raise
        finally:
            win.close(h)
