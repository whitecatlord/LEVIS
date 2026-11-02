"""Target-Windows candidate qualification. New disposable output only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


def source_hashes(root):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir()) if p.is_file() and p.suffix in ('.py','.json')}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if os.name!='nt':raise RuntimeError('This candidate requires native Windows qualification')
    output=args.output.resolve();output.mkdir(parents=False,exist_ok=False);(output/'profiles').mkdir()
    root=Path(__file__).resolve().parent;before=source_hashes(root)
    env=dict(os.environ,LEVIS_TEST_PARENT=str(output/'profiles'),PYTHONDONTWRITEBYTECODE='1')
    process=subprocess.run([sys.executable,'-m','unittest','discover','-p','test_*.py','-v'],cwd=root,env=env,capture_output=True,text=True,timeout=300)
    log=process.stdout+process.stderr;(output/'tests.log').write_text(log,encoding='utf-8')
    match=re.search(r'Ran (\d+) tests?',log);skip=re.search(r'skipped=(\d+)',log)
    total=int(match[1]) if match else 0;skipped=int(skip[1]) if skip else 0
    after=source_hashes(root)
    summary=dict(platform=platform.platform(),python=platform.python_version(),tests_run=total,tests_skipped=skipped,tests_passed=total-skipped if process.returncode==0 else None,exit_code=process.returncode,passed=process.returncode==0 and total>0 and before==after,source_unchanged=before==after,source_hashes=before,profile_schema=3,one_actor_one_database=True,acceptance='NOT_GRANTED',authority_effect='NONE',skipped_scope='M1.1-only unreachable WORKING assertion replaced by authorized claim/finalization controls')
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='source_hashes'},indent=2))
    return int(not summary['passed'])


if __name__=='__main__':sys.exit(main())
