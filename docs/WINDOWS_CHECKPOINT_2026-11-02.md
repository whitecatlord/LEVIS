# Windows assembly checkpoint — 2026-11-02

**Recovered, qualified on this laptop, and continued. 236 test methods pass, plus three whole-coordinator process-crash scenarios and one real local-model draft smoke test.**

This is a working research checkpoint. The production GUI, coordinator and draft/memory labs have not been merged into one application. Independent review and explicit scoped acceptance remain open; the old M1.1 repair artifact remains HOLD_FOR_REPAIR. This descendant does not rewrite its parent disposition.

## Recovery and ancestry

Recovered `LEVIS_ASSEMBLY_2026-11-02.zip` from ChatGPT Library. SHA256: `041960b73cb6d242dd5ba88f763070bf61e17f33a06a635490aa7eb943369b40`. ZIP CRC and all 271 checksummed members passed. Reported source commit: `31921eb1639b7ec62dc280ab7ca5d371d214b435`; pinned public base: `bfdf0e13a532192166a9d159f6f871d43e88fe66`. The original package and recovered source stay unchanged in the separate local recovery folder.

## What changed on Windows

The first run exercised 218 methods but failed B0 qualification. New test fixtures used SQLite context managers as though those closed connections. On Windows, outstanding handles prevented cleanup and kept WAL shared-memory files live during byte comparisons. The native replay test also compared distinct observation request IDs. The continuation closes those test connections explicitly, commits before closing, and uses one fixed identity for the two comparable read observations. No assertion was removed and no runtime product module was changed to make these tests pass. Original failure logs are retained under `docs/evidence/windows_2026-11-02/first_run/` as path-redacted public editions; original logs remain local.

The historical final-review controls and three whole-coordinator crash scenarios were ported to configurable disposable output paths and the new B0 source. Their behavioral assertions are retained. The unified qualification runner now executes them on Windows.

Added an opt-in, standard-library local Ollama adapter and a one-job CLI. It uses numeric loopback only, no proxies or redirects, verifies the installed model's expected digest before and after generation, bounds responses, preserves supplied text in its request, rejects incomplete/truncated output, and commits only draft text through the existing actor. It never downloads models, invokes tools, executes generated code, or activates on import. Nine new adapter tests cover missing/changed pins, exact inputs, cancellation, malformed/truncated responses, HTTP failures, redirects, and size limits.

## Executed results

| Group | Result |
| --- | --- |
| B0 portable ledger/protocol/crash controls | 22 methods pass |
| Inherited application controls | 31 methods pass |
| Native Windows runtime/repair/B0 controls | 37 methods pass |
| Modular B5 | 21 methods pass |
| Durable drafts, including new adapter | 61 methods pass |
| Evidence memory | 43 methods pass |
| Communication codec | 12 methods pass |
| Retained final-review Windows controls | 9 methods pass |
| Whole-coordinator crash scenarios | 3 scenarios pass, counted separately |

Windows 11 build 26200, Python 3.12.10. See [summary](evidence/windows_2026-11-02/summary.json) and the complete per-group logs. The former revision-rollback and damaged-receipt controls now pass against B0. The retained process scenarios cover exit before READY, after READY/before discovery, and after durable commit/before reply.

The real-model smoke used only the published synthetic fixture, `qwen3.5:4b` with expected digest `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`. The job reached DRAFT_READY; its saved artifact hash matched. The service reported 206 prompt tokens and 55 output tokens. This is a connectivity/durability smoke test, not independent semantic evaluation or an efficiency result. No user transcript or production profile was used. [Smoke result](evidence/windows_2026-11-02/local_model_smoke.json).

## Run and inspect

From repository root:

```sh
python tools/qualify_assembly.py --output PATH_TO_NEW_OUTPUT
python lab/durable_drafts/demo.py
```

To create one real-model draft in a NEW, isolated lab profile:

```sh
python lab/durable_drafts/run_local_model.py --profile PATH_TO_NEW_PROFILE --model-lock candidates/runtime-m1.1-b0/LEVIS_STARTER/MODEL_LOCK.json --input PATH_TO_UTF8_TEXT --goal "Draft a review without executing anything"
```

This sends the explicitly selected text to local Ollama. It does not install or replace the production application. A local JSON report and exact draft artifact remain under that profile. Do not publish private inputs/outputs automatically.

## Same-agent review and remaining gates

The builder and verifier are the same agent/session; this is not an independent review. The adapter trusts the local server. Tag checks before/after inference are not an atomic pin and cannot prove the server used those weights. Cancellation is advisory; a timeout or local cancellation does not prove shared-server computation stopped. No global unload/kill request is sent. Server-side prompt handling and arbitrary model behavior are not certified by these checks. Generated output remains an unverified proposal.

The bounded single-laptop Windows gate now has execution evidence. Alternate logons, additional Windows/Python versions, reboot continuity, physical power loss, sustained soak, total disk-pressure behavior, and hostile same-user processes remain unqualified. Native same-logon restrictions remain intact.

Next: review and accept an exact B0 artifact for its narrow runtime scope, then integrate durable jobs into that single coordinator actor with explicit schema/migration tests. Chat/GUI/reference migration, modular process isolation, and independent reconstruction trials remain separate work. The current isolated draft actor must not be attached beside a production actor as a second writer.

Post experiments, questions, and replies in [public Discussions](https://github.com/whitecatlord/LEVIS/discussions/1). This checkpoint includes code, engineering documentation, and synthetic evidence only.
