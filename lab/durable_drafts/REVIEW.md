# Durable draft contract review — 2026-11-02

Builder and reviewer: the same Codex agent/session. This is source inspection plus bounded executed controls, not independent certification. No integration, acceptance, promotion or release is recorded.

## Executed evidence

| Group | Methods | Result |
| --- | ---: | --- |
| Actor/store, idempotency, persistence, corruption, cancellation and concurrent callers | 36 | PASS |
| Background fake-adapter lane and responsive controls | 11 | PASS |
| Whole-process file/transaction crash windows | 5 | PASS |

The broader assembly run passed all 126 methods. A disposable demo was also executed; its JSON observations are preserved. The existing B0 and modular candidates were not patched to obtain these results.

## Source findings and corrections during construction

1. An early corruption fixture kept its editing SQLite connection open. Refusal changed shared-memory reader bookkeeping, so file-preservation assertions failed. The fixture now explicitly commits and closes that connection before hashing a stopped profile. This corrects the fixture; it does not redefine shared-memory files as immutable under live readers.
2. Review found that merely checking a receipt envelope still allowed empty success results and unknown refusal outcomes. Startup now validates command-specific outcome shapes, supported refusal codes and matching events/attempts/artifact hashes. Both failures have explicit negative controls.
3. Request results and actor state are kept separate from the mutable adapter argument. An adapter trying to replace generation/attempt IDs cannot finalize under those forged IDs.
4. Reading every output inline would grow aggregate observations. Snapshot reads now page metadata; a separate bounded read returns one verified output. Oversized external artifact files are classified as invalid without loading their full contents.
5. A failed finalization/lost reply stops the lane and attempts to pause admission. The original completion identity/body is retained for a receipt query; the adapter is not rerun. A test injects reply loss after a real commit and confirms exact recovery and one adapter invocation.
6. An early file-creation shell command used the wrong working directory; no test file was created in that attempt. Subsequent source creation and the recorded full qualification succeeded.

## Invariants inspected

Only the actor thread opens its writable connection. Other threads exchange copied JSON envelopes and futures. A bounded queue limits admission. Shutdown joins the actor before closing the advisory writer lock. A blocked adapter does not own the database connection, and a stop timeout leaves store ownership intact. Refused mutation transactions roll back before a refusal receipt is saved.

Startup checks exact schema/version, SQLite quick_check, supported page size, contiguous event revisions, generation identity, successful event/receipt correspondence, supported receipt outcomes, immutable submit snapshots, authorization records, running-job/attempt agreement and historical attempt/artifact references. Missing artifact bytes are reported as incomplete/corrupt evidence rather than recomputed. Recovery interrupts RUNNING attempts, pauses dispatch, records orphans and never reconstructs authorization from output text.

This is a defined detectable-consistency floor, not proof against coordinated adversarial edits. The receipt/event chain has no external authentication anchor. Complete consistent rollback remains undetectable here. Native profile authority and access control must come from the future accepted coordinator, not these trusted harness methods.

## Limits and remaining work

- Production M1.2 requires B0 Windows qualification and an accepted exact parent; that gate is still open.
- The injected fake adapter is trusted Python. It can ignore cancellation or access its host process. No untrusted module, actual model or OS isolation was qualified.
- Cancellation is advisory for active computation. STOP_TIMEOUT reports uncertainty; it does not kill shared model services. Errors are distinct from clean lane STOPPED.
- Windows locking, paths, native IPC, physical disk failures, sleep/logoff and hardware durability remain unexecuted.
- The simple scan-based lab integrity checker and bounded profile sizes need performance measurement before production. WAL and total filesystem quotas are not fully enforced by a main-file page limit.
- No authenticated external client, GUI replacement, legacy database importer, network connector, model lock selection or Base admission was added.
- A large full request receipt retains its source/output data; this is intentional for contract checking, but privacy/retention policy and future transport budgets need explicit reconciliation.

Rollback: discard the isolated lab and its disposable profiles. Keep the unchanged historical/runtime/modular candidates. Do not transplant this actor alongside a live production writer.
