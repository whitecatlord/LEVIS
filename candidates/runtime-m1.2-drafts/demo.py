"""One synthetic job through native authenticated IPC; new output folder only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from runtime_client import Client,UnconfirmedRequest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--adapter',choices=['fake','ollama'],default='fake')
    args=parser.parse_args();args.output.mkdir(parents=False,exist_ok=False)
    profile=args.output/'profile';root=Path(__file__).resolve().parent
    process=subprocess.Popen([sys.executable,str(root/'runtime_coordinator.py'),'--profile',str(profile),'--init','--adapter',args.adapter],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    source='Synthetic fixture: Aster proposes, Birch reviews, Cedar archives. Drafts must never be executed.'
    goal='Write three short sentences preserving these roles and the no-execution boundary.'
    client=None
    try:
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if process.poll() is not None:raise RuntimeError(process.communicate())
            if (profile/'discovery.json').exists():
                client=Client(profile,'synthetic-demo');client.request('status');break
            time.sleep(.05)
        else:raise TimeoutError('Coordinator startup')
        payload=dict(goal=goal,inputs=[dict(name='synthetic-fixture.txt',text=source,sha256=hashlib.sha256(source.encode()).hexdigest())],authorization=dict(operator='synthetic-demo',scope='DRAFT_ONLY'))
        revision=client.request('jobs')['draft']['revision']
        submitted=client.request('job-submit',revision,payload,'synthetic-submit')
        if submitted['draft']['status']!='OK':raise RuntimeError(submitted)
        job=submitted['draft']['result']['job']
        status=client.request('status');client.request('resume',status['revision']);client.request('detach')
        deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            snapshot=Client(profile,'reattached-demo').request('jobs')['draft']
            row=next(item for item in snapshot['jobs'] if item['id']==job)
            if row['state'] not in ('QUEUED','RUNNING'):break
            if process.poll() is not None:raise RuntimeError(process.communicate())
            time.sleep(.1)
        else:raise TimeoutError('Draft outcome uncertain')
        if row['state']!='DRAFT_READY' or not row['completed']:raise RuntimeError(row)
        artifact=client.request('job-artifact',payload=dict(attempt=row['artifacts'][-1]['attempt']))['draft']
        if hashlib.sha256(artifact['text'].encode()).hexdigest()!=artifact['sha256']:raise RuntimeError('Artifact hash mismatch')
        result=dict(synthetic_input=source,goal=goal,job=job,completed=True,artifact=artifact,job_count=snapshot['job_count'],same_database=True,adapter=args.adapter,executor_enabled=False,production_profile_used=False,authority_effect='NONE')
        (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        if process.poll() is None and client is not None:
            try:
                status=client.request('status',control=True)
                client.request('stop',status['revision'])
                process.communicate(timeout=15)
            except (OSError,ValueError,RuntimeError,TimeoutError,subprocess.TimeoutExpired):
                process.kill();process.communicate(timeout=10)
        elif process.poll() is None:
            process.kill();process.communicate(timeout=10)
        if process.returncode not in (0,None):
            print('Synthetic coordinator ended with code '+str(process.returncode),file=sys.stderr)


if __name__=='__main__':main()
