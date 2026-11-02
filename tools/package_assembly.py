"""Package a clean committed assembly and rehearse its binary patch offline."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PUBLIC_BASE='bfdf0e13a532192166a9d159f6f871d43e88fe66'


def git(*arguments):
    return subprocess.check_output(['git',*arguments],cwd=ROOT)


def archive_files(raw):
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        result={}
        for member in archive:
            if member.isdir():continue
            if not member.isfile():raise ValueError('Non-regular archived entry')
            path=Path(member.name)
            if path.is_absolute() or '..' in path.parts:raise ValueError('Invalid archive path')
            result[member.name]=archive.extractfile(member).read()
        return result


def build(output,summary_path):
    output=Path(output).absolute()
    if output.is_relative_to(ROOT) or output.exists():
        raise ValueError('Choose a new output file outside the repository')
    if git('status','--porcelain').strip():raise ValueError('Commit or preserve work before packaging')
    summary=json.loads(Path(summary_path).read_text())
    if summary.get('passed') is not True:raise ValueError('Qualification summary is not passing')
    head=git('rev-parse','HEAD').decode().strip()
    source=archive_files(git('archive','--format=tar',head))
    baseline=archive_files(git('archive','--format=tar',PUBLIC_BASE))
    patch=git('diff','--binary','--full-index',PUBLIC_BASE,head)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='LEVIS-upload-rehearsal-') as temporary:
        temporary=Path(temporary);checkout=temporary/'checkout';checkout.mkdir()
        for name,data in baseline.items():
            path=checkout/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        patch_path=temporary/'upload.patch';patch_path.write_bytes(patch)
        for arguments in (['--check','--whitespace=nowarn'],['--whitespace=nowarn']):
            subprocess.run(['git','apply',*arguments,str(patch_path)],cwd=checkout,check=True,capture_output=True)
        actual={p.relative_to(checkout).as_posix():p.read_bytes() for p in checkout.rglob('*') if p.is_file()}
        if actual!=source:raise ValueError('Upload patch did not reconstruct exact source')
    metadata=dict(source_commit=head,public_base=PUBLIC_BASE,branch=git('branch','--show-current').decode().strip(),
                  tests_passed=summary['tests_run'],native_windows_executed=summary['native_windows_executed'],
                  qualification_summary_sha256=hashlib.sha256(Path(summary_path).read_bytes()).hexdigest(),
                  upload_patch_rehearsal='PASS: every reconstructed file matches committed source',
                  acceptance='NOT_GRANTED',authority_effect='NONE')
    readme=f'''# LEVIS assembly checkpoint — 2026-11-02

Source commit: {head}
Pinned public parent: {PUBLIC_BASE}
Tests: {summary['tests_run']} passing methods on the recorded platform. Windows qualification remains pending. Nothing in this package was published by this packaging command.

## Contents

- source/LEVIS/: full committed source, historical parents, candidate/lab code, reviews and executed evidence.
- LEVIS_UPLOAD.patch: Git binary patch against the exact pinned public parent.
- PACKAGE.json and PACKAGE_SHA256.txt: identities and complete package-member checksums.

## What is built

B0 startup/content and receipt repair; modular room persistence/delegation controls; an isolated durable-draft actor/background fake-adapter lane; and an isolated evidence-memory bridge with exact source citations, typed contradictions/corrections, source-origin grouping and compact packets.

The memory bridge can read a verified saved draft as a private proposal, preserving an explicit gap for original-input/model provenance unavailable through its observation API. It never grants execution or Base authority. Context completeness is unknown without an expected inventory. Five deterministic fixture conditions were run; independent model trials and token efficiency are still untested.

## At the computer

Read source/LEVIS/docs/ASSEMBLY_CONTINUATION_2026-11-02.md and each candidate/lab REVIEW.md. Python 3.12+ with Tkinter is needed for the inherited application tests.

From source/LEVIS:
```
python tools/qualify_assembly.py --output PATH_TO_NEW_TEST_OUTPUT
python lab/durable_drafts/demo.py
python lab/evidence_memory/experiment.py --output PATH_TO_NEW_FIXTURE_OUTPUT
```

On Windows, candidates/runtime-m1.1-b0/QUALIFY_WINDOWS.cmd also provides a convenience entry point for the B0 suite. Keep all output logs. These use disposable profiles; no production profile, actual model, migration or generated-code executor is started. Full native IPC/coordinator qualification, fresh review and exact-artifact acceptance still gate runtime integration.

## Upload to GitHub when ready

Use a clean checkout of https://github.com/whitecatlord/LEVIS. Replace PATH_TO_PACKAGE with this extracted package folder. Choose a new branch name if needed.
```
git fetch origin
git switch -c assembly/2026-11-02-checkpoint {PUBLIC_BASE}
git apply --check "PATH_TO_PACKAGE/LEVIS_UPLOAD.patch"
git apply --index "PATH_TO_PACKAGE/LEVIS_UPLOAD.patch"
git diff --cached --stat
git commit -m "Continue LEVIS isolated candidate assembly"
git push -u origin HEAD
```

This creates a review branch, not a merge or runtime acceptance. The patch has already been applied offline to a fresh export of the exact public parent; every resulting file matched this committed source. If a check fails, preserve the checkout and review conflicts instead of forcing an application.

The source history was restored from the verified saved checkpoint after a workspace reset. Historical commit identities remain in the handoff records; the current local commit reflects reconstructed Git metadata and new work.

## Remaining gates

Native Windows IPC/profile/process qualification; independent review; explicit scoped acceptance; production single-writer integration; chat/GUI/reference migration; actual target-machine/model qualification; and independent reconstruction trials. No complete-body, consciousness, semantic-truth or clinical claim is made.
'''
    files={'START_HERE.md':readme.encode(),'LEVIS_UPLOAD.patch':patch,
           'PACKAGE.json':(json.dumps(metadata,indent=2)+'\n').encode()}
    files.update({'source/LEVIS/'+name:data for name,data in source.items()})
    files['PACKAGE_SHA256.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    temporary_output=output.with_suffix(output.suffix+'.pending')
    if temporary_output.exists():raise ValueError('Existing partial package must be preserved/reconciled')
    with zipfile.ZipFile(temporary_output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):archive.writestr(name,data)
    with zipfile.ZipFile(temporary_output) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP CRC failure')
        for line in archive.read('PACKAGE_SHA256.txt').decode().splitlines():
            expected,name=line.split('  ',1)
            if hashlib.sha256(archive.read(name)).hexdigest()!=expected:raise ValueError('Package content hash mismatch')
    os.replace(temporary_output,output)
    print(json.dumps(dict(path=str(output),size_bytes=output.stat().st_size,
                          sha256=hashlib.sha256(output.read_bytes()).hexdigest(),**metadata),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--summary',type=Path,required=True)
    args=parser.parse_args();build(args.output,args.summary)
