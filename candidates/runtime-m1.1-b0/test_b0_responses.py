"""Client controls use a fake channel, not native IPC."""
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent / 'LEVIS_STARTER'))
if os.name != 'nt': sys.modules['runtime_ipc_windows'] = types.ModuleType('runtime_ipc_windows')
import runtime_protocol as protocol
import runtime_client


def request(command='status'):
    return dict(protocol_version=1, client_id='test', request_id='identity', command=command,
                expected_revision=3 if command in protocol.CONTROLS else None,
                payload={'after': 0, 'limit': 10} if command == 'events' else {})


def response():
    return dict(request_id='identity', status='OK', state='PAUSED', revision=3,
                runtime_generation='historical', event_cursor=3, clean_shutdown=False,
                startup_reason='clean', executor_enabled=False, model_enabled=False)


class ResponseTests(unittest.TestCase):
    def test_valid_observation_and_historical_outcome(self):
        self.assertEqual(protocol.validate_response(response(), request()), response())
        protocol.validate_response(dict(response(), state='READY', revision=4, event_cursor=4), request('resume'))

    def test_malformed_envelopes(self):
        for value in (None, [], {}, {'status': 'OK'}, dict(response(), status='UNKNOWN'),
                      dict(response(), request_id='wrong'), dict(response(), revision=True),
                      dict(response(), event_cursor=-1), dict(response(), state='WORKING'),
                      dict(response(), clean_shutdown=0), dict(response(), version=2),
                      dict(response(), runtime_generation=''), dict(response(), model_enabled=True)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                protocol.validate_response(value, request())

    def test_control_state_is_command_specific(self):
        with self.assertRaises(ValueError): protocol.validate_response(response(), request('resume'))

    def test_typed_storage_failure(self):
        error = dict(request_id='identity', status='ERROR', error='STORAGE_FAILURE', runtime_generation='old')
        protocol.validate_response(error, request('resume'))
        with self.assertRaises(ValueError): protocol.validate_response(dict(error, error='UNKNOWN'), request('resume'))

    def test_refusals_and_attachments(self):
        for reason in ('REVISION_CONFLICT', 'INVALID_LIFECYCLE', 'REQUEST_ID_CONFLICT'):
            protocol.validate_response(dict(response(), status='REFUSED', error=reason), request('resume'))
        for command, label in (('attach', 'attached'), ('detach', 'detached')):
            protocol.validate_response(dict(response(), attachment=label), request(command))
        with self.assertRaises(ValueError):
            protocol.validate_response(dict(response(), attachment='attached'), request('detach'))

    def test_event_page_and_cursor(self):
        page = dict(response(), events=[dict(cursor=3, generation='historical', state='PAUSED', revision=3, at=1.0)], next_cursor=3)
        protocol.validate_response(page, request('events'))
        for modified in (dict(page, next_cursor=2), dict(page, events=page['events'] * 2),
                         dict(page, events=[dict(page['events'][0], at=float('nan'))]),
                         dict(page, events=[dict(page['events'][0], revision=4)])):
            with self.subTest(modified=modified), self.assertRaises(ValueError):
                protocol.validate_response(modified, request('events'))
        future = request('events'); future['payload']['after'] = 100
        protocol.validate_response(dict(response(), events=[], next_cursor=100), future)

    def client(self, outcome):
        client = runtime_client.Client.__new__(runtime_client.Client); client.client_id = 'test'
        class Channel:
            def __init__(self): self.sent = []
            def send(self, value): self.sent.append(value)
            def receive(self): return outcome
        channel = Channel(); client.connect = lambda control: ('handle', channel)
        return client, channel

    def test_client_refuses_missing_envelope_before_ack(self):
        client, channel = self.client({})
        with patch.object(runtime_client.win, 'close', create=True), self.assertRaises(ValueError):
            client.request('status', request_id='identity')
        self.assertEqual(len(channel.sent), 1)

    def test_control_malformed_reply_is_unconfirmed(self):
        client, channel = self.client({})
        with patch.object(runtime_client.win, 'close', create=True), self.assertRaises(runtime_client.UnconfirmedRequest) as raised:
            client.request('resume', 3, request_id='identity')
        self.assertEqual(raised.exception.request, request('resume'))
        self.assertEqual(len(channel.sent), 1)

    def test_client_valid_reply_acknowledged(self):
        client, channel = self.client(response())
        with patch.object(runtime_client.win, 'close', create=True):
            self.assertEqual(client.request('status', request_id='identity'), response())
        self.assertEqual(channel.sent[-1], {'ack': 'identity'})


if __name__ == '__main__': unittest.main(verbosity=2)
