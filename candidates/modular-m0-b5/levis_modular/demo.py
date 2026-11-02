"""Zero-module boot demonstration; no module code is loaded."""
from .base import BaseRuntime, ModuleSlot, Room
from .contracts import CapabilityRequest
from .supervisor import Supervisor


def main() -> None:
    base = BaseRuntime((Room("engineering", "bounded engineering work", (ModuleSlot("code-intelligence"),)),))
    supervisor = Supervisor(base)
    supervisor.approve_capability("code.inspect", "code-intelligence-provider", "schema-v1")
    work_order = supervisor.issue_work_order({"code.inspect"})
    print("rooms:", [(room.room_id, [(slot.slot_id, slot.occupant_id) for slot in room.slots]) for room in base.rooms])
    result = base.dispatch(CapabilityRequest("code.inspect", "schema-v1", work_order), supervisor)
    print("response:", result)


if __name__ == "__main__":
    main()
