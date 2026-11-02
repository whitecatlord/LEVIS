"""Native Windows negative controls; all profiles disposable. No live model."""
import ast
import contextlib
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid

import runtime_ipc_windows as win
import runtime_profile as profiles
import runtime_protocol as protocol
from runtime_client import Client
from runtime_store import Store

ROOT = Path(__file__).resolve().parent
# Tests may choose a workspace parent; never default to a production profile.
TEST_PARENT = Path(os.environ.get('LEVIS_TEST_PARENT', tempfile.gettempdir()))


def request(command='status', revision=None, request_id=None):
    return {'protocol_version': 1, 'client_id': 'test', 'request_id': request_id or uuid.uuid4().hex,
            'expected_revision': revision, 'command': command, 'payload': {}}


class Runtime:
    def __init__(self, path, initialize=True):
        self.path = Path(path)
        command = [sys.executable, str(ROOT/'runtime_coordinator.py'), '--profile', str(path)]
        if initialize:
            command.append('--init')
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        old = (self.path/'discovery.json').read_bytes() if not initialize and (self.path/'discovery.json').exists() else None
        for _ in range(200):
            if self.process.poll() is not None:
                raise RuntimeError(self.process.communicate())
            if (self.path/'discovery.json').exists():
                raw = (self.path/'discovery.json').read_bytes()
                if raw != old:
                    self.client = Client(path, 'test')
                    self.client.request('status')
                    return
            time.sleep(.025)
        self.kill()
        raise TimeoutError('Coordinator startup')

    def kill(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)
        self.process.communicate()

    def stop(self):
        if self.process.poll() is None:
            status = self.client.request('status', control=True)
            result = self.client.request('stop', status['revision'])
            assert result['state'] == 'STOPPED', result
            self.process.wait(timeout=10)
        stdout, stderr = self.process.communicate()
        if self.process.returncode != 0:
            raise AssertionError((stdout, stderr, self.process.returncode))


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='LEVIS-M11-test-', dir=TEST_PARENT)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def runtime(self):
        run = Runtime(self.base/'profile')
        self.addCleanup(run.kill)
        return run

    def test_LIFE02_idle_LIFE04_attach_detach_and_revision(self):
        run = self.runtime();client = run.client
        initial = client.request('snapshot')
        self.assertEqual(initial['state'], 'PAUSED')
        self.assertFalse(initial['executor_enabled']);self.assertFalse(initial['model_enabled'])
        for command in ('attach', 'detach', 'status'):
            view = client.request(command)
            self.assertEqual(view['revision'], initial['revision'])
            self.assertEqual(view['state'], 'PAUSED')
        ready = client.request('resume', initial['revision'])
        self.assertEqual(ready['state'], 'READY')
        bad = client.request('pause', initial['revision'])
        self.assertEqual(bad['error'], 'REVISION_CONFLICT')
        paused = client.request('pause', ready['revision'])
        self.assertEqual(paused['state'], 'PAUSED')
        events = client.request('events', payload={'after': 0, 'limit': 100})['events']
        self.assertEqual([e['state'] for e in events], ['STARTING', 'RECOVERING', 'PAUSED', 'READY', 'PAUSED'])
        self.assertEqual([e['cursor'] for e in events], sorted(set(e['cursor'] for e in events)))
        run.stop()
        db = sqlite3.connect(run.path/'runtime.sqlite3')
        try:self.assertEqual(db.execute('SELECT state,clean FROM runtime').fetchone(), ('STOPPED', 1))
        finally:db.close()

    def test_IPC04_lost_reply_retry_and_conflict_after_restart(self):
        run = self.runtime();client = run.client
        revision = client.request('status')['revision']
        req = request('resume', revision, 'lost-reply')
        h,ch = client.connect(True)
        ch.send(req)
        # Close without reading response or sending ACK. A committed outcome
        # must be recovered by retry, never applied a second time.
        for _ in range(50):
            if client.request('status')['state']=='READY':break
            time.sleep(.01)
        else:self.fail('Mutation did not commit before lost reply')
        win.close(h)
        result = client.request('resume', revision, request_id='lost-reply')
        repeat = client.request('resume', revision, request_id='lost-reply')
        self.assertEqual(result, repeat)
        self.assertEqual(result['state'], 'READY')
        conflict = client.request('pause', revision, request_id='lost-reply')
        self.assertEqual(conflict['error'], 'REQUEST_ID_CONFLICT')
        run.kill()
        recovered = Runtime(run.path, False);self.addCleanup(recovered.kill)
        historical = recovered.client.request('resume', revision, request_id='lost-reply')
        self.assertEqual(result, historical)
        self.assertEqual(recovered.client.request('status')['state'], 'PAUSED')
        recovered.stop()

    def test_DB01_two_processes_alias_and_duplicate_endpoint(self):
        run = self.runtime()
        args = [sys.executable, str(ROOT/'runtime_coordinator.py'), '--profile', str(run.path/'..'/'profile')]
        other = subprocess.run(args, capture_output=True, text=True, timeout=10)
        self.assertEqual(other.returncode, 2)
        self.assertIn('32', other.stderr)
        with self.assertRaises(OSError):
            win.new_pipe(win.pipe_name(run.path, run.client.who), run.client.who)
        run.stop()

    def test_IPC01_bad_secret_and_native_wrong_logon_acl(self):
        run = self.runtime()
        client = Client(run.path);client.secret = secrets.token_bytes(32)
        with self.assertRaises((OSError, TimeoutError, PermissionError)):
            client.request('resume', 3)
        self.assertEqual(run.client.request('status')['revision'], 3)
        # Actual Windows DACL check with an unavailable logon SID, no accounts
        # created and no claim of a real second-user/session test.
        who = {**win.process_identity(), 'logon': 'S-1-5-5-999999-999999'}
        name = win.pipe_name(run.path, who)
        h = win.new_pipe(name, who)
        try:
            with self.assertRaises(PermissionError):win.open_pipe(name, .1)
        finally:win.close(h)
        run.stop()

    def test_IPC01_effective_peer_user_and_logon_mismatch(self):
        run = self.runtime()
        for key, wrong in [('user', 'S-1-5-18'), ('logon', 'S-1-5-5-999-999')]:
            h = win.open_pipe(win.pipe_name(run.path, run.client.who))
            try:
                with self.assertRaises(PermissionError):
                    win.peer_identity(h, False, {**run.client.who, key: wrong})
            finally:win.close(h)
        run.stop()

    def test_IPC02_stale_discovery(self):
        run = self.runtime();p = run.path/'discovery.json';original = p.read_bytes()
        value = json.loads(original);value['pid'] += 1000000;p.write_bytes(protocol.encode(value))
        try:
            with self.assertRaises(PermissionError):run.client.request('status')
        finally:p.write_bytes(original)
        run.stop()

    def test_IPC02_squatted_namespace_before_database_start(self):
        path,who,secret = profiles.initialize(self.base/'profile')
        store=Store(path/'runtime.sqlite3',uuid.uuid4().hex,create=True);store.close()
        profiles.mark_ready(path,who)
        before=(path/'runtime.sqlite3').read_bytes()
        h=win.new_pipe(win.pipe_name(path,who),who)
        try:
            other=subprocess.run([sys.executable,str(ROOT/'runtime_coordinator.py'),'--profile',str(path)],capture_output=True,text=True,timeout=10)
            self.assertEqual(other.returncode,2)
            self.assertEqual((path/'runtime.sqlite3').read_bytes(),before)
        finally:win.close(h)

    def test_IPC02_wrong_server_proof_native_pipe(self):
        profile,who,secret = profiles.initialize(self.base/'profile')
        store=Store(profile/'runtime.sqlite3',uuid.uuid4().hex,create=True);store.close()
        profiles.mark_ready(profile,who)
        generation=uuid.uuid4().hex;profiles.publish(profile,who,generation)
        h=win.new_pipe(win.pipe_name(profile,who),who)
        stop=threading.Event();errors=[]
        def fake():
            try:
                win.accept(h,stop);protocol.unpack(h,4096)
                protocol.pack(h,protocol.encode({'version':1,'generation':generation,'server_nonce':secrets.token_hex(32)}))
                protocol.unpack(h,4096)
                protocol.pack(h,protocol.encode({'proof':'0'*64}))
                time.sleep(.1)
            except BaseException as e:errors.append(e)
        t=threading.Thread(target=fake);t.start()
        try:
            with self.assertRaisesRegex(PermissionError,'Server authentication'):Client(profile).request('status')
        finally:
            stop.set();t.join(5);win.close(h)
        self.assertEqual(errors,[])

    def test_IPC03_bad_mac_sequence_json_version_and_lengths(self):
        run=self.runtime();client=run.client
        raws=[b'\xff', b'{"x":1,"x":2}', protocol.encode({**request(), 'protocol_version':2}), b'['*100+b']'*100]
        for raw in raws:
            h,ch=client.connect()
            try:
                seq=struct.pack('!Q',0)
                protocol.pack(h,seq+protocol.proof(ch.key,b'C',seq+raw)+raw)
                with self.assertRaises((OSError,TimeoutError)):ch.receive()
            finally:win.close(h)
        for kind in ('mac','gap','oversize'):
            h,ch=client.connect()
            try:
                frame=ch.frame(request('resume',3))
                if kind=='mac':frame=frame[:8]+bytes(32)+frame[40:]
                if kind=='gap':frame=struct.pack('!Q',1)+frame[8:]
                if kind=='oversize':win.write_all(h,struct.pack('!I',protocol.MAX_FRAME+1),time.monotonic()+1)
                else:protocol.pack(h,frame)
                with self.assertRaises((OSError,TimeoutError)):ch.receive()
            finally:win.close(h)
        self.assertEqual(client.request('status')['revision'],3)
        run.stop()

    def test_IPC03_replay_cross_connection_and_direction(self):
        run=self.runtime();client=run.client
        h,ch=client.connect()
        first=ch.frame(request())
        protocol.pack(h,first);reply=ch.receive();ch.send({'ack':reply['request_id']});win.close(h)
        h,ch=client.connect()
        try:
            protocol.pack(h,first)
            with self.assertRaises((OSError,TimeoutError)):ch.receive()
        finally:win.close(h)
        key=secrets.token_bytes(32)
        sender=protocol.Channel(None,key,b'C',b'S');receiver=protocol.Channel(None,key,b'S',b'C')
        frame=sender.frame({'value':1});self.assertEqual(receiver.verify(frame),{'value':1})
        with self.assertRaises(PermissionError):receiver.verify(frame)
        reflected=protocol.Channel(None,key,b'C',b'S')
        with self.assertRaises(PermissionError):reflected.verify(frame)
        run.stop()

    def test_reserved_control_reachable_during_slow_data_client(self):
        run=self.runtime()
        h=win.open_pipe(win.pipe_name(run.path,run.client.who))
        try:
            start=time.monotonic()
            status=run.client.request('status',control=True)
            result=run.client.request('resume',status['revision'])
            self.assertEqual(result['state'],'READY')
            self.assertLess(time.monotonic()-start,2)
        finally:win.close(h)
        run.stop()

    def test_startup_REC01_unclean_recovery_always_paused(self):
        run=self.runtime();status=run.client.request('status')
        run.client.request('resume',status['revision']);run.kill()
        restarted=Runtime(run.path,False);self.addCleanup(restarted.kill)
        state=restarted.client.request('status')
        self.assertEqual(state['state'],'PAUSED');self.assertEqual(state['startup_reason'],'unclean')
        events=restarted.client.request('events',payload={'after':0,'limit':100})['events']
        self.assertEqual([e['state'] for e in events][-3:],['STARTING','RECOVERING','PAUSED'])
        restarted.stop()

    def test_AUTH01_unsupported_commands_and_fields(self):
        run=self.runtime()
        for command in ('shell','set_state','apply_patch','submit_chat','promote','grant_lease','change_model_lock','finalize'):
            h,ch=run.client.connect()
            try:
                ch.send(request(command))
                with self.assertRaises((OSError,TimeoutError)):ch.receive()
            finally:win.close(h)
        h,ch=run.client.connect()
        try:
            ch.send({**request('resume',3),'approved':True})
            with self.assertRaises((OSError,TimeoutError)):ch.receive()
        finally:win.close(h)
        self.assertEqual(run.client.request('status')['revision'],3)
        run.stop()

    def test_DB03_actor_validates_worker_and_stale_generation_fields(self):
        store=Store(self.base/'actor.db',uuid.uuid4().hex,create=True);self.addCleanup(store.close)
        with self.assertRaises(sqlite3.ProgrammingError):
            store.db.execute("UPDATE runtime SET state='READY'")
        for bad in ({**request(),'runtime_generation':'stale'}, request('finalize')):
            with self.assertRaises(ValueError):store.call(bad)
        self.assertEqual(store.call(request())['state'],'PAUSED')

    def test_DB04_locked_database_no_success_and_error_gate(self):
        store=Store(self.base/'actor.db',uuid.uuid4().hex,create=True);self.addCleanup(store.close)
        locked=sqlite3.connect(self.base/'actor.db',isolation_level=None)
        try:
            locked.execute('BEGIN IMMEDIATE')
            result=store.call(request('resume',3,'blocked'))
            self.assertEqual(result['status'],'ERROR');self.assertTrue(store.failed.is_set())
        finally:locked.execute('ROLLBACK');locked.close()
        db=sqlite3.connect(self.base/'actor.db')
        try:
            self.assertEqual(db.execute('SELECT state FROM runtime').fetchone()[0],'PAUSED')
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0],0)
        finally:db.close()

    def test_DB04_commit_failure_injection_no_success_receipt(self):
        # Native SQLite authorizer denies only COMMIT, after lifecycle/receipt
        # writes. The real rollback must preserve the prior committed state.
        class DenyCommit(Store):
            def _event(self,state):
                super()._event(state)
                if state=='READY':
                    self.db.set_authorizer(lambda code,a,b,c,d: sqlite3.SQLITE_DENY
                        if code==sqlite3.SQLITE_TRANSACTION and a=='COMMIT' else sqlite3.SQLITE_OK)
        path=self.base/'actor.db';store=DenyCommit(path,uuid.uuid4().hex,create=True);self.addCleanup(store.close)
        result=store.call(request('resume',3))
        self.assertEqual(result['status'],'ERROR')
        db=sqlite3.connect(path)
        try:
            self.assertEqual(db.execute('SELECT state FROM runtime').fetchone()[0],'PAUSED')
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0],0)
        finally:db.close()

    def test_DB04_sqlite_full_quota_rolls_back(self):
        class FillStore(Store):
            def _event(self,state):
                super()._event(state)
                if state=='READY':
                    pages=self.db.execute('PRAGMA page_count').fetchone()[0]
                    self.db.execute(f'PRAGMA max_page_count={pages}')
                    try:
                        self.db.execute("INSERT INTO requests VALUES('quota','quota','hash',zeroblob(1048576))")
                    except sqlite3.OperationalError as error:
                        self.quota_error_code=error.sqlite_errorcode
                        raise
        path=self.base/'quota.db';store=FillStore(path,uuid.uuid4().hex,create=True);self.addCleanup(store.close)
        result=store.call(request('resume',3))
        self.assertEqual(result['status'],'ERROR')
        self.assertEqual(store.quota_error_code,sqlite3.SQLITE_FULL)
        db=sqlite3.connect(path)
        try:
            self.assertEqual(db.execute('SELECT state FROM runtime').fetchone()[0],'PAUSED')
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0],0)
        finally:db.close()

    def test_native_pipe_dacl_excludes_instance_creation(self):
        who=win.process_identity();name=win.pipe_name(self.base,who)
        h=win.new_pipe(name,who)
        get_security=win.bind(win.A,'GetSecurityInfo',[win.W.HANDLE,win.W.DWORD,win.W.DWORD,
                               win.P,win.P,win.P,win.P,win.P],win.W.DWORD)
        descriptor=win.P();acl=win.P()
        try:
            self.assertEqual(get_security(h,1,4,None,None,win.C.byref(acl),None,win.C.byref(descriptor)),0)
            count=win.C.c_ushort.from_address(acl.value+4).value;self.assertEqual(count,1)
            ace=win.P();win.check(win.get_ace(acl,0,win.C.byref(ace)))
            self.assertEqual(win.sid_text(ace.value+8),who['logon'])
            mask=win.W.DWORD.from_address(ace.value+4).value
            self.assertEqual(mask,win.CLIENT_RIGHTS);self.assertFalse(mask&4)
        finally:
            if descriptor.value:win.local_free(descriptor)
            win.close(h)

    def test_corrupt_schema_refused(self):
        path,who,secret=profiles.initialize(self.base/'profile')
        profiles.mark_ready(path,who)
        (path/'runtime.sqlite3').write_bytes(b'not a SQLite database'.ljust(4096,b'!'))
        proc=subprocess.run([sys.executable,str(ROOT/'runtime_coordinator.py'),'--profile',str(path)],capture_output=True,text=True,timeout=10)
        self.assertNotEqual(proc.returncode,0)
        self.assertFalse((path/'discovery.json').exists())

    def test_secret_corruption_and_existing_init_refused(self):
        path,who,secret=profiles.initialize(self.base/'profile')
        store=Store(path/'runtime.sqlite3',uuid.uuid4().hex,create=True);store.close()
        profiles.mark_ready(path,who)
        with self.assertRaises(FileExistsError):profiles.initialize(path)
        (path/'secret.dpapi').write_bytes(b'broken')
        with self.assertRaises(OSError):profiles.load(path)
        self.assertEqual((path/'secret.dpapi').read_bytes(),b'broken')

    def test_no_executor_model_legacy_import_or_working_transition(self):
        runtime_files=list(ROOT.glob('runtime_*.py'))
        forbidden={'tkinter','levis_desktop','away_work','library_tools','urllib','requests','socket','subprocess'}
        for path in runtime_files:
            tree=ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):names=[x.name.split('.')[0] for x in node.names]
                elif isinstance(node,ast.ImportFrom):names=[(node.module or '').split('.')[0]]
                else:continue
                self.assertFalse(forbidden.intersection(names),(path,names))
        run=self.runtime()
        self.assertFalse(run.client.request('snapshot')['model_enabled'])
        run.stop()
        self.assertFalse(any((run.path/name).exists() for name in ('jobs.sqlite3','conversations.sqlite3','library.sqlite3')))


if __name__=='__main__':
    unittest.main(verbosity=2)
