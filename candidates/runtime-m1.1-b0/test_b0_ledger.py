from contextlib import closing
"""Store-only controls. Linux stubs the unused Win32 import, never the transport."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest

SOURCE = Path(os.environ.get('LEVIS_TEST_SOURCE', Path(__file__).parent / 'LEVIS_STARTER')).resolve()
sys.path.insert(0, str(SOURCE))
if os.name != 'nt':
    sys.modules['runtime_ipc_windows'] = types.ModuleType('runtime_ipc_windows')
from runtime_store import Store


def request(command, revision=None, identity='request'):
    return dict(protocol_version=1, client_id='test', request_id=identity,
                command=command, expected_revision=revision, payload={})


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("LEVIS_TEST_PARENT"))
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ledger.sqlite3'
        store = Store(self.path, 'first', create=True)
        try:
            self.resume = request('resume', 3, 'resume')
            self.outcome = store.call(self.resume)
            store.call(request('stop', 4, 'stop'))
        finally:
            store.close()

    def corrupt(self, sql, parameters=()):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(sql, parameters)
        before = self.path.read_bytes()
        opened = None
        try:
            with self.assertRaises(RuntimeError) as raised:
                opened = Store(self.path, 'second')
            if not os.environ.get('LEVIS_TEST_SOURCE'):
                self.assertEqual(getattr(raised.exception, 'code', None), 'LEDGER_INTEGRITY')
        finally:
            if opened is not None:
                opened.close()
        self.assertEqual(self.path.read_bytes(), before, 'refusal changed original bytes')

    def test_revision_rollback(self):
        self.corrupt('UPDATE runtime SET revision=0')

    def test_revision_ahead(self):
        self.corrupt('UPDATE runtime SET revision=100')

    def test_empty_receipt(self):
        self.corrupt("UPDATE requests SET response='{}' WHERE id='resume'")

    def test_receipt_shapes(self):
        # Each subcase begins from the same stopped valid fixture.
        original = self.path.read_bytes()
        for value in ([], None, {'status': 'UNKNOWN'}, {**self.outcome, 'version': 99},
                      {**self.outcome, 'request_id': 'wrong'},
                      {**self.outcome, 'revision': True},
                      {**self.outcome, 'state': 'WORKING'},
                      {**self.outcome, 'executor_enabled': True}):
            with self.subTest(value=value):
                self.path.write_bytes(original)
                self.corrupt("UPDATE requests SET response=? WHERE id='resume'", (json.dumps(value),))

    def test_missing_control(self):
        self.corrupt("DELETE FROM controls WHERE id='resume'")

    def test_bad_control(self):
        self.corrupt("UPDATE controls SET command='pause' WHERE id='resume'")

    def test_missing_event(self):
        self.corrupt('DELETE FROM events WHERE cursor=2')

    def test_event_state(self):
        self.corrupt("UPDATE events SET state='READY' WHERE cursor=2")

    def test_valid_historical_replay(self):
        store = Store(self.path, 'second')
        try:
            before = store.call(request('snapshot'))
            self.assertEqual(before['revision'], 9)
            self.assertEqual(store.call(self.resume), self.outcome)
            after = store.call(request('snapshot'))
            self.assertEqual(before, after)
            refused = store.call(request('resume', 0, 'stale'))
            self.assertEqual(refused['status'], 'REFUSED')
            store.call(request('pause', 9, 'noop'))
        finally:
            store.close()
        store = Store(self.path, 'third')
        store.close()

    def test_new_and_unclean_restart(self):
        store = Store(self.path, 'second')
        store.close()
        store = Store(self.path, 'third')
        try:
            self.assertEqual(store.call(request('status'))['state'], 'PAUSED')
        finally:
            store.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
