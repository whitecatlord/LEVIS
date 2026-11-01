# READ FIRST: geometry, compact communication, and context-loss tests

Date: 2026-11-01. Status: **DESIGN PROPOSAL / EXPERIMENTS PENDING**.

This engineering memo carries forward the design discussion titled “GitHub Geometry Encoding.” It is a technical synthesis, not a raw conversation export. The visible exchange was reviewed for this update. Private conversation logs, Drive contents, and device-security information are excluded.

## The proposal skimmers should check

**Preserve exact authorized source → record typed relationships → generate compact references and changes → test reconstruction after context loss.**

Optimize communication only while measuring whether another reader can recover the same relationships, evidence families, uncertainty, and authority boundaries. Shorter character counts alone do not establish better communication or lower model token use.

| Geometry term | Proposed recorded meaning |
| --- | --- |
| Node | Identified claim, artifact, or agent |
| Connection | Typed relationship between identified records |
| View | Scoped interpretation, with its assumptions |
| Basin | Related records under an explicitly defined theme |
| Boundary | Constraint or permission, with its source |
| Convergence | Agreement with shared origins tracked |
| Gap | Unknown or missing evidence |
| Change | New record linked to its predecessor |

Three models repeating one source remain one evidence family. Agreement does not create independent support. A view does not silently become a fact; a proposal does not grant execution authority.

## Candidate coordination format

Proposed layout, not implemented by this memo:

```text
coord/schema.md       versioned notation and decoding rules
coord/records.jsonl   structured records; authoritative within this proposed format
coord/index.json      generated lookup by ID, scope, and relation
coord/current.md      readable checkpoint generated from records
```

Candidate compact field order:

```text
id | type | scope | body | source | lineage | state
```

This field list is a design sketch, not a complete wire grammar. Define escaping, Unicode, null values, arrays, version negotiation, duplicate IDs, and invalid-input handling before using a delimiter codec. Prefer structured JSON records as the source of generated compact views. Preserve exact quotations separately from summaries, with authorization and publication review before any source text becomes public.

Illustrative structured record (all IDs and values are examples):

```json
{"id":"example-c1","type":"claim","scope":"example-only","body":"Startup should end PAUSED","source":["example-source-1"],"lineage":["example-family-1"],"state":"proposed"}
```

Source IDs must resolve to an exact artifact, commit, or permitted passage. A source register should preserve content hashes, attribution, access/publication scope, and unresolved references. Hashes establish content identity, not truth or permission. Missing source material remains an explicit gap. Corrections append a successor link and retain the earlier statement and contradiction; they must not rewrite the past invisibly.

## Context-loss reconstruction experiments

“Dementia basins” in the discussion is treated here as a name for context-loss reconstruction experiments. It is not a clinical claim, a demonstrated property, or a claim about consciousness.

| Experiment | Controlled change | What to measure |
| --- | --- | --- |
| Baseline | Give an independent reader the full permitted packet | Correct claims, typed relations, sources, boundaries, and unknowns |
| Context loss | Remove selected context while keeping the same questions | Reconstruction loss and unsupported additions |
| Paraphrase | Change wording while preserving intended relations | Meaning and relationship preservation |
| Decoy | Add irrelevant records and conflicting assertions | Source selection, contradiction retention, false acceptance |
| Correction | Append a correction linked to its predecessor | Current-state recovery without erasing lineage |
| Shared origin | Repeat one source through multiple model summaries | Avoidance of false source independence |

Freeze source hashes, prompts, model/version, input budgets, questions, scoring rubric, and expected answers before a run. Compare verbose structured records, compact views, and readable summaries on the same tasks. Report bytes, characters, model-specific tokens, retrieval accuracy, relation recovery, unsupported claims, and source/authority errors separately. Record failures and abstentions. Publish only approved test fixtures and redacted results; do not turn on public conversation logging by default.

## Evidence status and lineage

- Design source: two visible exchanges in “GitHub Geometry Encoding,” reviewed on 2026-11-01. This memo is derived engineering documentation; it is not an exact transcript or an independent audit of its cited Drive materials.
- The phone assistant reported finding 485 Drive items and reviewing 12 selected files. That claim has not been independently verified in this repository update.
- It reported a package named `LEVIS_Communication_Review_2026-11-01.zip` and **12 passing encoding checks**. The package and its test output were not retrieved here; no package hash or locally reproduced result is asserted.
- It explicitly described the basin experiments as **prepared, not executed**. Their outcomes remain unknown.
- Continuous conversation logging was not activated by that discussion or by this documentation update. GitHub does not automatically synchronize models or authorize autonomous execution.
- Runtime M1.1 remains **HOLD_FOR_REPAIR** under the existing structural review. This proposal does not close any engineering gate or alter an accepted component's scope.
- The October 31 release assets remain the historical snapshot. This November 1 memo is a subsequent repository documentation update.

## Bridge into the existing skeleton

Start with a bounded proposal using `BRIDGE_PROPOSAL_TEMPLATE.json`. Pin the parent artifact, specify the schema and source register, implement a deterministic view generator and decoder, and supply round-trip and malformed-input controls. Then run the context-loss experiments with independent readers. Admit implementation, verification, review, and acceptance separately through the engineering lineage process. Do not mark any level finished from this memo alone.

Acceptance must show preserved provenance, source independence, contradictions, and authority boundaries, with a measured communication tradeoff. “Most efficient” remains an open hypothesis until compared under a stated workload.
