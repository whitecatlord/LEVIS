# LEVIS M1.1 — Final Structural Closure Review

Date: October 25, 2026. Recommendation: **HOLD_FOR_REPAIR**.

Disposition: **CANDIDATE / AUTHORITY_EFFECT: NONE**. Operator retains final acceptance authority. No repair, integration, promotion, seal, executor, model invocation or production migration was performed.

Reviewer: the same Codex agent and coding session that implemented M1.1 and its repair. This is a fresh examination and new execution of the frozen artifact, **not an independent reviewer or independent certification**. Prior conclusions were treated as claims to check, not acceptance authority.

## Decision

The three originally reported implementation defects are addressed in the exercised paths. The candidate passes its supplied 64-test suite. It nevertheless fails two additional ledger-content integrity controls required by this review: a nonnegative but rolled-back revision is accepted despite contradictory events, and a damaged historical response is returned as a valid receipt. These gaps undermine the revision and outcome ledger that durable jobs would inherit. Do not use this candidate as the implementation parent for M1.2 until a separately authorized repair and review addresses them.

These are **synthetic inconsistent-ledger fixtures**, created only in stopped disposable profiles. They are not evidence that SQLite normally generates such states, that a power-loss event produced them, or that hostile same-user database editing is within the authentication threat model. The failure is accepting detectable internal inconsistencies during the explicitly requested corruption/recovery controls.

## Phase 1 — Verified identity and custody

Candidate: `LEVIS_M1_1_REPAIR_CANDIDATE.zip`.

Expected and recomputed SHA-256:

`cb14b9eb60502d2a13d7cf95ef0298e98587c9b95fb31eab7925d6b9539e4101`

Parent SHA-256, independently recomputed in this pass:

`cbb165fa52b1c79c7a249c34b17a05e52b468ee4bbfbf01a402ca62f350f874c`

| Identity/custody check | Result | Evidence |
|---|---|---|
| Candidate SHA-256 | PASS | Exact expected value above; checked again after execution |
| ZIP CRC | PASS | All members checked |
| Root manifest hashes | PASS | All 82 listed files match |
| Complete manifest membership | PASS | Exactly 83 ZIP members: manifest plus its 82 entries; no missing/unexpected members |
| Parent comparison | PASS | Five changed parent files, ten additions, zero removals |
| Inherited application bytes | PASS | Changed Starter files are limited to three runtime modules and the runtime test fixture; inherited GUI, library, away-work, ZIP, application tests, model locks/providers and Base payloads are unchanged |
| Candidate immutability | PASS | Archive and original extracted manifest-listed files rechecked; tests ran in disposable extractions/profiles |

The five changed parent files are:

1. `LEVIS_STARTER/runtime_coordinator.py`
2. `LEVIS_STARTER/runtime_profile.py`
3. `LEVIS_STARTER/runtime_store.py`
4. `LEVIS_STARTER/test_runtime_windows.py`
5. Root `MANIFEST_SHA256.txt`

The ten additions are:

1. `LEVIS_M1_1_STRUCTURAL_REVIEW.md`
2. `LEVIS_STARTER/test_runtime_repairs.py`
3. `M1_1_REPAIR_CHANGED_FILES.json`
4. `M1_1_REPAIR_PATCH.diff`
5. `REPAIR_IMPLEMENTATION_NOTES.md`
6. `START_HERE_REPAIR.md`
7. `evidence/M1_1_REPAIR_BEFORE.log`
8. `evidence/M1_1_REPAIR_PARENT_REPRO.py`
9. `evidence/M1_1_REPAIR_TESTS_FINAL.log`
10. `evidence/M1_1_REPAIR_TESTS_FIRST.log`

`custody.json` in the evidence bundle records per-file before/after hashes. `artifact_hashes.json` records candidate, parent, reference-document and review-evidence hashes.

## Source inspection — separate from execution

Read the seven runtime modules, repair regressions, pertinent inherited runtime assertions, and all three requested reference documents. Relevant control flow:

