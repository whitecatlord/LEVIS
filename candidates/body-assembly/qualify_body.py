"""Reproduce native assembly and inherited component controls in a new output root."""
import argparse,hashlib,json,os,re,subprocess,sys,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def code_hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob('*.py')) if '__pycache__' not in p.parts and '.venv' not in p.parts}
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',LEVIS_BODY_TEST_ROOT=str(args.output.resolve()/'body-profiles'),LEVIS_GUI_TEST_ROOT=str(args.output.resolve()/'gui-profiles'));before=code_hashes();groups=[]
    for name,command in [('assembly',[sys.executable,'-m','unittest','-v','test_body','test_workbench']),('components',[sys.executable,'component_controls.py'])]:
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8');log=result.stdout;(args.output/(name+'.log')).write_text(log,encoding='utf-8');matches=re.findall(r'Ran (\d+) tests? in',log)
        groups.append(dict(group=name,tests=int(matches[-1]) if matches else 0,exit_code=result.returncode,passed=result.returncode==0 and bool(matches)))
    summary=dict(platform=platform.platform(),python=platform.python_version(),groups=groups,tests_run=sum(g['tests'] for g in groups),passed=all(g['passed'] for g in groups),source_unchanged=before==code_hashes(),source_sha256=before,independent_review='NOT_RUN',new_assembly_acceptance='NOT_RECORDED',operator_workbench_acceptance='RECORDED_SEPARATELY',base_promoted=False)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in summary.items() if k!='source_sha256'},indent=2));return 0 if summary['passed'] and summary['source_unchanged'] else 1
if __name__=='__main__':sys.exit(main())
