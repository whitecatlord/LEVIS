# M1.2 command and ownership contract

The inherited native transport keeps same-user/same-logon peer checks, DPAPI profile secret, mutual HMAC proofs, sequenced authenticated frames, a separate reserved lifecycle endpoint, bounded JSON, and explicit revisions. This candidate expands the command vocabulary and uses a new, isolated version-3 profile. It provides no cross-logon continuity or migration.

## Revisions and routes

| Command | Expected revision | Payload / result |
| --- | --- | --- |
| status, snapshot, attach, detach | none | inherited lifecycle observation |
| events | none | `{ "after": 0, "limit": 100 }`; lifecycle events |
| pause, resume, stop | `status.revision` | empty payload; durable control receipt |
| jobs | none | empty or `{ "after": 0, "limit": 25 }`; `reply.draft` snapshot |
| job-events | none | `{ "after": 0, "limit": 100 }`; draft events |
| job-artifact | none | `{ "attempt": "ID" }`; hash-checked text, integrity, provider |
| job-submit | `jobs.draft.revision` | goal, literal inputs, explicit DRAFT_ONLY authorization |
| job-answer | `jobs.draft.revision` | job, literal answer text, fresh authorization |
| job-retry | `jobs.draft.revision` | failed/interrupted/cancelled job, fresh authorization |
| job-cancel | `jobs.draft.revision` | job; queued cancellation or active CANCEL_PENDING |

Runtime and draft revision numbers are separate concurrency namespaces inside the same actor/database. Read the correct revision immediately before the relevant command. The server does not silently retry a changed command. Replay a lost mutation using its exact original client ID, request ID, revision, and payload. A changed body under the same identity refuses. Job mutations go to the ordinary data endpoint; the reserved endpoint admits lifecycle controls and status only. Worker claim/finalize are in-process actor messages and are not public IPC commands.

Submission JSON example:

```json
{"goal":"Draft a review without executing anything","inputs":[],"authorization":{"operator":"descriptive caller label","scope":"DRAFT_ONLY"}}
```

Each input has exactly `name`, `text`, and `sha256` (SHA256 of exact UTF-8 text). Total source text is bounded at 10,000 characters across at most 32 items. Goal, question and answer limits remain inherited. The caller label is preserved in the request body; authorization rows bind to the authenticated profile user SID, not to that label. No file paths from payloads are opened on the server. Public source packages do not contain profiles, secrets, or user jobs.

## Atomic lifecycle and drafts

Startup validates supported schema, runtime history/receipts, draft history/receipts, provider ancestry, and cross-ledger active/paused consistency before recovery mutation. One actor connection writes all tables. No lab database, attached SQLite database, second writer thread, or worker-side writable connection is used. Nested repository savepoints participate in the actor's outer transaction.

Resume opens dispatch. A claim atomically creates one RUNNING attempt and records WORKING. Pause while active closes new claims and drains the current attempt; lifecycle stays WORKING until its outcome is committed, then becomes PAUSED. Stop commits STOPPING and closes new submissions/claims; an active attempt drains, and its outcome plus STOPPED commit together. An idle stop commits STOPPED directly. The default 600-second drain target reports STOP_TIMEOUT to stderr if reached and retains process/writer ownership until the lane actually exits. The test uses a shorter bounded deadline with a deliberately unresponsive fake adapter. No shared Ollama process is killed.

Output files are flushed and renamed before the artifact reference, terminal job state, draft receipt, and resulting lifecycle state commit atomically. A precommit crash may leave an orphan file, never a completion acknowledgement. Recovery preserves orphan evidence, interrupts RUNNING attempts, and pauses. Interrupted work requires explicit reauthorized retry; completed jobs do not rerun. A historical stop intent/receipt does not stop a later runtime generation.

Each attempt's generation resolves to an immutable provider record (none, fake, or configured Ollama model/digest). That records configuration, not atomic weight attestation or model truth. The loopback adapter checks the installed tag before and after each generation; it does not trust generated text as commands. Artifact reads verify bytes against the committed hash before returning text.

Cancellation is advisory for the worker call; durable cancellation governs whether a late result can count as completed. A cancelled active result remains cancelled-output. Stop/failure/timeouts do not prove shared-server computation stopped. All outputs remain unverified drafts. No shell, patch application, model installation, authority promotion, public posting, GUI migration, or arbitrary tool dispatch is exposed by this protocol.