- Coordinator retains its Store before starting the actor, cancels on cleanup, joins listeners and Store, then closes the writer lock. Store.close joins without a timeout. This removes the original timed-cleanup ownership release path, with the documented availability cost of retaining ownership during a hung native operation.
- Established-profile load requires READY metadata and an existing, nontruncated ledger. Reopen uses SQLite `mode=rw`; creation requires the explicit new-profile path and exclusive file creation. INITIALIZING is not silently retried.
- Schema validation compares the entire stored schema with the expected DDL before lifecycle mutation. Database CHECKs and actor transitions exclude WORKING. However, content validation checks the runtime row largely in isolation. It does not reconcile its revision with the event ledger or validate persisted request outcome envelopes.
- Historical replay loads response JSON directly. The client accepts a missing request_id, and the CLI assumes a status field. This creates the damaged-receipt failure below.
- SAME_LOGON_ONLY_UNQUALIFIED remains enforced before ledger opening. Native ACL/peer/challenge/frame mechanisms were not modified or weakened.

This is source-level evidence. It does not establish arbitrary interleaving coverage, security certification, hardware durability or another user's actual logon behavior.

## Execution results

Execution used normal, non-elevated Windows user tokens outside the tool AppContainer; no permission or ACL widening was used. Python/Windows/SQLite versions are recorded in `artifact_hashes.json`. Temporary profiles were confined to workspace scratch directories; real profiles and installed applications were not opened for mutation.

| Run | Result | Scope |
|---|---|---|
| Supplied suite, fresh verified extraction | **64 passed**, 16.445 seconds | 31 inherited application tests, 21 retained runtime tests, 12 repair tests |
| Added final-review suite | **7 passed, 2 failed**, 6.414 seconds | Nine additional named tests, with several bounded subcases |
| Whole-process crash-boundary harness | **3 scenarios passed** | Before READY, after READY/before discovery, after durable commit/before reply |

The two red tests remain red; they were not weakened or reclassified as passes. An earlier added-suite run had a review-harness marker-path mistake in the precommit crash case. That log is retained as `adversarial_first.log`. The harness was corrected; the final run passes that case and retains the two genuine failures. The accidental scratch marker was removed. This was a harness correction, not a candidate patch.

### Inspection of assertion quality

- The supplied startup-cancellation tests assert actor liveness during cleanup and native second-lock refusal, then actor death before reacquisition. The additional test checks the specific Windows sharing violation (32) and a **real second coordinator process**, avoiding an assertion that might pass on any unrelated OSError.
- The supplied lost-reply test waits for READY before disconnecting; it therefore checks a committed outcome rather than assuming an early disconnect committed. This review also tests death before commit and confirms the opposite result: no receipt/event persisted and retry stays stale/refused after recovery.
- The supplied schema tests mutate a stopped valid SQLite database and compare files after refusal. They establish refusal of those schema objects. They do **not** establish consistency of otherwise schema-valid row contents; the new failing tests expose that boundary.
- The supplied revision checks cover type/nonnegative constraints and ordinary stale revisions. They do not test a nonnegative value below previously committed event revisions. The new control does.
- The no-executor tests support an architectural claim through source/import/command/profile inspection; they are not a complete operating-system filesystem audit or proof against arbitrary dynamically supplied code. The reviewed runtime contains no executor/model dispatch route.

## Newly established defects

### F1 — [P1] Detectable revision rollback is accepted and stale control revisions become valid

Location: `LEVIS_STARTER/runtime_store.py`, lines 112–117 (isolated runtime-row validation), lines 133–139 (startup revision increments), and lines 218–219 (revision comparison).

Reproduction, disposable stopped profile only:

1. Start a fresh runtime and stop it cleanly. Stored runtime revision and maximum event revision are both 5.
2. Execute `UPDATE runtime SET revision=0` against that disposable ledger and commit. Approved schema is untouched; SQLite quick_check still returns ok.
3. Explicitly reopen the profile. Instead of refusing the inconsistent ledger, startup succeeds PAUSED at revision 3, even though earlier events reach revision 5.
4. Submit a new resume request with expected_revision=3. It returns OK, READY, revision 4. A stale revision value from the earlier history has become usable again.

Observed cursor/revision split: startup event_cursor=8, revision=3; subsequent resume event_cursor=9, revision=4. The existing event ledger already provides evidence of the rollback, but startup does not examine it.

