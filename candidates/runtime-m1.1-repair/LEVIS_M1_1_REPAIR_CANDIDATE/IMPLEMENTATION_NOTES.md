# M1.1 implementation and evidence

Date: October 24, 2026. Candidate only. AUTHORITY_EFFECT: NONE.

## Custody and isolated scope

Source downloaded in `LEVIS_M0_1_DELIVERY.zip`. Its nested parent is `LEVIS_M0_1_CHAT_INPUT_INTEGRITY_CANDIDATE.zip`, SHA-256 `f9d785042c770492526db5fd4010846687586fd8fd4a9ff6a224d4ca9b4353a2`. Parent ZIP CRC and 58 manifest entries passed. All 59 parent files were extracted without modification and checked again before packaging. Original Downloads files, the installed desktop app, legacy databases, Base archives, model locks and provider bytes were not modified.

The design is copied verbatim as `DESIGN_PARENT.md`. The earlier Windows desktop shortcut targets `levis_desktop.py` in the October 22 workspace. All 54 files from its RC2 export match that workspace. The local installation therefore predates M0.1; its differences from the pinned M0.1 parent are the known chat-input repair/test changes, manifest, and M0.1 evidence additions. This is reconciled as an isolated candidate build from the specified parent, not an installation or migration onto the older app. No live database was opened by the new runtime.

## Implementation

Seven new runtime modules and one Windows test module implement the following:

- `runtime_ipc_windows.py`: small ctypes wrapper over Windows APIs, including process/effective client token verification, user and logon SID checks, elevation/AppContainer refusal, user-bound DPAPI, profile ACL checks, exclusive unshared writer handle, nonblocking deadline-bounded pipes and first-instance creation.
- `runtime_profile.py`: explicit nonexistent-profile initialization; protected user/SYSTEM folder DACL; inherited child ACL verification; refusal of reparse paths, network/removable drives, unknown files, missing/corrupt secret and identity mismatch. Discovery metadata carries no credential and is atomically published while ownership is held.
- `runtime_protocol.py`: strict bounded UTF-8 JSON, duplicate-key and unknown-field refusal, nonce challenges, role-bound HMAC-SHA256 proof, a derived connection key, direction/sequence/frame MAC checks before command decoding, and a 1 MiB frame ceiling. Handshakes are capped at 4 KiB; an operation has a 3-second pipe deadline.
- `runtime_store.py`: one writable SQLite connection on its owning actor thread, bounded queue, schema recognition, quick integrity check, WAL/FULL durability settings, 64 MiB main-store page quota, revision/event/control/receipt transactions, idempotency conflict checks and a fail-closed storage error gate. Original evidence is not evicted to recover space.
- `runtime_coordinator.py`: foreground explicit process, retained first-instance handles on separate data/control pipes, one bounded request per connection, independent control endpoint, PAUSED startup/recovery, explicit resume/pause/idle stop. No imports of the GUI, job engine, model, source acquisition or arbitrary command execution.
- `runtime_client.py` and `runtime_cli.py`: mutually authenticated observations/controls, attach/detach harness, explicit expected revision and recoverable request identity for uncertain control replies.

The pipe DACL grants the current logon SID individual client rights `0x12019b`, excluding FILE_CREATE_PIPE_INSTANCE. It does not grant a default Everyone or anonymous ACE. The kernel-read DACL was inspected in a native test. Both pipes reject remote clients at creation; peer token validation additionally requires the expected user and logon. Windows client process identity is checked before exchanging credentials; the server also checks the effective client token after reading the initial version frame.

The single pipe instance is retained and reused, avoiding a namespace gap or the need to grant clients server-instance creation rights. A separate reserved control endpoint remains available while a data client stalls. Acknowledged replies are consumed before disconnecting the server instance. A disconnect before acknowledgement does not undo a committed control.

The runtime publishes STARTING → RECOVERING → PAUSED during startup. Resume permits READY only. Idle stop commits STOPPING → STOPPED before replying, then closes endpoints/actor/lock and exits. Tests wait for the actual process exit as well as checking the clean marker. No active-work drain or cancellation is claimed because no executor exists.

## Executed evidence

The initial sandboxed connection probe received Windows access denied: this tool host uses an AppContainer token. No ACL grants were broadened as a workaround. Subsequent native smoke and acceptance tests were run through the approved normal-user execution path, with non-elevated tokens and disposable profiles. AppContainer execution is now explicitly refused by the adapter.

