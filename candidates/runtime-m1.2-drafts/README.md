# LEVIS M1.2 — coordinator-owned durable drafts

**Candidate · 2026-11-02 · 78 tests pass on Windows; one explicitly inapplicable M1.1 assertion skipped.**

The Windows coordinator now owns durable draft jobs in its own `runtime.sqlite3`, through its one database actor. A worker lane performs inference outside database transactions and returns outcomes to that actor. Authenticated clients can submit, inspect, answer, retry, cancel, detach, and reconnect. A separate client process was exercised; the production Tkinter GUI has not yet been converted into an IPC client.

Start with [REVIEW.md](REVIEW.md), [the command contract](PROTOCOL.md), [qualification evidence](evidence/summary.json), and [ancestry](SOURCE_BASIS.json). This is a separate candidate, not an installation, implicit migration, accepted Base change, or independent certification.

## Run the synthetic demonstration

Windows, Python 3.12+, standard library:

```sh
python demo.py --output PATH_TO_NEW_OUTPUT_FOLDER --adapter fake
```

This creates a new private profile, submits a synthetic draft through authenticated native IPC, resumes, detaches and reattaches, verifies the committed artifact, and stops its coordinator. The fake adapter is explicitly labeled. The output directory must not exist.

For the already installed digest-matched local model:

```sh
python demo.py --output PATH_TO_ANOTHER_NEW_FOLDER --adapter ollama
```

Ollama must already be running on `127.0.0.1:11434` with the model/digest in MODEL_LOCK.json. No model is downloaded. The demo uses synthetic text only. Its actual-model smoke report is [preserved here](evidence/local_model_smoke.json); this checks connectivity, persistence, and provider attribution, not semantic accuracy.

## Start a persistent candidate process

```sh
python runtime_coordinator.py --profile PATH_TO_NEW_PROFILE --init --adapter ollama
```

On subsequent starts omit `--init`. Every restart is paused. Default `--adapter none` performs no inference; `--adapter fake` is for explicit tests. Profile kind `LEVIS-M1.2-draft-isolated`, metadata/schema version 3. Older profiles are refused and left in place. No production profile or desktop shortcut is replaced.

Use `runtime_cli.py --profile PROFILE jobs` and `status` to observe the candidate. Submit explicit JSON payloads with `--payload-file`, `--revision`, and optionally stable `--client-id` / `--request-id`; see PROTOCOL.md. Text in selected inputs is stored literally and never executed.

## Qualification

```sh
python qualify.py --output PATH_TO_NEW_QUALIFICATION_FOLDER
```

The Windows runner executes the integration, actual process-crash, typed-response, inherited native security/storage, and repair controls in disposable profiles. It records before/after source hashes and all results. This run: 79 methods scheduled, **78 pass, 1 explicit skip**, no failures. The skipped historical assertion forbids every WORKING state in M1.1; M1.2 instead tests authorized atomic claim/WORKING transitions. Its original function and the earlier failing run remain visible.

Do not point the candidate at a live legacy profile or combine its writer with another runtime. Chat migration, the GUI client, reference ownership, independent review, wider Windows/reboot/soak qualification, and exact-artifact acceptance remain open. Shared-model cancellation and exact external execution are not guaranteed. There is no code executor or autonomous public posting route.
