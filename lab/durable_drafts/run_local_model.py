"""Explicit one-job local-model lab runner; new profile and source text required."""
import argparse
import json
from pathlib import Path
import sys
import time
from draft_store import DraftStore, digest
from draft_lane import DraftLane
from ollama_adapter import OllamaDraftAdapter


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',required=True,type=Path,help='New isolated lab profile; existing profiles refuse')
    parser.add_argument('--model-lock',required=True,type=Path)
    parser.add_argument('--input',required=True,type=Path,help='Exact UTF-8 text to send to loopback Ollama')
    parser.add_argument('--goal',required=True)
    args=parser.parse_args()
    pin=json.loads(args.model_lock.read_text(encoding='utf-8'))
    source=args.input.read_bytes().decode('utf-8')
    adapter=OllamaDraftAdapter(pin['model'],pin['digest'])
    adapter.verify_model()  # Refuse unavailable/mismatched models before creating a profile.
    store=DraftStore(args.profile,create=True); lane=DraftLane(store,adapter)
    try:
        payload=dict(goal=args.goal,inputs=[dict(name=args.input.name,text=source,sha256=digest(source.encode()))],
                     authorization=dict(operator='explicit-local-cli',scope='DRAFT_ONLY'))
        submitted=store.call('submit',payload,revision=store.call('snapshot')['revision'])
        if submitted['status']!='OK': raise RuntimeError(str(submitted))
        job_id=submitted['result']['job']; lane.start(); lane.control('resume')
        deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            snapshot=store.call('snapshot')
            job=next(j for j in snapshot['jobs'] if j['id']==job_id)
            if job['state'] not in ('QUEUED','RUNNING'): break
            if lane.last_error: raise RuntimeError(lane.last_error)
            time.sleep(.1)
        else: raise TimeoutError('LOCAL_JOB_OUTCOME_UNCERTAIN')
        report=dict(job=job,model_run=adapter.last_run,executor_enabled=False,production_integration=False)
        if job['artifacts']:
            report['artifact']=store.call('artifact',dict(attempt=job['artifacts'][-1]['attempt']))
        # Local report only: do not publish source/output automatically.
        (args.profile/'local_model_run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if job['completed'] else 2
    finally:
        stopped=lane.stop(timeout=125)
        if lane.thread.is_alive():
            raise RuntimeError('Adapter still alive; retain store ownership: '+str(stopped))
        store.close()


if __name__=='__main__': sys.exit(main())
