# M0 acceptance map — implementation candidate, not yet qualified

| Blueprint condition | Current code location | Status |
|---|---|---|
| Zero-module boot | `levis_modular/base.py:BaseRuntime` default constructor | Implemented in candidate; not acceptance-tested |
| Room survives empty slot | `Room.with_occupant`, `Supervisor.unmount` | Implemented in candidate; no restart/durable-store test |
| Base does not import concrete module code | `base.py` imports only shared contracts | Static boundary is present; no automated import-ban check run |
| Typed unavailable response | `contracts.py:CapabilityUnavailable` and `UnavailableReason` | Implemented; no-provider demo path present |
| No output laundering | `ModuleOutput` is marked noncanonical; Base exposes no state-admission method | Surface is absent; integration with existing Base not built |
| No transitive authority growth | `Supervisor.invoke` requires work-order grant, approved catalog entry, matching schema, mounted provider, and live lease | In-process routing floor only; adversarial tests not run |
| Module declaration is not a grant | Supervisor assigns runtime provider IDs; declaration capabilities are not consulted for routing | Implemented in candidate; package identity measurement is M1 |

## Required next evidence

Before calling M0 accepted, write and run negative-control acceptance tests for
empty boot, slot/room persistence, missing provider, forged/unknown work-order
handle, out-of-scope capability, missing lease, schema mismatch, module error,
and module output that attempts to present itself as canonical. Then red-team
the isolation boundary. The current Python objects do not provide OS-grade
security, and this status table is implementation tracking rather than proof.
