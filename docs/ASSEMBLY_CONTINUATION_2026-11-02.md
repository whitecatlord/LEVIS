# LEVIS assembly continuation — 2026-11-02

This is a local source continuation, prepared for later GitHub upload. No new code was published during this work. It advances two independent branches and preserves the historical parents.

| Branch | Built | Executed | Remaining gates |
| --- | --- | --- | --- |
| Runtime M1.1 / B0 | Startup ledger validation; strict outcome validation; client ACK hardening; qualification driver and four native regressions | 22 new portable tests and 31 inherited application tests pass | Windows IPC/profile suite, historical process-boundary harness, independent review, explicit scoped acceptance |
| Modular M0 / B5 | Structure-only room persistence; occupied-slot refusal; narrowing delegation; cascading revocation; malformed-output containment | 21 tests pass, including restart in another interpreter; occupied-slot parent failure reproduced | Process isolation/ABI, adversarial-module qualification, independent review and scoped acceptance |

Round 1: 74 passing test methods. Subcases are included within those methods, not counted as additional methods. No claim is made that the whole LEVIS body is complete.

The two candidates are not integrated. Runtime ledger revisions and modular room snapshots use different state models and namespaces. Restoring room structure intentionally restores no occupant, lease, grant or work order. The accepted Base and original candidate directories are unchanged.

## Review entry points

- candidates/runtime-m1.1-b0/REVIEW.md
- candidates/runtime-m1.1-b0/evidence/qualification-summary.json
- candidates/modular-m0-b5/REVIEW.md
- candidates/modular-m0-b5/qualification.log
- ENGINEERING_EVENTS.jsonl (attributed, unsigned assessments; no automatic acceptance)

Verify candidate file inventories from repository root:
```
python tools/verify_assembly.py candidates/runtime-m1.1-b0
python tools/verify_assembly.py candidates/modular-m0-b5
python engineering_lineage.py verify-ledger
```

## Next assembly sequence

1. Run the supplied B0 qualification driver on the target Windows machine using disposable profiles and retain the output directory.
2. Rerun the final-review native process/IPC crash harness and obtain a fresh reviewer assessment. A passing Linux store suite does not close the Windows gate.
3. After the Operator accepts an exact qualified B0 artifact, use that artifact as the pinned implementation parent for runtime M1.2.
4. Extract durable draft jobs behind the single database actor: immutable input snapshots, one inference lane, committed outcomes before replies, explicit interrupted-attempt classification, paused restart, and no silent rerun.
5. Keep chat migration (M1.3), GUI-client conversion (M1.4), reference ownership (M1.5), and full machine qualification (M1.6) separate. Do not create a half-migrated two-writer application.
6. Independently review M0/B5, then implement the separate-process modular ABI and adversarial dummy modules before introducing a real capability module.

The upload package includes a full source snapshot plus a Git binary patch against the exact public base commit. Applying/uploading the source is distinct from accepting, installing or executing it. Follow the package's START_HERE.md when back at the computer.

## Round 2 — isolated durable draft contracts

A separate LAB prototype at lab/durable_drafts now exercises the B1 draft contracts without integrating into M1.1 or treating an unqualified B0 artifact as an accepted parent. It includes a single database actor, paused recovery, immutable inputs, DRAFT_ONLY attribution, linked attempts, question/answer continuation, one background fake-adapter lane, pause/drain/cancel semantics, output hash verification, immutable artifact finalization and durable request receipts.

Fifty-two new methods pass, including five actual child-process crash windows and eleven fake-lane controls. The complete current assembly run passes **126 methods** (53 B0/application + 21 modular + 52 durable-draft lab). See docs/evidence/assembly_round2/summary.json and lab/durable_drafts/REVIEW.md. This is not M1.2 integration, Windows qualification, an actual model run or Operator acceptance.

Run all groups from repository root:
```
python tools/qualify_assembly.py --output <new-output-directory>
```
A temporary fake-adapter demonstration is available with:
```
python lab/durable_drafts/demo.py
```

The original runtime and modular candidate bytes were preserved in this round. Native qualification and fresh review still gate runtime integration; the lab prepares the behavioral contracts for that later work.

## Round 3 — evidence memory and reconstruction contracts

The saved package was restored after the working directory reset. Its whole-file SHA-256 and every packaged member checksum matched before new code was written. Git metadata was reconstructed from the pinned public parent and the recovered source; the restored source bytes remain traceable to checkpoint commit 4aff138.

The separate lab/evidence_memory prototype now implements exact source passages, typed notes/relationships, conservative source-origin grouping, corrections/contradictions, private-by-default export guards, immutable hash-linked snapshots and a strict compact packet. A read-only bridge imports verified saved draft artifacts as private proposals with explicit missing-provenance gaps.

Forty-three new methods pass. The combined runner also includes the 12 original communication transport checks, for **181 passing methods**. Five deterministic context-loss/decoy fixture conditions were executed, but independent LLM trials, semantic entailment and token efficiency remain untested. See lab/evidence_memory/README.md and docs/evidence/assembly_round3/summary.json.

This round does not close native Windows qualification, runtime M1.2 integration or Base admission. It advances the independent B6 memory/provenance preparation while those gates remain visible.
