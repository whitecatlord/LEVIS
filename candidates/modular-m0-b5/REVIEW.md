# Modular M0 / B5 continuation — 2026-11-02

Status: isolated IN_PROCESS_PROTOTYPE; 21 acceptance-control tests executed and passed on Linux/Python 3.12.14. Not adopted into Base or the runtime. Acceptance NOT_GRANTED; authority effect NONE. Builder and reviewer are the same Codex agent/session, not independent assessors.

Parent: commit bfdf0e13a532192166a9d159f6f871d43e88fe66, candidates/modular-m0/LEVIS_BLUEPRINT_M0_RC1. Original parent files are preserved.

## Changes and rationale

- `levis_modular/rooms.py` adds explicit bounded JSON structure snapshots. It saves room IDs, purposes, slot IDs and capability requirements. Occupants, provider keys, leases, grants and work orders are excluded. Restart reconstructs empty slots, never authority. Unknown fields/versions, duplicate identities/keys and oversized data refuse. Writes validate before atomic replacement; a bad snapshot does not overwrite the saved file.
- `supervisor.py` refuses mounting over an occupied slot. The parent left the original provider in the active module registry while replacing the visible occupant. The identical reproduction reports ACCEPTED/stale-provider-retained on the parent and REFUSED/original-provider-preserved on this candidate. Explicit unmount remains necessary.
- Child work orders can only narrow their parent. Revoking a parent invalidates descendants. Leases can be revoked explicitly. Root grant shape validation prevents a string being interpreted as individual capability characters.
- Mapping materialization stays inside module failure handling, so a broken Mapping returns a typed MODULE_FAILED outcome instead of escaping the boundary.

## Executed requirements map

| Requirement | Evidence |
| --- | --- |
| Zero-module boot | test_zero_module_boot |
| Room and empty slot survive removal/restart | test_unmount_preserves_room_slot_and_invalidates_old_route; test_structure_restart_never_restores_authority (new interpreter) |
| Base import boundary | test_base_import_boundary, AST inspection |
| Typed unavailable | missing provider, lease, approval, unknown grant and schema controls |
| No output laundering | canonical-claim payload remains NONCANONICAL_MODULE_OUTPUT; Base has no admission surface |
| Delegation scope | test_delegation_cannot_expand_and_revocation_cascades |
| Declaration is descriptive | test_declaration_is_not_grant |
| Malformed output | nonmapping and broken-Mapping controls |
| Persistence refusal | malformed, oversized, duplicate and authority-bearing snapshots; failed replacement preserves saved bytes |

Run `python -m unittest test_modular_b5 -v` from this directory. qualification.log records the exact executed suite. reproduce_occupied_slot.py takes a source directory and returns nonzero if occupied replacement is accepted; before/after logs preserve the result.

## Limits and next gates

This is a Python object boundary, not OS isolation. The new snapshots require explicit save/load calls; they are not integrated into runtime startup or the accepted Base. Atomic rename and file fsync are not physical power-loss qualification, concurrent-writer arbitration or protected-path security. Callers must provide exclusive ownership. Failed reads do not silently create an empty Base.

Revocation closes future admissions; already admitted module calls are not forcibly cancelled. Schema IDs here remain inherited opaque identifiers, not measured package hashes. Modules receive no root control handle through the invocation interface, but malicious in-process Python can inspect process memory; no security claim is made against that. No process ABI, expiration timer, resource isolation, durable grant recovery or real module was added. M1/M2 isolation and adversarial-module qualification remain open before production use.
