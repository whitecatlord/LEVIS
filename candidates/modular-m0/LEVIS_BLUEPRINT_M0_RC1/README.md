# LEVIS Modular Blueprint — M0 implementation candidate

This package starts the **M0 boundary/truth-conditions slice** from the
September 12, 2026 *LEVIS Post-LLM Modular Capability Architecture — Reconciled
Red-Team Packet v0.2*. That packet labels itself a review candidate, not sealed
implementation authority. This package is therefore an isolated implementation
candidate; it does not replace or modify the accepted Base.

## Included in this slice

- `BaseRuntime` boots with zero modules, keeps stable Room identities, and
  preserves a ModuleSlot when its occupant is removed.
- Requests with no lawful route return the typed `CapabilityUnavailable`
  response and reason.
- Capability routing requires the intersection of a supervisor catalog entry,
  an opaque work-order grant, a mounted provider, and a live supervisor lease.
- A module declaration's claimed capabilities do not grant access.
- Module results are tagged `NONCANONICAL_MODULE_OUTPUT`; this package has no
  API that promotes module output into canonical Base state.
- Unmounting removes the provider's leases and empties the slot without deleting
  the Room.

## Deliberate limits

This is a small in-process boundary prototype. Opaque handles are unguessable
identifiers, but Python objects and process memory are not a security boundary.
The slice does not yet provide OS process isolation, measured package identity,
hard CPU/RAM/disk/network limits, signed work orders, expiring leases, draining,
crash recovery, durable state admission, independent assessors, or production
Base integration. It makes no safety qualification or acceptance claim.

The next blueprint stages remain M1 (process ABI/supervisor floor), M2
adversarial dummy modules, then M3 (a low-authority read-only module). Do not
skip M2 or treat this package as production-ready.

## Run the zero-module demonstration

From this directory:

```powershell
python -m levis_modular.demo
```

The demo prints the stable room inventory and a typed unavailable response.
No optional module is imported by `BaseRuntime`.

## Source basis

The exact blueprint and reconciled packet hashes are recorded in
`SOURCE_BASIS.json`. `ACCEPTANCE_STATUS.md` maps M0 requirements to code paths
and records that no acceptance tests have yet been run for this candidate.
