# LEVIS M1.1 repair: follow-up source and Windows crash review

October 25, 2026. **CANDIDATE / AUTHORITY_EFFECT: NONE. Structural acceptance pending.**

This follow-up was performed by the same agent that built the repair. It provides additional source analysis and executed Windows evidence, not an independent review, independent Windows execution, or authority to promote the candidate. No M1.2 implementation was started.

## Artifact identity

- Archive: `LEVIS_M1_1_REPAIR_CANDIDATE.zip`
- Recomputed SHA-256: `cb14b9eb60502d2a13d7cf95ef0298e98587c9b95fb31eab7925d6b9539e4101`
- ZIP CRC: passed; 83 files.
- Root manifest: all 82 listed files verified, with exact correspondence to the archive's non-manifest file set.
- New execution used a fresh temporary extraction of those verified archive bytes, rather than the builder's working source tree.
- Archive hash was checked again after execution: unchanged. Candidate source and existing application profiles were not modified.

## Source assessment of the reported repairs

| Invariant | Source assessment | Evidence and bounds |
|---|---|---|
| Writer ownership cannot be released under a delayed startup actor | Coordinator retains the Store before start. Timeout sets cancellation. Cleanup joins listeners and the Store actor before closing the profile lock. Store.close has no timed join that releases ownership while the actor remains alive. | Original delayed-start counterexample is addressed in the repaired control flow. Builder regressions cover before-open and in-transaction delays. This pass additionally checks actual process exits; it does not qualify every Windows filesystem stall. |
| Loss of an established ledger must not initialize a replacement | Existing-profile load requires READY metadata and an existing, sufficiently sized ledger. Store reopen uses mode=rw; schema creation is reachable only through explicit exclusive creation for a new profile. | No implicit empty-store creation path was found on normal established-profile startup. Missing/empty/truncated files and incomplete initialization are refused in builder regressions. The additional pre-READY crash check below confirms refusal after actual process exit. |
| Unsupported schema must be refused before lifecycle mutation | Startup checks full schema inventory before lifecycle UPDATEs or journaling-mode change, then integrity and singleton values. Unexpected triggers/views/indices/DDL are refused. Database CHECKs and actor transition checks exclude WORKING. | The original unexpected-trigger route is no longer accepted by the startup code. Builder regressions exercise that trigger and other unsupported objects/constraints. Same-user arbitrary database modification remains outside the stated security boundary. |
| Cross-logon behavior must be explicit and gated | Metadata requires SAME_LOGON_ONLY_UNQUALIFIED and matching user/logon. No identity update, rekey, migration or alternate open transport is implemented. | The policy is enforced as refusal, not cross-logon continuity. Actual logout/reboot/other-session behavior was not exercised here and remains unqualified. |

No additional blocking defect was established in the paths examined during this follow-up. That conclusion is limited to this source analysis and the specific execution below; it is not proof that all defects have been found or that the candidate is accepted.

## Additional native Windows execution

Three new checks go beyond merely rerunning the tests supplied with the repair. Each launched its own coordinator child process from the verified extraction and injected an immediate whole-process exit at a named boundary. Hooks lived solely in the external review harness; candidate files were untouched. Tests used disposable workspace profiles under the approved normal, non-elevated Windows user execution path. No installed LEVIS or unrelated process was terminated.

### 1. Exit after store startup, before READY metadata publication

The child exited with code 71 at mark_ready. Its ledger existed, but profile metadata remained INITIALIZING. Windows released the terminated process's native writer lock. An ordinary new coordinator invocation refused the incomplete profile, and the hashes/file set of its remaining files stayed identical. No replacement ledger or new secret was generated.

### 2. Exit after READY publication, before discovery publication

The child exited with code 72 at discovery publication. The profile was READY, its ledger had started, and discovery did not exist. Explicit native restart recovered PAUSED with startup_reason=unclean. Profile metadata and DPAPI-protected secret remained byte-identical. Authenticated idle stop completed with process exit code 0.

### 3. Exit after resume COMMIT, before the authenticated response

The child exited with code 73 when about to send the committed READY response. The client received an unconfirmed outcome. After explicit native restart, replaying the exact client/request ID and expected revision returned the historical committed receipt. Repeated replay returned the same outcome. The receipt's generation differed from the current runtime's generation, and the current runtime remained PAUSED throughout: the old control was not applied again. Authenticated idle stop exited cleanly.

These are real Windows child-process exits and restarts with test-only boundary hooks. They are not hardware power-loss tests. The builder's 64-test suite was not rerun again in this follow-up; its original log remains attributed to the builder run. These three checks are additional, separately logged scenarios, not an invented new aggregate certification count.

## Remaining acceptance and qualification work

1. An independent reviewer must inspect the repaired source and regression design and issue their own disposition. This same-agent follow-up cannot supply that independence.
2. Native Windows validation by that independent reviewer remains pending. This pass supplies additional native execution by the builder/reviewer agent only.
3. Real alternate accounts/logons, simultaneous Windows sessions, remote-host IPC, and supported Windows/Python combinations remain unqualified. Cross-logon continuity must stay disabled unless separately designed and actually qualified.
4. Hung native operations intentionally retain ownership. Availability/recovery procedures, incomplete-initialization recovery, hardware power loss and sustained stress remain as documented limitations.

The package remains **M1.1 REPAIR CANDIDATE — INTEGRITY PASS / STRUCTURAL ACCEPTANCE PENDING**. No promotion, seal, production migration or M1.2 work is authorized by this report.

## Reproduction materials

- `LEVIS_M1_1_REPAIR_FOLLOWUP_EVIDENCE/M1_1_REPAIR_FOLLOWUP_REVIEW.log`: new executed output.
- `LEVIS_M1_1_REPAIR_FOLLOWUP_EVIDENCE/review_m11_repair_crashes.py`: exact external harness. Run in this workspace with the original repair ZIP available and a normal non-elevated Windows Python environment. It locates the workspace through the archive path and uses only temporary profiles.
