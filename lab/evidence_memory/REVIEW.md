# Evidence-memory review — 2026-11-02

Builder and reviewer: same Codex agent/session. This is a bounded same-agent source review and executed fixture evidence, not independent certification or acceptance.

## Executed results

- 37 memory/transport/graph tests and six tests using the real durable-draft actor: 43 PASS.
- Five deterministic fixture conditions: expected missing/unexpected IDs verified; exact full/compact reconstruction verified.
- Full combined run: 181 PASS on Linux/Python 3.12.14. The 12 inherited communication checks were added to the combined runner; they are not newly written tests.
- Existing runtime, modular and durable-draft candidate bytes remain unchanged from the verified saved checkpoint.

## Review findings addressed

1. A naive recursive root walk would repeat work exponentially on a shared-ancestor DAG. Root traversal now visits each source once per query; the regression uses 30 layers of shared parents.
2. A one-shot iterator could be consumed by selection validation. Selection now copies the identities once before validation and closure.
3. Reference closure alone could certify a partial context after an unreferenced counterproposal was dropped. Reconstruction now distinguishes reference completeness from externally supplied inventory completeness. No inventory means unknown overall completeness when all present references resolve.
4. Known gap records could be lost while selecting only a proposal. Selection closure now keeps associated incoming gap dependencies, as well as contradictions and successors.
5. Draft output could otherwise appear to have known original-input/model provenance. The bridge explicitly records that missing provenance as a gap and leaves imported source parents empty. All imports remain private PROPOSAL records.
6. A valid prefix of an unsigned hash-linked JSONL file is still a valid prefix. The loader accepts an optional expected whole-file hash to detect truncation against a retained identity; tests preserve both the limitation and the bounded refusal.

## Source obligations checked

Schemas reject unknown fields, versions, dictionaries, row lengths, duplicate IDs/keys, invalid offsets, source hash mismatches, missing source/relationship targets, cycles/forward references and authority upgrades. Exact UTF-8 codepoint offsets preserve composed/decomposed Unicode without normalization. Compact import reconstructs and validates full records before use.

Publication defaults are private. Selected private dependencies or counterevidence prevent a public packet; the engine does not remove them silently. This does not establish that a caller's export authorization or license assertion is genuine. No connector publishes these records.

The draft bridge reads paginated observations, verifies the current artifact digest against committed metadata and creates a separate memory snapshot. It does not write into the actor's database or call an executor. A corrupt result remains unavailable; a successful local draft remains a proposal rather than an accepted fact.

## Residuals

No independent model trial, semantic-entailment test, provider identity verification, actual source acquisition, authenticated consent system, production migration or Base admission was performed. Hashes are identities/integrity checks, not signatures or truth proofs. Root grouping is conservative declared provenance, not verified independence.

The 256-node / 8 MiB packet limits bound this lab; larger-workload performance, concurrent persistent writing and production indexing remain unqualified. Immutable snapshots require exclusive new filenames and a separately retained identity for rollback detection. The design is not a replacement for a production single-writer ledger.

Rollback: discard this isolated lab and generated fixture snapshots. Existing accepted/historical artifacts are preserved. Keep model reconstruction experiments labeled NOT_RUN until actually executed with recorded model/version/settings and raw outcomes.
