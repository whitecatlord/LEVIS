# M1.2 same-agent structural review — 2026-11-02

Disposition: **implemented separate candidate / bounded Windows qualification PASS / independent review and scoped acceptance pending**. Builder and verifier are the same agent/session. This is not independent certification, production deployment, or completion of the LEVIS body. The previous artifacts and their dispositions are preserved.

## Parent and changed boundary

The parent is the November 2 Windows assembly, public commit `0ba4dea34939b69198ef1e1e036d5f2dc2b0de1a` (byte-equivalent local commit `f79cc2d2639576f32ebd3ade521c507717a9414d`). SOURCE_BASIS.json pins the inherited runtime and draft contract files by hash. M1.2 is a new directory; the parent is not modified. The Operator authorized advancing this integration in the current work; no independent acceptance is inferred.

The draft lab repository methods were extracted without its actor, connection, profile creation, or advisory writer lock. SQL table names are explicitly prefixed in the resulting source. The runtime schema combines these tables with lifecycle and provider records. This is one physical SQLite database and actor connection, not an attached two-database transaction. The worker performs inference after claim COMMIT and returns an outcome through the actor queue. Public job commands cannot reach worker claim/finalize methods.

## What the controls establish

Final target run: Windows 11 build 26200, Python 3.12.10; 79 methods scheduled, **78 passing, 1 skipped**, exit 0, candidate source hashes unchanged during qualification. The skipped M1.1-only test asserts that WORKING is globally unreachable. Its source is preserved with an explicit skip and replaced in M1.2 by authorized claim/lifecycle and rollback controls. It is not counted as a pass.

New controls exercise shared actor/thread ownership, one database, paused submission, exact input bytes, independent revision namespaces, pause drain, stop intent/drain, late cancellation, question/answer restart, interrupted-attempt explicit retry, exact receipt replay/conflicts, rejected public internal commands, malformed reads without actor death, real identity attribution, bounded requests, atomic rollback of pause/claim/finalization, orphan preservation, detectable cross-ledger inconsistency, provider history, and strict job response validation.

Native process controls exercise an actual separate client exiting after submission/resume/detach, pause preventing the next job, stop draining and exiting, active cancellation, process kill/restart without silent rerun, a second coordinator's native sharing violation, reserved endpoint restrictions, completed artifact replay, corrupt receipt refusal before recovery, lost submit replies, and STOP_TIMEOUT retaining the writer lock. Four whole-coordinator exit hooks distinguish claim-before-commit, finish-before-commit, finish-after-commit, and submit-after-commit/before-reply. They are process/SQLite controls, not physical power-loss tests.

The inherited native security, ownership, quota, IPC authentication/frame, schema, startup-cancellation, and B0 repair regressions also run against this new profile. The exact logs show all scheduled methods and the one explicit skip. Earlier native-profile admission failures and the earlier M1.1-scope failure are retained as first-run evidence; they were corrected rather than reported as passes.

The real-model demo used a synthetic fixture and the installed expected `qwen3.5:4b` digest. A job submitted through native authenticated IPC completed after detach/reattach, with one committed job, a hash-verified draft, and the recorded provider model/digest. The raw draft is retained. It did not strictly follow the requested sentence count; this is a persistence/connectivity smoke test, not proof of semantic correctness. No generated code was executed.

## Same-agent inspection

- SQLite connections are created by the runtime actor; repository and lane do not open a persistent writable connection. Shared schema validation precedes lifecycle/draft recovery writes.
- Runtime/draft recovery and provider-generation insertion share the startup transaction. A claim and WORKING share one outer transaction; finalization and READY/PAUSED/STOPPED share another. Savepoint refusal handling cannot commit the outer transaction early.
- Request bodies are copied at admission. Public IDs are namespaced away from internal worker/control identities. Stored job bodies/hashes and receipts remain replayable; current caller labels do not grant authority. Profile identity supplies the authorization attribution.
- Job/lifecycle/provider consistency is checked on reopen. Corrupt or unknown shapes fail closed. There is no automatic history truncation, reset, rekeying, old-profile migration, or adoption of orphan output.
- Pause/stop do not close the actor or release the native profile lock while the worker remains alive. The reserved control endpoint remains independent of slow ordinary clients. Storage failure closes further admission and causes cleanup with ownership retained until the worker/actor exit.

## Limits and next work

Same-user malicious processes, compromised local services/Python/kernel, internally consistent snapshot rollback without an external anchor, adversarial file replacement races, physical disk failure, reboot/cross-logon behavior, network filesystems, sustained soak, and broader supported Windows/Python matrices remain unqualified. The model tag checks are not atomic and cannot prove the server used specified weights. Cancellation and timeouts cannot prove a shared model stopped computing. The source corpus remains data; prompt guidance is not a sandbox or a truth verifier.

This candidate is headless. The production Tkinter GUI, chat migration, reference ownership, evidence-memory lab integration, modular process isolation, and final acceptance remain separate. No installed application or real profile was switched. Next steps are independent review of these exact bytes, then chat/client migration against this typed interface with explicit source snapshots and revision handling.
