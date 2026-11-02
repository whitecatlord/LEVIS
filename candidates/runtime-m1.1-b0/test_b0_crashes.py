from contextlib import closing
"""Real child exits around SQLite commit; no Windows IPC/power-loss claim."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
sys.path.insert(0, str(Path(__file__).parent / 'LEVIS_STARTER'))
if os.name != 'nt': sys.modules['runtime_ipc_windows'] = types.ModuleType('runtime_ipc_windows')
from runtime_store import Store


def request(command, revision=None):
    return dict(protocol_version=1, client_id='crash', request_id='resume-outcome',
                command=command, expected_revision=revision, payload={})


def child(path, phase):
    if phase == 'startup':
        original = Store._event
        def event(store, state):
            original(store, state)
            if state == 'RECOVERING': os._exit(73)
        Store._event = event
    store = Store(path, 'child', create=True)
    if phase == 'before-control-commit':
        original = store._request
        def call(req):
            def trace(sql):
                if sql == 'COMMIT': os._exit(73)
            store.db.set_trace_callback(trace)
            return original(req)
        store._request = call
    if phase == 'after-control-commit':
        original = store._request
        def call(req):
            original(req)
            os._exit(73)
        store._request = call
    store.call(request('resume', 3))
    os._exit(74)


class CrashTests(unittest.TestCase):
    def scenario(self, phase):
        temp = tempfile.TemporaryDirectory(dir=os.environ.get("LEVIS_TEST_PARENT")); self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'ledger.sqlite3'
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--child', str(path), phase],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 73, result.stderr)
        return path

    def test_exit_during_startup_rolls_back_lifecycle(self):
        path = self.scenario('startup')
        with closing(sqlite3.connect(path)) as db, db:
            self.assertEqual(db.execute('SELECT state,revision FROM runtime').fetchone(), ('STOPPED', 0))
            self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0], 0)
        # Only Store reopening; native INITIALIZING profile handling is unchanged.
        store = Store(path, 'parent')
        try: self.assertEqual(store.call(request('status'))['state'], 'PAUSED')
        finally: store.close()

    def test_exit_before_control_commit_leaves_no_receipt(self):
        path = self.scenario('before-control-commit')
        with closing(sqlite3.connect(path)) as db, db:
            self.assertEqual(db.execute('SELECT state,revision FROM runtime').fetchone(), ('PAUSED', 3))
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 0)
        store = Store(path, 'parent')
        try:
            reply = store.call(request('resume', 3))
            self.assertEqual((reply['status'], reply['error']), ('REFUSED', 'REVISION_CONFLICT'))
            self.assertEqual(store.call(request('status'))['state'], 'PAUSED')
        finally: store.close()

    def test_exit_after_commit_replays_without_reexecution(self):
        path = self.scenario('after-control-commit')
        with closing(sqlite3.connect(path)) as db, db:
            receipt = json.loads(db.execute('SELECT response FROM requests').fetchone()[0])
            self.assertEqual(receipt['state'], 'READY')
        store = Store(path, 'parent')
        try:
            before = store.call(request('status'))
            self.assertEqual(before['state'], 'PAUSED')
            self.assertEqual(store.call(request('resume', 3)), receipt)
            self.assertEqual(store.call(request('status')), before)
        finally: store.close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--child': child(sys.argv[2], sys.argv[3])
    else: unittest.main(verbosity=2)
