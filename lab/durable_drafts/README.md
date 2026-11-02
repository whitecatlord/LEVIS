# Durable draft contracts — LAB prototype

Date: 2026-11-02. Status: ISOLATED_CONTRACT_PROTOTYPE / 52_TESTS_PASS_ON_LINUX. AUTHORITY_EFFECT: NONE. Acceptance: NOT_GRANTED.

This advances preparation for the B1 / runtime M1.2 draft lane described in the existing persistent-runtime design. It is not integrated into M1.1, does not use the unqualified B0 candidate as an accepted implementation parent, and does not close the M1.2 dependency gate. All existing runtime, GUI, Base and modular candidates remain unchanged in this continuation.

## What works in this prototype

- A single actor owns writable SQLite and artifact operations. A second process cannot obtain the lab writer lock while the actor is alive. Explicit profile creation and unknown-schema refusal are separate from reopening.
- Submissions store exact UTF-8 text snapshots, source hashes, a bounded goal and explicit DRAFT_ONLY authorization attribution. No file path is read from a job payload. Attribution is provided by trusted harness code, not authenticated here.
- Resume enables eligible authorized jobs; startup always pauses. One durable RUNNING attempt is allowed globally. Failed, interrupted and cancelled jobs require an explicit reauthorized retry. A retry creates a new attempt linked to the previous one.
- A background lane calls an explicitly injected fake Python adapter. The actor remains responsive. Pause closes further admission while an active attempt drains. Cancellation is recorded as pending until the active outcome resolves; late output is retained as cancelled-output, never a completed draft.
- Output is flushed, hashed and renamed to an attempt-specific artifact before artifact reference, terminal states, event and request receipt commit together. Only that commit returns success. Interrupted files remain visible as orphans; they are never silently adopted or deleted.
- Questions and answers preserve their exact history. A missing/corrupt question prevents continuation. The 6,000-character continuation budget refuses overflow instead of discarding old context.
- Receipts include original request bodies and hashes. A repeated identical request returns its historical outcome. Reusing its identity with a different body refuses. Lost completion replies can be queried without rerunning the adapter.
- Reads verify committed artifact bytes. Missing/corrupt drafts expose CORRUPT_OR_MISSING, completed=false and no trusted output text. Snapshots page job metadata; a separate read returns one verified artifact.

## Run

From this directory, Python 3.12+:
```
python -m unittest discover -p "test_*.py" -v
python demo.py
```

The demo creates a temporary profile, submits one fake-adapter job, shows paused admission and committed output, then removes the disposable profile. It does not install anything or start a model. The adapter input remains data; no generated code is executed.

From repository root, all assembly groups:
```
python tools/qualify_assembly.py --output <new-output-directory>
```
The complete Linux run records 126 passing methods: B0's 53 portable/application controls, modular B5's 21 controls, and this lab's 52 controls. On Windows the B0 driver additionally schedules native tests; no Windows execution is claimed here.

## Tested failure boundaries

The five real child-process exit controls cover: after attempt claim, after a pending-file flush, after output rename, before finalization COMMIT, and after COMMIT before a reply. Precommit loss recovers paused/interrupted with no completion receipt; pending/renamed files are orphan evidence. Postcommit loss preserves exact historical replay. These are actual process exits and SQLite transactions, not physical power-loss tests or native Windows IPC tests.

Other controls cover concurrent claims and duplicate requests, another writer process, blocked and unresponsive adapters, pause/cancel races, receipt corruption, input tampering, missing authorization, unknown schema, missing established databases, failed COMMIT acknowledgement, and strict historical outcome validation. evidence/qualification.log is the executed 52-method result; REVIEW.md maps evidence and limits.

## Bounds and intended integration

Prototype bounds: 256 jobs, 32 attempts per job, 32 input items, 10,000 selected-text characters, 3,000 goal/question/answer characters, 30,000 draft/failure characters, 6,000 continuation characters, 256 KiB request envelope, 25 jobs per snapshot page and 100 events per event page. SQLite main-file ceiling is 16,384 4-KiB pages; artifact ceiling is 64 MiB and 1,024 entries. WAL/temporary-file and total-volume behavior still require target-system qualification.

The future coordinator must own this concern through its accepted single actor and authenticated typed command router. Do not put this lab database beside a live coordinator as a second production writer. Extraction needs schema reconciliation/migration, pinned model verification, bounded adapter cancellation, IPC admission, real client detach tests, output-path custody and a fresh review. Reference tools, chat and production GUI migration are separate stages.

The lab lock uses flock on Linux and msvcrt locking on Windows. Only the Linux path was executed here. The fake adapter is trusted in-process Python with no OS isolation: this is not a sandbox or an untrusted-code host. No actual Operator authentication, model service, shared Ollama cancellation, network path detection, native profile ACL or production migration is provided. A reported STOP_TIMEOUT retains uncertainty and does not pretend to kill external computation.


## Windows and opt-in real-model continuation

The [November 2 Windows checkpoint](../../docs/WINDOWS_CHECKPOINT_2026-11-02.md) records this lab passing 61 methods on Windows, including nine new adapter controls. `ollama_adapter.py` and `run_local_model.py` provide an explicitly invoked loopback-only, digest-checked local model path. The synthetic real-model smoke committed a hash-verified draft. Earlier fake-adapter/Linux descriptions above remain the historical prototype scope. The new adapter is trusted local integration, not an execution sandbox, atomic weight pin, or independent model trial. Cancellation does not prove the service stopped. The production runtime remains separate.