Impact: revision monotonicity and optimistic concurrency no longer hold for an internally inconsistent recovered ledger. Before durable jobs inherit this store, startup needs a defined consistency check against committed events/controls/receipts and explicit refusal rather than silently adopting the lower value. This review authorizes no repair and does not prescribe automatic rewriting of original evidence.

Exact test: `test_revision_rollback_with_valid_schema_must_be_refused` in `final_review_controls.py`. Final observation is preserved in `observations.json`.

### F2 — [P2] Damaged historical receipt is accepted and returned without an outcome envelope

Location: `LEVIS_STARTER/runtime_store.py`, lines 210–215; `runtime_client.py`, lines 39–45; downstream CLI failure at `runtime_cli.py`, line 22.

Reproduction, disposable stopped profile only:

1. Commit resume under client_id=test, request_id=receipt-damaged, expected_revision=3; then stop cleanly.
2. Change only that requests.response cell to the valid JSON text `{}`. Keep its identity/body hash and the schema unchanged. quick_check still returns ok.
3. Restart. Startup succeeds PAUSED; no receipt consistency error is reported.
4. Retry the identical original request. The server returns `{}` and Client.request accepts it.
5. Run the CLI with the same client/request/revision. It prints `{}`, exits 1 and raises `KeyError: 'status'` instead of providing a typed stored outcome or explicit integrity refusal.

Impact: an outcome query can present invalid durable evidence and crash the control client. This is not proof of duplicate execution in this scenario; the demonstrated failure is missing validation and failure reporting for the receipt ledger. It must be addressed before job outcome receipts are inherited. A future review should verify stored-envelope identity/shape and consistency, plus robust client handling of malformed server outcomes.

Exact test: `test_corrupt_receipt_outcome_must_be_refused_before_ready`. `observations.json` contains the native startup response, empty replay and CLI traceback.

## Explicit per-invariant disposition

PASS means the named bounded control passed, not universal certification. NOT TESTED means no execution claim is made.

| Invariant/control | Result | Evidence |
|---|---|---|
| DB01 startup timeout retains lock under live actor | PASS | Supplied regressions plus real second-process/shared-lock error-32 control |
| Cancellation before database opening | PASS | Supplied regression; actor exits before ownership reacquisition |
| Cancellation during initial schema COMMIT | PASS | Added trace-gated COMMIT control; lock retained, incomplete profile refused |
| Cancellation during lifecycle transaction | PASS | Supplied in-transaction regression; rollback and zero startup events checked |
| Actor shutdown precedes native unlock | PASS | Source cleanup order and actor-death/reacquisition assertions |
| Failed startup cleanup | PASS | Supplied initialization/schema/storage failures and added delayed-start cases |
| Second coordinator process denied ownership | PASS | Supplied process test plus added established-profile timeout contention |
| Missing/empty/truncated ledger not silently created | PASS | Supplied regressions rerun with file-preservation assertions |
| Incomplete initialization/ordinary explicit restart | PASS | Supplied regressions and actual process exit before READY |
| Valid same-logon restart recovers PAUSED | PASS | Supplied suite and all restart crash scenarios |
| Valid historical receipt survives lost reply/restart | PASS | Supplied suite, added duplicate/stop-disconnect control and postcommit death |
| Revision monotonicity against existing events | **FAIL** | F1: revision 5→0 accepted, recovery 3, stale resume accepted |
| Corrupt stored receipt refusal/typed outcome | **FAIL** | F2: `{}` replay accepted; CLI KeyError |
| Interrupted write before COMMIT rolls back | PASS | Actual child kill after uncommitted lifecycle/event writes; no READY event/receipt persisted |
| Interrupted reply after COMMIT retains receipt | PASS | Actual process exit before send; exact outcome survives without re-execution |
| Unexpected trigger/view/index/schema version refused | PASS | Supplied schema controls rerun; comparisons precede state writes |
| Modified columns/constraints refused | PASS | Supplied valid-SQLite schema fixtures |
| Invalid state, negative/nonnumeric revision, singleton deletion/key corruption | PASS | Added stopped-ledger fixtures with checks bypassed solely to create invalid contents |
| WORKING excluded in M1.1 | PASS | Source CHECK/actor guards and supplied regression; no executor exists |
| Client disconnect during committed resume | PASS | Supplied test waits for commit before disconnect |
| Client disconnect after stop reply, without ACK | PASS | Added native connection control; process exits, old receipt does not stop restarted runtime |
| Duplicate/conflicting request IDs | PASS | Supplied and added controls; one committed control/receipt under repeated ID |
| Ordinary stale expected revisions refused | PASS | Normal history control; F1 is the separate corruption failure |
| Malformed/oversized/replayed frames refused | PASS | Supplied native suite; invalid MAC/version/nesting/sequence and replay controls |
| Truncated prefix/body and authenticated scalar JSON | PASS | Added native controls; no revision change, reserved control remains usable |
| Healthy-history event cursors/revisions and receipt consistency after restart | PASS | Added exact persisted sequence and one-control/one-receipt assertions |
| Corrupted-history event/revision/receipt consistency | **FAIL** | F1/F2; healthy-history results cannot substitute |
| SAME_LOGON_ONLY_UNQUALIFIED restriction | PASS | Source gate and supplied labeled mismatched-identity fixtures |
| Actual alternate logon/session/reboot/remote-host behavior | NOT TESTED | Restriction stays enabled; no continuity claim |
| Hardware power failure / physical full disk / failing drive | NOT TESTED | Process exits and SQLite fault injections are not these tests |
| Sustained soak / multiple supported Windows-Python versions | NOT TESTED | Bounded run on recorded local environment only |
| Production GUI, jobs, models, migration or Base promotion | NOT TESTED | Explicitly outside review; none performed |

