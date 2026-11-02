# Evidence memory bridge — LAB

2026-11-02. Status: ISOLATED_PROTOTYPE / 43_TESTS_PASS_ON_LINUX. Acceptance NOT_GRANTED. Authority effect NONE. No runtime, Base or model integration is adopted.

This implements a bounded part of the existing communication-geometry proposal: **exact source → typed records → compact packet → explicit reconstruction checks**. It also supplies a read-only lab bridge from a committed draft artifact into proposal memory.

## Working interfaces

- `source(...)` records exact UTF-8 text/hash, declared origin, parent sources, declared license (UNKNOWN unless supplied) and explicit publication/export fields. A declared origin or license is not independently verified.
- `note(...)` records claim/view/gap/boundary, scope, exact source citations, epistemic label and typed contradicts/supersedes/depends_on links. All notes retain authority NONE. SOURCE_STATEMENT requires a resolvable citation; matching quotation bytes do not prove semantic entailment or truth.
- `Memory.add` validates references to previously recorded nodes, exact quotation offsets/hashes and duplicate IDs. Source ancestry and dependency records cannot form forward cycles. Constructor input and returned data cannot mutate stored records.
- `view(scope)` keeps contradictions visible from both sides and shows successors without deleting the old statement. Neither majority agreement nor a successor becomes a truth verdict.
- `provenance(id)` follows source ancestry. Repeated summaries share their root. Equal text hashes or a declared common origin conservatively merge groups. Separate groups remain UNVERIFIED independence; the code does not certify independent corroboration.
- `select(ids)` includes source ancestors, referenced notes, incoming contradictions/corrections and associated gap records. It does not silently omit inconvenient counterevidence to make a public export succeed.
- `packet(public=True)` requires every selected node to be explicitly PUBLIC and export_allowed=true. Private is the constructor default. This is a trusted-caller serialization guard, not authentication, legal clearance, an ACL or a publishing service.
- `from_packet` verifies version, exact dictionary, row shapes, whole-content hash and the reconstructed reference graph. Positional compact records are versioned; this is not an implicit change to the existing levis-char/0.1 codec.
- `save(new_path)` writes a new exclusive, fsynced, hash-linked JSONL snapshot. `load(path, expected_sha256=...)` can check a separately retained file identity. No shared concurrent append writer or production database was introduced.

## Reconstruction and omissions

`reconstruction(nodes, expected_ids)` reports missing references, missing inventory entries, unexpected decoys and unverified quotations. Without an expected inventory, all present references can resolve even though an unreferenced contradiction was deleted. In that case completeness is UNKNOWN (`null`), not a fabricated success. Truth remains NOT_ADJUDICATED even with a complete inventory.

The inventory is itself a supplied assertion, not an authenticated external anchor. A whole internally consistent old snapshot or complete-line log truncation is not detectable without a separately retained identity. The tests demonstrate that limit and refusal when an expected file hash is supplied.

## Draft bridge

`import_verified_draft(memory, store, job_id)` uses only the supplied store's observation API. It requires a committed DRAFT_READY job and a currently hash-valid draft artifact, then returns a new memory snapshot containing:

1. Exact output as a private source.
2. A private PROPOSAL view, authority NONE.
3. An explicit gap: original input bindings, model identity and authorization records are not exposed by that observation API.

Output claiming “APPROVED ROOT” stays quoted data. Cancelled late output, corrupt files, queued work and missing jobs refuse import. Identical imports are idempotent. The bridge does not mutate the draft store, run output, infer model identity or invent original-input parent links.

## Run

From this directory:
```
python -m unittest discover -p "test_*.py" -v
python experiment.py --output <new-output-directory>
```
The executed evidence is in evidence/. All fixtures are synthetic and explicitly marked for export. No personal chats, Drive text or outside source content were copied into the fixtures.

The deterministic fixture run covers full context, a missing root source, an omitted counterproposal, an omitted correction and an added decoy. It verifies exact packet round-trip and the expected omissions. **Independent LLM/context-loss trials remain NOT_RUN.** No clinical result, consciousness claim, source-entailment score or model-token saving is asserted.

For this nine-node fixture, full canonical JSON is 2,967 bytes and the compact packet is 2,474 bytes, including its 215-byte dictionary. This is a fixture byte measurement only; token counts, larger workloads and semantic reconstruction quality remain unmeasured.

## Next integration gates

The complete assembly runner now executes 181 methods: 53 B0/application, 21 modular, 52 durable-draft lab, 43 evidence-memory and 12 inherited communication transport checks. Windows qualification is still pending. The memory and draft prototypes remain separate from the accepted Base and Windows coordinator.

Before real use: review exact source provenance/license assertions, agree admission rules and retention, qualify independent-reader trials with preregistered tasks/settings, reconcile target schemas and obtain scoped acceptance. Missing evidence must stay missing; this format does not create authority.