Final command: `python -m unittest discover -s outputs/LEVIS_M1_1_COORDINATOR_CANDIDATE/LEVIS_STARTER -p 'test_*.py' -v` from the build workspace. `LEVIS_TEST_PARENT` selected the workspace `work` directory for disposable profiles. Windows 11 10.0.26200, Python 3.12.10. Final result: 52 passed in 6.734 seconds. The full log is newly executed evidence; inherited evidence files retain their original attribution.

| Design check | Executed coverage | Limit |
|---|---|---|
| IPC01 | Real pipe handshake, bad secret, native mismatched-logon DACL denial, peer token user/logon mismatch refusal, private ACL and DPAPI use | No real second account, other interactive logon, or SMB remote host exercised |
| IPC02 | Native first-instance duplication refusal, squatted namespace refused before DB startup, stale PID refusal, deliberately false server proof over native pipe | No independent adversarial review |
| IPC03 | Authenticated invalid JSON/version/nesting, bad MAC/sequence, oversized frame, cross-connection replay and direction reflection refusal | Stress/load qualification and network-host attempts not performed |
| IPC04 | Mutation committed while reply unread; identical retry returns receipt once; different-body conflict; receipt survives restart without resuming new runtime | Lost stop reply may require restart to retrieve receipt |
| DB01 | Separate coordinator process and canonical path alias refused by exclusive OS lock; native duplicate pipe refusal | Separate Windows sessions not exercised |
| DB03 | Direct cross-thread use of actor connection refused by SQLite; unknown worker/finalization command and stale-generation extra field refused | Arbitrary same-user software opening a separate DB handle remains outside this application discipline |
| DB04 | Real SQLite writer-lock failure, actual COMMIT denial through test authorizer, SQLite page-quota exhaustion, corrupt database refusal | No physical disk-fill, failing drive or power-loss test |
| LIFE02 | Attach/detach/status preserve PAUSED and revision; no automatic dispatch; forged controls refused | No job submission implemented in M1.1 |
| idle LIFE04 | Idle stop journals STOPPED/clean marker; process exits; handles release | Active model cancellation intentionally absent |
| startup REC01 | Coordinator killed while READY; explicit restart recovers PAUSED with unclean reason and sequenced startup events | No attempt/output recovery exists before M1.2 |
| AUTH01 | No shell/set-state/lease/promotion/model-lock/chat/finalize route; unknown approval field refused | No governance integration or promotion |
| No executor/model | Runtime import census, reachable state/command set, isolated profile file census | Live talking GUI behavior was not exercised |

## Unresolved risks and qualification gaps

1. This is a review candidate, not completed Windows security qualification. Real alternate-user/logon/session and remote-host scenarios, independent IPC review, sustained contention/resource testing and deployment review remain. Native current-user tests and deliberately mismatched descriptors are not represented as those missing tests.
2. This first candidate binds profile identity to the creating Windows logon. A new logon/reboot requires a new isolated profile; the existing profile is refused rather than silently rekeyed or migrated. A reviewed logon-transition design is needed before useful production persistence.
3. Same-user malicious code, administrators, compromised Python and kernel attacks remain outside this boundary. A process-level writer lock and single actor do not stop arbitrary same-user code from bypassing the application.
4. Reparse checks assume trusted same-user profile storage. They do not establish resistance to an adversarial same-user filesystem race. Do not deploy profiles into shared/untrusted directories.
5. WAL/FULL and native process recovery do not establish power-loss durability. SQLite quota/authorizer failures are fault injections, not failing-hardware evidence. Event/request retention is bounded by a storage quota and fails closed; archival/rotation is future work. WAL/temporary filesystem usage needs sustained qualification.
6. The ctypes adapter is new code; Windows 11/Python 3.12.10 is the executed configuration. Other supported Windows/Python combinations have not been qualified. AppContainer and elevated tokens are explicitly unsupported.
7. No jobs, inference, library acquisition, migration, GUI attachment integration, active drain, backup/restore, login registration or service installation were added. Those remain later design slices. The legacy GUI continues to own its old data.

## Primary API references consulted

- [Microsoft: Named Pipe Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)
- [Microsoft: CreateNamedPipe](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createnamedpipea)
- [Microsoft: Named Pipe Type, Read, and Wait Modes](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-type-read-and-wait-modes)
- [Microsoft: GetNamedPipeServerProcessId](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid)
- [Microsoft: GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation)
- [Microsoft: CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)

These references informed implementation. They are not test evidence or an independent safety review.
