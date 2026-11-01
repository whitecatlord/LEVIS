# LEVIS M1.1 repair implementation and verification

October 25, 2026. **CANDIDATE / AUTHORITY_EFFECT: NONE.** Repair submission for separate structural review; no self-approval, Operator seal or Base promotion.

## Parent and review basis

Parent: `LEVIS_M1_1_COORDINATOR_CANDIDATE.zip`. Expected and recomputed SHA-256:

`cbb165fa52b1c79c7a249c34b17a05e52b468ee4bbfbf01a402ca62f350f874c`

Review: `LEVIS_M1_1_STRUCTURAL_REVIEW.md`, copied unchanged into this package. A separate extraction was repaired. Original archive/source bytes remain unchanged. Parent ZIP CRC/root manifest and extracted-source correspondence passed before changes. Root manifest and external checksum identify the repair; the external verification report records its final archive hash, avoiding a self-referential hash inside the archive.

## Original defects reproduced before repair

The verified original parent was rerun before modifications. Evidence: `evidence/M1_1_REPAIR_BEFORE.log` and `M1_1_REPAIR_PARENT_REPRO.py`. All profiles were disposable native Windows profiles; no installed profile or candidate file was changed.

| Finding | Original observed behavior |
|---|---|
| P1 ownership | After injected startup delay/timeout, actor remained alive; second native writer lock succeeded; original actor then committed PAUSED under that second owner's lock |
| P1 missing ledger | Established revision 6/two-receipt database was moved aside intact; reopen silently produced PAUSED revision 3/zero receipts |
| P2 unsupported schema | Unexpected valid-SQLite trigger passed quick_check/startup; resume returned OK with WORKING |

The delay/readiness deadline are test-only in-memory injections. These are controlled failure reproductions, not naturally observed disk-stall or adversarial Windows qualification claims.

## Repair implementation supplied

### Retain writer ownership until actor exit

The coordinator retains an unstarted Store before starting its actor. Readiness failure requests cancellation. Cleanup waits for listeners and actor exit before releasing the native writer lock. Direct Store construction also joins its actor on failure. Actor close has no timeout that could relinquish ownership under a live writer.

Cancellation is checked before database creation/opening, through lifecycle writes and before startup COMMIT. Connection close rolls back unfinished transactions. Actor exit fails pending queued calls. A truly hung native operation retains ownership until it returns or the entire process is terminated. This is an explicit availability limitation, not an automatic lock-release workaround.

Two regressions gate startup before SQLite access and inside its lifecycle transaction. Both confirm second-owner refusal while the actor is alive and lock availability only after exit. The transaction case checks STOPPED revision 0/zero startup events after cancellation rollback.

### Separate first initialization from ledger recovery

Profile metadata version 2 records INITIALIZING or READY. Only explicit initialization of a nonexistent profile authorizes exclusive ledger-file creation. Reopen uses SQLite URI `mode=rw`, which cannot create an absent ledger. Established launch requires READY metadata, a nontruncated existing ledger and complete schema/content validation.

The coordinator atomically marks the profile READY under ownership after store startup. Interruption before READY publication is refused on ordinary launch, including when a complete schema already exists. No secret replacement, ledger reset, marker rewrite or implicit initialization retry is used to make the profile runnable. An explicit recovery procedure is future work.

Parent profile/schema version 1 is deliberately refused without conversion. This isolated repair does not migrate parent or production profiles.

### Validate schema and prohibit unsupported states

Schema version 2 adds a checked singleton key; allowed state checks; integer/nonnegative revision checks; clean-marker relation; event-state checks; and control-command checks. WORKING is absent. The actor independently validates lifecycle transitions before issuing SQL and uses explicit-column queries.

Before lifecycle mutation or journaling-mode change, startup compares the complete SQLite schema inventory against the approved DDL instantiated in an in-memory reference on the actor thread. It accounts for tables, definitions/constraints, triggers, views, indices and generated SQLite objects. Unknown structure is refused, followed by integrity and singleton-content validation. trusted_schema is disabled. No unapproved trigger is invoked to repair or normalize state.

Regressions exercise the original trigger, views, indices, changed columns/constraints/version, forbidden WORKING state and extra singleton insertion. These checks are unsupported-schema recovery controls; malicious same-user software remains outside the security boundary.

### Enforce a gated cross-logon policy