## Residual risk and closure conditions

The known original double-writer, missing-file recreation and unknown-trigger examples no longer reproduce in the supplied and added bounded controls. That does not compensate for accepting inconsistent ledger contents. The earlier follow-up's no-new-blocking-defect statement covered fewer cases; it did not exercise F1/F2.

Before closure, a separately authorized repair needs regressions that fail on this exact frozen candidate for both F1 and F2, without reducing the positive/negative controls already passing. Verification should establish a defined semantic consistency policy for runtime revisions, events, controls and durable receipts; corrupt evidence must be preserved for diagnosis, not silently normalized into a new history. Re-test real process commit boundaries after any repair. This report does not implement or approve that work.

Cross-logon continuity is not required for this M1.1 disposition under the Operator's directive. Keeping it disabled is an acceptable boundary; it is not the reason for HOLD. The two executed failures above are the reason.

Same-user malicious code, compromised Python/kernel, complete internally consistent old snapshots without an external anchor, adversarial filesystem races, indefinite native hangs, hardware durability and untested OS versions remain outside the established evidence. No claim is made that SQLite normally violates its transaction guarantees.

**Recommendation: HOLD_FOR_REPAIR. Authority effect: NONE. Final acceptance remains with the Operator.**

## Evidence and reproduction

The companion `LEVIS_M1_1_FINAL_REVIEW_EVIDENCE.zip` contains:

- `custody.json`: exact changed/added inventory and custody hashes.
- `supplied_suite.log`: freshly executed 64-test output.
- `adversarial.log`: final added suite, seven passes/two failures.
- `adversarial_first.log`: retained initial run, including the corrected harness-path failure.
- `observations.json`: actual responses, revisions, sharing-error and CLI evidence.
- `crash_boundaries.log`: three real process-exit scenarios, rerun for this review.
- `final_review_setup.py`, `final_review_controls.py`, `review_m11_repair_crashes.py`: exact reproduction harnesses.
- `artifact_hashes.json`: reviewed artifact/reference/evidence SHA-256 values and runtime environment.
- `SOURCE_ASSERTION_AUDIT.md`: what the named assertions establish and their limits.

The harnesses expect a workspace containing `outputs/LEVIS_M1_1_REPAIR_CANDIDATE.zip`. Setup creates `work/M1_1_FINAL_REVIEW_SOURCE` once and refuses to overwrite it; use a fresh review workspace or the verified extraction already created by this run. On Windows, run the supplied suite from that extraction, then `final_review_controls.py` and `review_m11_repair_crashes.py` with a normal non-elevated Python process. `final_review_controls.py` intentionally exits nonzero while F1/F2 remain reproducible. These are review controls, not repairs.
