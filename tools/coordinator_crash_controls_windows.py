"""Follow-up review: verified archived source and real process-exit boundaries.

Same builder/reviewer agent. This is not independent acceptance. Candidate
bytes are untouched; child exit hooks exist only in this external harness.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile

WORKSPACE=Path(os.environ['LEVIS_REVIEW_OUTPUT']).resolve()
WORKSPACE.mkdir(parents=True,exist_ok=True)
(WORKSPACE/'work').mkdir(exist_ok=True)
SOURCE=Path(__file__).resolve().parents[1]/'candidates/runtime-m1.1-b0/LEVIS_STARTER'
EXPECTED={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.iterdir() if p.is_file()}


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def wait_exit(p,code):
    out,err=p.communicate(timeout=15)
    assert p.returncode==code,(p.returncode,out,err)
    return out,err


def metadata(path):return json.loads((path/'profile.json').read_bytes())


def frozen_files(path):
    return {p.name:digest(p) for p in path.iterdir() if p.is_file()}


CHILD=r'''
import os,sys
sys.path.insert(0,sys.argv[1])
import runtime_coordinator as c
import runtime_profile as p
import runtime_protocol as protocol
mode,path=sys.argv[2:4]
if mode=='before-ready':
    p.mark_ready=lambda *a:os._exit(71)
elif mode=='before-discovery':
    p.publish=lambda *a:os._exit(72)
elif mode=='after-commit':
    original=protocol.Channel.send
    def send(self,value):
        if isinstance(value,dict) and value.get('state')=='READY' and value.get('status')=='OK':
            os._exit(73)
        return original(self,value)
    protocol.Channel.send=send
sys.argv=['runtime_coordinator.py','--profile',path,'--init']
sys.exit(c.main())
'''


with tempfile.TemporaryDirectory(prefix='M11-B0-REVIEW-',dir=WORKSPACE/'work') as d:
    base=Path(d)
    root=SOURCE
    sys.path.insert(0,str(root))
    from runtime_client import Client,UnconfirmedRequest
    import runtime_ipc_windows as win
    print('SOURCE',SOURCE,'identity=per-file hashes recorded before native crash controls')

    def crash(mode,path):
        return subprocess.Popen([sys.executable,'-c',CHILD,str(root),mode,str(path)],
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

    path=base/'before-ready'
    child=crash('before-ready',path)
    wait_exit(child,71)
    assert metadata(path)['phase']=='INITIALIZING'
    assert (path/'runtime.sqlite3').stat().st_size>0
    lock=win.ProfileLock(path);lock.close()  # OS released the killed process's ownership.
    before=frozen_files(path)
    failed=subprocess.run([sys.executable,str(root/'runtime_coordinator.py'),'--profile',str(path)],
                          capture_output=True,text=True,timeout=15)
    assert failed.returncode==2,(failed.stdout,failed.stderr)
    assert frozen_files(path)==before
    print('CRASH_BEFORE_READY: actual exit 71; INITIALIZING preserved; ordinary reopen refused; all remaining files byte-equal; lock released by OS')

    def restart(path):
        p=subprocess.Popen([sys.executable,str(root/'runtime_coordinator.py'),'--profile',str(path)],
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        for _ in range(200):
            if p.poll() is not None:raise RuntimeError(p.communicate())
            try:
                c=Client(path,'review-crash');status=c.request('status')
                if status['state']=='PAUSED':return p,c,status
            except (OSError,ValueError,RuntimeError):pass
            time.sleep(.025)
        p.kill();p.communicate();raise TimeoutError('Restart did not recover PAUSED')

    path=base/'before-discovery'
    child=crash('before-discovery',path);wait_exit(child,72)
    assert metadata(path)['phase']=='READY'
    assert not (path/'discovery.json').exists()
    secret=digest(path/'secret.dpapi');profile_meta=digest(path/'profile.json')
    p,c,status=restart(path)
    try:
        assert status['startup_reason']=='unclean'
        assert digest(path/'secret.dpapi')==secret and digest(path/'profile.json')==profile_meta
        c.request('stop',status['revision']);wait_exit(p,0)
    finally:
        if p.poll() is None:p.kill();p.communicate()
    print('CRASH_AFTER_READY_BEFORE_DISCOVERY: actual exit 72; native restart PAUSED/unclean; secret and metadata unchanged; clean stop')

    path=base/'after-commit'
    p=crash('after-commit',path)
    try:
        for _ in range(200):
            if (path/'discovery.json').exists():break
            if p.poll() is not None:raise RuntimeError(p.communicate())
            time.sleep(.025)
        c=Client(path,'review-crash');status=c.request('status')
        try:c.request('resume',status['revision'],request_id='crash-receipt')
        except UnconfirmedRequest:pass
        else:raise AssertionError('Should not receive committed reply before exit hook')
        wait_exit(p,73)
    finally:
        if p.poll() is None:p.kill();p.communicate()
    p,c,new_status=restart(path)
    try:
        outcome=c.request('resume',status['revision'],request_id='crash-receipt')
        assert outcome['state']=='READY' and outcome['status']=='OK'
        assert outcome['runtime_generation']!=new_status['runtime_generation']
        current=c.request('status');assert current['state']=='PAUSED'
        assert c.request('resume',status['revision'],request_id='crash-receipt')==outcome
        c.request('stop',current['revision']);wait_exit(p,0)
    finally:
        if p.poll() is None:p.kill();p.communicate()
    print('CRASH_AFTER_COMMIT_BEFORE_REPLY: actual exit 73; original receipt survives; repeated retry returns same outcome; current runtime stays PAUSED; clean stop')

assert {p.name:digest(p) for p in SOURCE.iterdir() if p.is_file()}==EXPECTED
print('FOLLOWUP_REVIEW_CHECKS_PASS: 3 real process-exit scenarios; candidate source unchanged; no independent acceptance claimed')
