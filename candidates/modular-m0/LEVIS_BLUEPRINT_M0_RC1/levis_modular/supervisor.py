"""Small deterministic router enforcing the M0 capability intersection."""
from dataclasses import dataclass
import secrets
import threading
from typing import Any, Mapping, Protocol

from .base import BaseRuntime
from .contracts import CapabilityRequest, CapabilityUnavailable, ModuleDeclaration, ModuleOutput, UnavailableReason


class Module(Protocol):
    def invoke(self, capability_id: str, payload: Mapping[str, Any], input_artifact_refs: tuple[str, ...]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class _Approval:
    provider_id: str
    schema_hash: str


@dataclass(frozen=True)
class _Lease:
    lease_id: str
    provider_id: str
    capability_id: str


class Supervisor:
    """In-process M0 harness for catalog, opaque work orders, and routing.

    OS process isolation, protected handles, hard resource limits, package
    measurement, and live lease expiry belong to later milestones and are not
    claimed by this prototype.
    """

    def __init__(self, base: BaseRuntime):
        self._base = base
        self._catalog: dict[str, _Approval] = {}
        self._modules: dict[str, tuple[ModuleDeclaration, Module]] = {}
        self._leases: dict[str, _Lease] = {}
        self._work_orders: dict[str, frozenset[str]] = {}
        self._lock = threading.RLock()

    def approve_capability(self, capability_id: str, provider_id: str, schema_hash: str) -> None:
        if not capability_id or not provider_id or not schema_hash:
            raise ValueError("catalog entries require capability, provider, and schema IDs")
        with self._lock:
            self._catalog[capability_id] = _Approval(provider_id, schema_hash)

    def mount(self, room_id: str, slot_id: str, declaration: ModuleDeclaration, module: Module) -> str:
        with self._lock:
            room = next((r for r in self._base.rooms if r.room_id == room_id), None)
            if room is None:
                raise KeyError(f"unknown room: {room_id}")
            if not any(s.slot_id == slot_id for s in room.slots):
                raise KeyError(f"unknown slot: {slot_id}")
            # The runtime key is supervisor-assigned. A module's declared ID is
            # retained as descriptive metadata and cannot select its own grant.
            provider_id = secrets.token_hex(16)
            self._modules[provider_id] = (declaration, module)
            self._base._rooms[room_id] = room.with_occupant(slot_id, provider_id)
            return provider_id

    def unmount(self, room_id: str, slot_id: str) -> None:
        with self._lock:
            room = next((r for r in self._base.rooms if r.room_id == room_id), None)
            if room is None:
                raise KeyError(f"unknown room: {room_id}")
            slot = next((s for s in room.slots if s.slot_id == slot_id), None)
            if slot is None:
                raise KeyError(f"unknown slot: {slot_id}")
            if slot.occupant_id:
                self._modules.pop(slot.occupant_id, None)
                for lease_id, lease in tuple(self._leases.items()):
                    if lease.provider_id == slot.occupant_id:
                        self._leases.pop(lease_id, None)
            self._base._rooms[room_id] = room.with_occupant(slot_id, None)

    def grant_lease(self, provider_id: str, capability_id: str) -> str:
        with self._lock:
            if provider_id not in self._modules:
                raise ValueError("lease target is not mounted")
            approval = self._catalog.get(capability_id)
            if approval is None or approval.provider_id != provider_id:
                raise ValueError("provider is not approved for this capability")
            lease_id = secrets.token_urlsafe(24)
            self._leases[lease_id] = _Lease(lease_id, provider_id, capability_id)
            return lease_id

    def issue_work_order(self, capability_ids: set[str] | frozenset[str]) -> str:
        """Create a root grant through the supervisor control surface."""
        if not capability_ids:
            raise ValueError("work order must grant at least one capability")
        handle = secrets.token_urlsafe(32)
        with self._lock:
            self._work_orders[handle] = frozenset(capability_ids)
        return handle

    def invoke(self, request: CapabilityRequest) -> ModuleOutput | CapabilityUnavailable:
        with self._lock:
            grant = self._work_orders.get(request.work_order_handle)
            if grant is None or request.capability_id not in grant:
                return CapabilityUnavailable(request.capability_id, UnavailableReason.WORK_ORDER_SCOPE)
            approval = self._catalog.get(request.capability_id)
            if approval is None:
                return CapabilityUnavailable(request.capability_id, UnavailableReason.NOT_APPROVED)
            if request.schema_hash != approval.schema_hash:
                return CapabilityUnavailable(request.capability_id, UnavailableReason.SCHEMA_MISMATCH)
            provider_id = approval.provider_id
            mounted = self._modules.get(provider_id)
            if mounted is None:
                return CapabilityUnavailable(request.capability_id, UnavailableReason.NO_PROVIDER)
            declaration, module = mounted
            lease = next((l for l in self._leases.values() if l.provider_id == provider_id and l.capability_id == request.capability_id), None)
            if lease is None:
                return CapabilityUnavailable(request.capability_id, UnavailableReason.NO_LIVE_LEASE)
            # The module's claimed capabilities are descriptive; the measured
            # catalog + work-order + live lease determine the route.
        try:
            payload = module.invoke(request.capability_id, request.payload, request.input_artifact_refs)
            if not isinstance(payload, Mapping):
                raise TypeError("module response payload must be a mapping")
        except Exception as exc:
            return CapabilityUnavailable(request.capability_id, UnavailableReason.MODULE_FAILED, type(exc).__name__)
        return ModuleOutput(provider_id, request.capability_id, dict(payload))

