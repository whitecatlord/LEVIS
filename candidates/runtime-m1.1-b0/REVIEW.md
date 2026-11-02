# B0 runtime repair continuation — 2026-11-02

Status: IMPLEMENTED / PORTABLE_CONTROLS_PASS / WINDOWS_QUALIFICATION_PENDING. Acceptance NOT_GRANTED; authority effect NONE. Runtime M1.2 remains blocked until B0 is reviewed and qualified on Windows. Builder and reviewer are the same Codex agent/session, not independent assessors.

Parent checkout: bfdf0e13a532192166a9d159f6f871d43e88fe66, candidates/runtime-m1.1-repair/LEVIS_M1_1_REPAIR_CANDIDATE/LEVIS_STARTER. Original parent bytes are preserved. SOURCE_BASIS.json distinguishes the inherited archive reference (not rehashed here) from this checkout identity. Inherited reports in Starter retain their original historical meaning; current evidence is in this directory's evidence/ folder. Starter's manifest is regenerated for the new candidate.

## Implemented repair

Before changing journal mode or writing startup lifecycle events, runtime_store validates:
- Contiguous event cursor/revision history, legal lifecycle transitions, unique generation starts, and agreement with the runtime singleton.
- Strict stored receipt shape, identity, supported status/error, bounded JSON, typed revisions/flags, and correspondence with a historical event.
- One matching compatible control for each successful receipt; no controls for refused receipts; supported body-hash shape.

Detectable corruption raises LedgerIntegrityError with LEDGER_INTEGRITY. Startup preserves that typed error for the coordinator diagnostic. It never truncates, recreates, normalizes or silently rewrites inconsistent evidence.

runtime_protocol now validates replies before the client acknowledges or presents them. This includes observations, historical control receipts, typed storage failures, attachment responses and paginated events. Missing identity/envelope fields and unsupported shapes refuse. For a control, an invalid/missing reply remains UNCONFIRMED, with the original identity retained for outcome recovery. Store error replies now include request_id so storage failures also have attributable envelopes.

## Executed evidence

| Group | Result | Evidence |
| --- | --- | --- |
| Store corruption, clean/unclean recovery, exact historical replay | 10 tests pass | evidence/portable-b0.log |
| Protocol/client envelope, event pagination, invalid reply/ACK handling | 9 tests pass | evidence/portable-b0.log |
| Real child exits during startup, before control commit, after control commit | 3 tests pass | evidence/portable-b0.log |
| Inherited application regressions | 31 tests pass | evidence/inherited-application.log |
| Native Windows IPC/profile controls | NOT RUN | qualify.py schedules inherited suites plus four new native controls on Windows |

The preserved before.log records 15 failing assertions across the original ten test methods/subcases on the frozen parent, including revision rollback and empty-receipt acceptance. after.log records the earlier ten-method repair run. The current full evidence is in evidence/. An initial harness run leaked actors when parent acceptance violated an assertion; cleanup was corrected before final recorded comparison. A later shell command used the wrong working directory when creating new tests; no source was created in that attempt. Subsequent creation and qualification succeeded.

Linux stubs only the otherwise unused Win32 import for store/client logic. Fake client channels do not qualify IPC. The crash controls terminate actual child processes, exercise actual SQLite transactions, and verify precommit absence versus postcommit receipt recovery. They do not test native pipe loss, profile-lock timing, physical power loss or hardware durability.

Run from this candidate directory:
```
python qualify.py --output <new-output-directory>
```
On Windows, QUALIFY_WINDOWS.cmd runs the same driver and adds the inherited 33 runtime tests plus four new native B0 startup/replay controls. It writes logs under a new temporary directory, never opens a production profile, never starts a model or executes drafts. That runner is supplied but has not been executed on Windows here. The historical final-review whole-coordinator/IPC crash harness still needs a rerun against the new artifact.

## Same-agent structural review and residuals

Validation precedes startup mutation; writer ownership, schema, ACLs, transport authentication, lifecycle scope and the no-executor/model boundary remain unchanged. Failed mutation commits retain typed storage failures and no success receipt. The stricter schema is the existing supported response shape, not a new protocol version.

Full-history scans are bounded by the inherited 64 MiB store quota; startup time still needs measurement on Windows. Complete internally consistent old snapshots remain undetectable without an external anchor. Request body hashes cannot be recomputed because original bodies were not stored. Undetectable coordinated edits and malicious same-user code remain outside established evidence. No cross-logon continuity, GUI migration, durable job dispatch, model run or Base promotion was performed.

Rollback: discard this candidate and disposable profiles; original candidate remains unchanged. Do not change HOLD on the historical parent or use this unqualified descendant as an accepted runtime parent.
