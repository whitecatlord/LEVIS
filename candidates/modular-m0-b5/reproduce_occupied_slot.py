"""Same occupied-slot control against the parent and new candidate."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from levis_modular.base import BaseRuntime, Room, ModuleSlot
from levis_modular.contracts import ModuleDeclaration
from levis_modular.supervisor import Supervisor
base = BaseRuntime((Room('r', 'test', (ModuleSlot('s'),)),))
supervisor = Supervisor(base)
declaration = ModuleDeclaration('module', '1', ())
class Module:
    def invoke(self, *args): return {}
first = supervisor.mount('r', 's', declaration, Module())
try:
    supervisor.mount('r', 's', declaration, Module())
except ValueError:
    assert base.rooms[0].slots[0].occupant_id == first
    print(json.dumps(dict(occupied_replacement='REFUSED', original_provider_preserved=True)))
    sys.exit(0)
print(json.dumps(dict(occupied_replacement='ACCEPTED', stale_provider_retained=first in supervisor._modules)))
sys.exit(1)
