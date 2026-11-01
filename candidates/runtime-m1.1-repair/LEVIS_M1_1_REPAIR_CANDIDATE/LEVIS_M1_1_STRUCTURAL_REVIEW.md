# LEVIS M1.1 structural review

October 25, 2026. Disposition: CANDIDATE / AUTHORITY_EFFECT: NONE. Fix the three findings below before using M1.1 as the parent for durable jobs in M1.2.

Reviewed archive SHA-256: `cbb165fa52b1c79c7a249c34b17a05e52b468ee4bbfbf01a402ca62f350f874c`.

Recomputed archive SHA-256, passed ZIP CRC, verified its root manifest, and confirmed extracted source matches the archive. Read all seven runtime modules and compared them with M1.0 sections 4–9, 11 and 13. Ran focused Windows reproductions in new disposable profiles under the approved normal-user execution path. No candidate source, archive, installed app or real profile was modified. The 52-test original result remains valid for that original suite; that suite did not cover the failures below. This review is not independent Windows security certification.

## 1. [P1] A startup timeout releases ownership before its database actor exits

Location: `LEVIS_STARTER/runtime_store.py`, lines 21–25; cleanup consequence in `runtime_coordinator.py`, lines 49–52. Design: section 6 exclusive ownership for the writer's entire lifetime; DB01.

The constructor waits 10 seconds for readiness, joins for only two seconds after a failure, then raises without checking whether the actor stopped. A slow actor can remain alive. Because construction never returns, the coordinator's `self.store` remains None; its finally block skips store cleanup and closes the profile lock. A second coordinator can then acquire that lock while the old actor later opens or continues writing the same database.

Reproduced with a gated startup worker and a shortened readiness timeout to avoid waiting 12 seconds. The first coordinator unwound, its actor remained alive, and a second native Windows ProfileLock succeeded. Releasing the worker gate allowed the old actor to initialize and commit PAUSED while the second owner still held the lock. This is a controlled startup-delay fault injection, not a claim of a naturally observed disk stall.

Required repair: keep profile ownership until every possible writer is confirmed terminated. Prefer constructing/retaining the actor before starting it, cooperative cancellation checked before opening/writing SQLite, and explicit wait/termination behavior for startup failures. Never unwind ownership while a startup thread can still become a writer. Add a delayed-start two-owner regression and verify the actor cannot commit under a replacement owner.

## 2. [P1] Existing profiles silently receive a fresh database when theirs is missing

Location: `LEVIS_STARTER/runtime_store.py`, line 34 and lines 48–59; `runtime_profile.load` does not require an established database. Design: sections 6 and 8 durable receipts and evidence-preserving recovery; DB04/startup REC01.

`sqlite3.connect(path)` creates a missing file, and an empty schema unconditionally follows the fresh-store initialization path. Existing-profile startup therefore cannot distinguish first initialization from loss of the database. The profile secret and identity still validate, so a missing store produces a normal PAUSED runtime with reset revisions and no prior idempotency receipts.

Reproduced by creating a disposable store, committing resume/stop (revision 6, two receipts), closing it, and moving its database aside intact. Loading the established profile and opening Store succeeded with PAUSED, revision 3, and zero receipts. The old database was preserved outside that disposable profile for the duration of the reproduction. No real data was removed.

This does not itself execute any work in M1.1, but it silently loses access to the controls/event history and the deduplication ledger that M1.2 would depend on.

Required repair: separate explicit first-time database creation from reopen/recovery. Persist an initialization phase/marker under exclusive ownership, use an existing-file connection mode for established profiles, and report missing/empty/truncated stores as recovery errors. Do not silently start a new ledger under the old profile identity. Add absent, empty and partial-initialization regressions.

## 3. [P2] Schema validation ignores unexpected triggers and other schema structure

Location: `LEVIS_STARTER/runtime_store.py`, lines 48–61. Design: section 7 RECOVERING schema validation; section 13 WORKING unreachable; DB04.

Startup checks only the set of table names, user_version and SQLite quick_check. It does not validate column definitions, constraints or unexpected triggers/views. A structurally different database can therefore pass startup and run schema code when lifecycle records change.

Reproduced by adding a trigger to a disposable existing store: after a transition to READY, it updates runtime.state to WORKING. The database retained the expected table names and user_version, and quick_check returned ok. Store accepted it, recovered PAUSED, then acknowledged resume with status OK and state WORKING. No executor ran; the demonstrated failure is acceptance of unsupported schema and violation of the M1.1 state invariant.

This is a corrupt/unsupported-schema recovery control, not a claim that arbitrary malicious same-user code is inside the security boundary. Such code is already explicitly outside the threat model.

Required repair: validate the complete supported schema before lifecycle mutations, reject unknown triggers/views/indices or explicitly account for approved ones, validate singleton contents and permissible stored states, and enforce M1.1 state constraints in the database and application. Add a valid-SQLite/unsupported-schema test; the existing corrupt-file test only exercises non-SQLite bytes.

## Known continuity limitation: profile identity includes the creating logon

`runtime_profile.py` lines 31 and 47–48 save and later compare the whole `{user, logon}` identity. The candidate explicitly documents that profiles are refused after a new Windows logon. This is confirmed by source inspection; this review did not log the user out or reboot the PC.

Before production continuity claims, distinguish durable profile ownership (stable user/profile identity and user-bound protected secret) from the current runtime's logon-specific endpoint ACL and peer checks. Define a controlled, explicit reopen procedure for a later logon, keeping the exclusive profile lock across sessions. A fix must not weaken current-logon IPC isolation. Test actual logoff/logon, reboot, and simultaneous sessions before claiming that qualification.

## Requirement assessment

| M1.0 area | Source-review result |
|---|---|
| Headless process and GUI separation, section 4 | Implemented for the CLI skeleton; GUI migration remains correctly excluded |
| Authenticated Windows IPC, section 5 | Implementation includes narrow ACLs, native peers, DPAPI, nonce proofs and framed MACs; real alternate-account/session/remote-host qualification remains open |
| Single writer and durable storage, section 6 | Normal-path implementation present; startup-timeout ownership and missing-store recovery are blocking findings |
| Lifecycle and recovery, sections 7–8 | Normal PAUSED/READY/idle-stop present; unsupported-schema acceptance can violate the state invariant; logon continuity unresolved |
| Migration, section 9 | No production migration performed, consistent with M1.1 isolation |
| Negative controls, section 11 | Original suite is useful but missed the reproduced startup/recovery/schema conditions |
| M1.1 exclusions, section 13 | No job execution, model invocation, Base promotion, service registration or production GUI integration introduced |

## Evidence and next bounded step

`LEVIS_M1_1_REVIEW_EVIDENCE/M1_1_REVIEW_REPRODUCTIONS.log` contains the newly executed output. `review_m11.py` contains the exact review harness. It uses temporary workspace profiles and never patches the candidate. The unknown-trigger fixture and moved database are disposable test data; the startup-delay fixture temporarily patches in-memory methods only, restoring them before allowing the actor to continue.

The next build should be M1.1 repair/closure with a separate candidate, parent checksum, changed-file census and new regression evidence. Close findings 1–3 and resolve or explicitly gate the logon-transition design before adding durable jobs. Do not expand model, execution, filesystem or Base authority during that repair.