Policy: **SAME_LOGON_ONLY_UNQUALIFIED**. Metadata records that exact policy and its creating user/logon. An unknown policy or different identity is refused before opening the ledger. There is no automatic identity update, rekey, reset, migration or alternate open endpoint. Native peer checks, current-logon pipe ACLs, DPAPI and authenticated framing remain unchanged.

This does not implement or claim cross-logon continuity. Actual logoff/logon, reboot and simultaneous-session qualification was not performed. The refusal regression supplies a different identity in-memory: it is a labeled fixture, not a real second Windows logon. Same-logon restart is exercised natively and preserves secret/metadata and original receipts while recovering PAUSED.

## Executed tests and negative controls

Final command, run from the build workspace:

`python -m unittest discover -s outputs/LEVIS_M1_1_REPAIR_CANDIDATE/LEVIS_STARTER -p 'test_*.py' -v`

LEVIS_TEST_PARENT selected the workspace work directory. Tests used the approved normal-user path outside the AppContainer, real Windows pipes/token/ACL/DPAPI, and disposable profiles. No ACL grants were broadened. The runtime still refuses elevated/AppContainer tokens.

**64 passed in 19.106 seconds:** 31 unchanged inherited workbench/library/away/ZIP tests; 21 retained native runtime tests with initialization fixtures adapted; 12 new repair tests. Full log: `evidence/M1_1_REPAIR_TESTS_FINAL.log`. The earlier 62-test repaired-run log is retained; two final tests add in-transaction cancellation and explicit parent-schema refusal. Parent evidence remains historical, not presented as newly executed.

| Negative control | Repair-run observation |
|---|---|
| Delayed actor before DB access | Second owner refused until actor exit; no ledger created after cancellation |
| Delayed actor inside transaction | Second owner refused; lifecycle changes rolled back before unlock |
| Missing established ledger | Refused; no replacement; preserved old revision/receipts retained |
| Empty/truncated/invalid ledger | Refused without initialization or profile rewrite |
| Interrupted initialization before/after schema | Refused; secret/marker preserved |
| Duplicate create / absent rw reopen | Refused; old bytes unchanged / no file fabricated |
| Unexpected trigger | Refused before startup mutation; bytes unchanged |
| View/index/column/constraint/version mismatch | Refused before mutation |
| WORKING / second singleton | Database refuses; actor rejects illegal transition and rolls back |
| Parent-v1 ledger | Refused without migration or byte changes |
| Different identity / unknown policy | Refused without ledger/secret modification; identity mismatch is a fixture |
| Same-logon restart | PAUSED; stable metadata/secret; historical receipt returned without re-execution |
| Existing IPC/writer/storage/lifecycle controls | Retained 21-test suite passed, including actual SQLITE_FULL and COMMIT/lock fault controls |
| Scope exclusions | Import/command/state/profile census passed; original application/model/provider/Base bytes preserved |

## Limitations and separate review

- Results are builder evidence, not independent structural acceptance or Windows security certification. Closure disposition remains for separate review.
- Cross-logon continuity stays disabled. Real alternate users, logoff/logon, reboot, simultaneous Windows sessions and remote-host IPC remain unqualified.
- A hung native operation may prevent shutdown finishing; its lock remains owned. A separate writer-process architecture or force-termination policy would be additional design work.
- Interrupted initialization needs an explicit future recovery procedure. No version-1 or production migration is implemented.
- Schema SQL comparison is conservative; unrecognized variations are refused. Only the executed Windows/Python/SQLite combination is evidenced.
- Same-user malicious code and adversarial filesystem races remain outside the established boundary. Path and ACL restrictions are unchanged.
- No power interruption, physical disk-fill/failing-drive, sustained soak or production deployment test was performed. Startup delay, quota and COMMIT failures are labeled injections.
- No executor, model invocation, large-file support, filesystem-root expansion, production GUI migration, Base change, promotion or seal was added.

**Disposition: CANDIDATE / AUTHORITY_EFFECT: NONE, awaiting separate structural review.**

## Final artifact verification

- Output: `LEVIS_M1_1_REPAIR_CANDIDATE.zip`
- Output SHA-256: `cb14b9eb60502d2a13d7cf95ef0298e98587c9b95fb31eab7925d6b9539e4101`
- Output bytes: 5930689
- Archive files: 83
- Final ZIP CRC and complete root manifest: passed.
- Original parent archive and extracted manifest-listed files: unchanged.
- Changed-file census and source diff: included in repaired ZIP.
- Disposition: CANDIDATE / AUTHORITY_EFFECT: NONE. Separate structural review pending.
