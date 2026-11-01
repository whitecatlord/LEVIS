"""Minimal Base-facing model: durable rooms, optional slots, typed routing."""
from dataclasses import dataclass
from typing import Protocol

from .contracts import CapabilityRequest, CapabilityUnavailable, ModuleOutput


@dataclass(frozen=True)
class ModuleSlot:
    slot_id: str
    required_capabilities: frozenset[str] = frozenset()
    occupant_id: str | None = None


@dataclass(frozen=True)
class Room:
    room_id: str
    purpose: str
    slots: tuple[ModuleSlot, ...] = ()

    def with_slot(self, slot: ModuleSlot) -> "Room":
        if any(current.slot_id == slot.slot_id for current in self.slots):
            raise ValueError(f"slot already exists: {slot.slot_id}")
        return Room(self.room_id, self.purpose, self.slots + (slot,))

    def with_occupant(self, slot_id: str, occupant_id: str | None) -> "Room":
        if not any(current.slot_id == slot_id for current in self.slots):
            raise KeyError(slot_id)
        slots = tuple(ModuleSlot(s.slot_id, s.required_capabilities, occupant_id if s.slot_id == slot_id else s.occupant_id) for s in self.slots)
        return Room(self.room_id, self.purpose, slots)


class CapabilityBoundary(Protocol):
    def invoke(self, request: CapabilityRequest) -> ModuleOutput | CapabilityUnavailable: ...


class BaseRuntime:
    """Keeps room identity and routes requests through an abstract boundary.

    No concrete module implementation is imported or instantiated here. Module
    outputs have no path into canonical state in this M0 surface.
    """

    def __init__(self, rooms: tuple[Room, ...] = ()):
        ids = [room.room_id for room in rooms]
        if len(ids) != len(set(ids)):
            raise ValueError("room IDs must be unique")
        self._rooms = {room.room_id: room for room in rooms}

    @property
    def rooms(self) -> tuple[Room, ...]:
        return tuple(self._rooms.values())

    def add_room(self, room: Room) -> None:
        if room.room_id in self._rooms:
            raise ValueError(f"room already exists: {room.room_id}")
        self._rooms[room.room_id] = room

    def dispatch(self, request: CapabilityRequest, boundary: CapabilityBoundary) -> ModuleOutput | CapabilityUnavailable:
        return boundary.invoke(request)

