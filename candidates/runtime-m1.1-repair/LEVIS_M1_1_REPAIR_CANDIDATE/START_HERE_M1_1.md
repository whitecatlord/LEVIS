# LEVIS M1.1 — isolated coordinator candidate

October 24, 2026. AUTHORITY_EFFECT: NONE. No acceptance, Base promotion, Operator seal, or public release.

This candidate implements a separate, non-elevated Windows coordinator with authenticated local named pipes, one exclusive profile writer, a SQLite actor, revision-checked lifecycle controls, durable receipts, and sequenced events. Startup always enters PAUSED. Explicit resume enters READY; pause and idle stop are supported.

There is no job executor or model invocation in this milestone. WORKING is unreachable. Attach/detach is a CLI harness; the production Tkinter GUI has not been connected to the coordinator. Keeping actual draft work alive after closing the GUI requires the later M1.2–M1.4 slices.

All 59 files from the pinned M0.1 parent remain byte-for-byte unchanged. New runtime files are additions. `LEVIS_STARTER/MANIFEST_SHA256.txt` is the preserved parent manifest; the root `MANIFEST_SHA256.txt` covers this whole candidate. Read the new evidence separately from inherited M0.1 evidence.

## Run the isolated harness

Use Python 3.12+ in a normal, non-elevated Windows terminal, outside an AppContainer. No extra Python packages are required. Do not run `levis_desktop.py` to test M1.1: that is the preserved legacy app.

Extract the candidate ZIP and open PowerShell in its top-level folder. The profile below is new and separate from all legacy application profiles. Initialization refuses an existing directory.

```powershell
$levisProfile = Join-Path $env:LOCALAPPDATA 'LEVIS-M11-Isolated-Candidate'
python .\LEVIS_STARTER\runtime_coordinator.py --profile "$levisProfile" --init
```

Leave that terminal running. In a second PowerShell terminal in the same extracted folder:

```powershell
$levisProfile = Join-Path $env:LOCALAPPDATA 'LEVIS-M11-Isolated-Candidate'
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" status
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" attach
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" detach
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" events --after 0 --limit 100
```

Read the revision from `status`. A freshly initialized profile starts at revision 3. For that fresh profile only:

```powershell
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" resume --revision 3 --request-id first-resume
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" pause --revision 4 --request-id first-pause
python .\LEVIS_STARTER\runtime_cli.py --profile "$levisProfile" stop --revision 5 --request-id first-stop
```

Always use the actual current revision. A stale revision is refused. If a control reply is lost, the CLI reports UNCONFIRMED and retains the request ID/revision; retry the identical command with the identical client ID, request ID, and revision. Reusing the ID with different arguments is refused. A receipt from an earlier runtime generation describes the original outcome and does not reapply it after restart. If the coordinator has stopped, receipt retrieval requires explicit restart first.

To explicitly restart an existing M1.1 profile during the same Windows logon, omit `--init`. It starts PAUSED regardless of its prior state:

```powershell
python .\LEVIS_STARTER\runtime_coordinator.py --profile "$levisProfile"
```

Closing a CLI client does not stop the coordinator. Closing its own hosting terminal or terminating its process can interrupt it; the next explicit startup recovers PAUSED. This candidate does not register a service, login task, or startup entry.

## Verification

Executed on this PC: Windows 11 build 26200, Python 3.12.10, native Windows pipes and normal non-elevated user tokens.

```powershell
python -m unittest discover -s .\LEVIS_STARTER -p 'test_*.py' -v
```

52 tests passed: 31 inherited tests rerun and 21 new native runtime tests. Full executed log: `evidence/M1_1_ALL_TESTS.log`. Existing model/network interactions in the inherited unit tests use mocks; no live LLM run was performed. The coordinator itself has no model or job path.

Read `IMPLEMENTATION_NOTES.md` for controls, evidence limits, and unresolved risks before considering integration.
