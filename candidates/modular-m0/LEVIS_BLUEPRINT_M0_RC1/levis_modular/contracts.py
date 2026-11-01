"""Typed ABI contracts shared across the Base/Supervisor boundary."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class UnavailableReason(str, Enum):
    NO_PROVIDER = "NO_PROVIDER"
    EMPTY_SLOT = "EMPTY_SLOT"
    NOT_APPROVED = "NOT_APPROVED"
    NO_LIVE_LEASE = "NO_LIVE_LEASE"
    WORK_ORDER_SCOPE = "WORK_ORDER_SCOPE"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    MODULE_FAILED = "MODULE_FAILED"


@dataclass(frozen=True)
class CapabilityUnavailable:
    capability_id: str
    reason: UnavailableReason
    detail: str = ""
    response_class: str = field(default="CAPABILITY_UNAVAILABLE", init=False)


@dataclass(frozen=True)
class CapabilityRequest:
    """A request carries a handle, never caller-authored authority fields."""
    capability_id: str
    schema_hash: str
    work_order_handle: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    input_artifact_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModuleOutput:
    """An attributed observation. It is deliberately not a Base state record."""
    provider_id: str
    capability_id: str
    payload: Mapping[str, Any]
    output_artifact_refs: tuple[str, ...] = ()
    response_class: str = field(default="NONCANONICAL_MODULE_OUTPUT", init=False)


@dataclass(frozen=True)
class ModuleDeclaration:
    """Untrusted descriptive metadata supplied by a module package."""
    module_id: str
    version: str
    claimed_capabilities: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

