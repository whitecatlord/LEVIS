"""Run isolated assembly groups; no migration, installation, model or deployment."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


def run(command,cwd,env,log):
    result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=300)
    content=result.stdout+result.stderr
    log.write_text(content,encoding='utf-8')
    count=re.search(r'Ran (\d+) tests?',content)
    return dict(exit_code=result.returncode,tests=int(count[1]) if count else None,log=log.name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    env.pop('LEVIS_TEST_SOURCE',None)
    groups=[]
    b0=run([sys.executable,str(root/'candidates/runtime-m1.1-b0/qualify.py'),'--output',str(output/'b0')],root,env,output/'b0-driver.log')
    if (output/'b0/summary.json').exists():
        summary=json.loads((output/'b0/summary.json').read_text())
        b0['tests']=sum(item['tests'] or 0 for item in summary['results'])
    groups.append(dict(group='runtime-b0',**b0))
    for name,folder,arguments in (
        ('modular-b5','candidates/modular-m0-b5',['-m','unittest','test_modular_b5','-v']),
        ('durable-draft-lab','lab/durable_drafts',['-m','unittest','discover','-p','test_*.py','-v']),
        ('evidence-memory-lab','lab/evidence_memory',['-m','unittest','discover','-p','test_*.py','-v']),
        ('communication-transport','lab/communication',['-I','codec.py'])):
        groups.append(dict(group=name,**run([sys.executable,*arguments],root/folder,env,output/(name+'.log'))))
    if os.name == 'nt':
        native_env=dict(env,LEVIS_REVIEW_OUTPUT=str(output/'final-review'),LEVIS_TEST_PARENT=str(output/'b0/profiles'))
        groups.append(dict(group='historical-final-review',**run(
            [sys.executable,str(root/'tools/final_review_controls_windows.py')],root,native_env,output/'historical-final-review.log')))
        native_env['LEVIS_REVIEW_OUTPUT']=str(output/'coordinator-crashes')
        crash=run([sys.executable,str(root/'tools/coordinator_crash_controls_windows.py')],root,native_env,output/'coordinator-crashes.log')
        crash['process_crash_scenarios']=3 if crash['exit_code']==0 else 0
        groups.append(dict(group='coordinator-crashes',**crash))
    summary=dict(platform=platform.platform(),python=platform.python_version(),groups=groups,
                 tests_run=sum(item['tests'] or 0 for item in groups),
                 process_crash_scenarios=sum(item.get('process_crash_scenarios',0) for item in groups),
                 passed=all(item['exit_code']==0 for item in groups),
                 native_windows_executed=os.name=='nt',lab_isolated=True,acceptance='NOT_GRANTED',authority_effect='NONE')
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return int(not summary['passed'])


if __name__=='__main__':sys.exit(main())
