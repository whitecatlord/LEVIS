"""Reproducible isolated qualification. Existing output directories refuse."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    (output/'profiles').mkdir()
    root = Path(__file__).resolve().parent
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', LEVIS_TEST_PARENT=str(output/'profiles'))
    env.pop('LEVIS_TEST_SOURCE', None)
    groups = [('portable-b0', root, ['test_b0_ledger', 'test_b0_responses', 'test_b0_crashes']),
              ('inherited-application', root/'LEVIS_STARTER', ['test_workbench', 'test_away_work', 'test_library_tools', 'test_zip_reader'])]
    if os.name == 'nt':
        groups.append(('native-windows', root/'LEVIS_STARTER', ['test_runtime_windows', 'test_runtime_repairs', 'test_runtime_b0_windows']))
    results = []
    for label, cwd, modules in groups:
        command = [sys.executable, '-m', 'unittest', *modules, '-v']
        try:
            process = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, timeout=240)
            log = process.stdout; code = process.returncode
        except subprocess.TimeoutExpired as error:
            log = (error.stdout or b'')
            if isinstance(log, bytes): log = log.decode('utf-8', errors='replace')
            log += '\nQUALIFICATION TIMEOUT: inspect any surviving child processes.\n'; code = 124
        (output/(label+'.log')).write_text(log, encoding='utf-8')
        count = re.search(r'Ran (\d+) tests?', log)
        results.append(dict(group=label, exit_code=code, tests=int(count[1]) if count else None))
        print(f'{label}: {"PASS" if code == 0 else "FAIL"}', flush=True)
    summary = dict(platform=platform.platform(), python=platform.python_version(), results=results,
                   native_windows_executed=os.name == 'nt', acceptance='NOT_GRANTED', authority_effect='NONE',
                   residuals=['independent review required', 'physical durability not qualified',
                              'same-logon restriction retained', 'full historical final-review process/IPC harness still required'])
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    return int(any(x['exit_code'] for x in results))


if __name__ == '__main__': sys.exit(main())
