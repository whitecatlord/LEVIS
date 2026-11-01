# LEVIS M1.1 repair candidate

October 25, 2026. **CANDIDATE / AUTHORITY_EFFECT: NONE. Separate structural review required.**

Start with this file and `REPAIR_IMPLEMENTATION_NOTES.md`. The original `START_HERE_M1_1.md`, `IMPLEMENTATION_NOTES.md`, `M1_1_CHANGED_FILES.json` and `evidence/M1_1_ALL_TESTS.log` are preserved historical parent records, not this repair's instructions/results. New evidence uses the `M1_1_REPAIR_` prefix. The root manifest covers this repair; the nested Starter manifest remains historical M0.1 provenance.

## Isolated run instructions

Use Python 3.12+ in a normal, non-elevated Windows PowerShell terminal outside an AppContainer. No extra packages are required. Open the terminal in the extracted repair package root:

```powershell
$levisProfile = Join-Path $env:LOCALAPPDATA 'LEVIS-M11-Repair-Isolated-Candidate'
python .\LEVIS_STARTER\runtime_coordinator.py --profile "$levisProfile" --init
```

`--init` requires a nonexistent directory. This repair uses profile/ledger schema version 2. Parent version-1 and legacy profiles are refused; no migration occurs.

In a second normal PowerShell terminal in the package root:

```powershell
$levisProfile = Join-Path $env:LOCALAPPDATA 'LEVIS-M11-Repair-Isolated-Candidate'
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" status
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" attach
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" detach
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" events --after 0 --limit 100
```

A fresh profile starts PAUSED at revision 3. Use the actual revision returned by status. For a fresh, otherwise unchanged profile:

```powershell
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" resume --revision 3 --request-id first-resume
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" pause --revision 4 --request-id first-pause
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" stop --revision 5 --request-id first-stop
```

For an uncertain control reply, retry the identical command, client ID, request ID and expected revision. A historical receipt never re-executes its control after restart. Once stopped, explicitly restart first if receipt retrieval is needed.

Within the **same Windows logon**, restart an established repair profile without `--init`; it always recovers PAUSED:

```powershell
python .\LEVIS_STARTER\runtime_coordinator.py --profile "$levisProfile"
```

Missing/empty/truncated databases, incomplete initialization and unsupported schemas are refused. Preserve the profile for review/recovery; do not erase its marker or rerun initialization over that directory.

## Cross-logon policy and shutdown

**SAME_LOGON_ONLY_UNQUALIFIED** is enforced. Another user/logon is refused before ledger opening. No automatic rekeying, identity update or migration is provided. Do not reuse this profile after logout/reboot and claim continuity. Preserve it; a distinct new isolated profile requires an explicit new `--init` path. Actual logoff/logon, reboot and simultaneous-session qualification has not been performed.

On startup timeout, cancellation retains the writer lock until the database thread has exited. A hung native operation can keep the process and lock alive; no timeout releases ownership under a possibly live writer. Explicit whole-process termination ends its threads and lets Windows release the handles; the profile may then require recovery and remains subject to refusal checks.

Attach/detach is still a CLI harness. No production GUI connection, jobs, inference, active-job drain, login registration, service, larger-file support or new filesystem authority has been added. Do not run the preserved legacy GUI to exercise this coordinator.

## Tests

```powershell
python -m unittest discover -s .\LEVIS_STARTER -p 'test_*.py' -v
```

Final result on this Windows PC: **64 passed** (31 unchanged inherited application tests, 21 retained runtime tests with initialization fixtures adapted, 12 repair tests). Full executed output: `evidence/M1_1_REPAIR_TESTS_FINAL.log`. Builder evidence is not independent approval or certification.
