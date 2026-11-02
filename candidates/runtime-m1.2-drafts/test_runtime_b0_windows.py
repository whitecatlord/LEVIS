from contextlib import closing
"""Native B0 startup/replay controls. Disposable profiles only."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
if os.name == 'nt':
    from test_runtime_windows import Runtime, ROOT, TEST_PARENT


@unittest.skipUnless(os.name == 'nt', 'requires native Windows')
class NativeB0Tests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix='LEVIS-B0-', dir=TEST_PARENT)
        self.addCleanup(temp.cleanup)
        run = Runtime(Path(temp.name) / 'profile'); self.addCleanup(run.kill)
        state = run.client.request('status')
        self.revision = state['revision']
        self.receipt = run.client.request('resume', self.revision, request_id='b0-replay')
        run.stop()
        return run

    def refused(self, mutation, parameters=()):
        run = self.fixture()
        with closing(sqlite3.connect(run.path / 'runtime.sqlite3')) as db, db: db.execute(mutation, parameters)
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in run.path.iterdir() if p.is_file()}
        result = subprocess.run([sys.executable, str(ROOT/'runtime_coordinator.py'), '--profile', str(run.path)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2, result.stderr)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in run.path.iterdir() if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((run.path/'discovery.tmp').exists())

    def test_revision_rollback_refused_before_ready(self): self.refused('UPDATE runtime SET revision=0')
    def test_damaged_receipt_refused_before_ready(self): self.refused("UPDATE requests SET response='{}' WHERE id='b0-replay'")
    def test_unknown_receipt_shape_refused(self): self.refused("UPDATE requests SET response=? WHERE id='b0-replay'", ('{"status":"UNKNOWN"}',))

    def test_native_replay_after_restart_remains_historical(self):
        run = self.fixture()
        restarted = Runtime(run.path, initialize=False); self.addCleanup(restarted.kill)
        before = restarted.client.request('status', request_id='stable-observation')
        replay = restarted.client.request('resume', self.revision, request_id='b0-replay')
        self.assertEqual(replay, self.receipt)
        self.assertEqual(restarted.client.request('status', request_id='stable-observation'), before)
        restarted.stop()


if __name__ == '__main__': unittest.main(verbosity=2)
