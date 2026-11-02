"""In-process M0 controls; no OS isolation or Base adoption claim."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from levis_modular.base import BaseRuntime, ModuleSlot, Room
from levis_modular.contracts import CapabilityRequest, CapabilityUnavailable, ModuleDeclaration, ModuleOutput, UnavailableReason
from levis_modular.supervisor import Supervisor
from levis_modular.rooms import load_rooms, save_rooms, snapshot_rooms, restore_rooms


class Echo:
    def __init__(self): self.calls = 0
    def invoke(self, capability, payload, references):
        self.calls += 1
        return dict(payload)


class ModularTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseRuntime((Room('room', 'reference work', (ModuleSlot('slot', frozenset({'read'})),)),))
        self.supervisor = Supervisor(self.base)
        self.module = Echo()
        self.provider = self.supervisor.mount('room', 'slot', ModuleDeclaration('declared', '1', ('root',)), self.module)
        self.supervisor.approve_capability('read', self.provider, 'schema')
        self.lease = self.supervisor.grant_lease(self.provider, 'read')
        self.handle = self.supervisor.issue_work_order({'read'})

    def request(self, capability='read', schema='schema', handle=None):
        return CapabilityRequest(capability, schema, handle or self.handle, {'value': 1})

    def reason(self, request, reason):
        before = self.module.calls
        result = self.base.dispatch(request, self.supervisor)
        self.assertIsInstance(result, CapabilityUnavailable)
        self.assertEqual(result.reason, reason)
        self.assertEqual(before, self.module.calls)

    def test_zero_module_boot(self): self.assertEqual(BaseRuntime().rooms, ())

    def test_scoped_route_is_noncanonical(self):
        result = self.base.dispatch(self.request(), self.supervisor)
        self.assertIsInstance(result, ModuleOutput)
        self.assertEqual(result.response_class, 'NONCANONICAL_MODULE_OUTPUT')
        self.assertEqual(result.provider_id, self.provider)

    def test_unknown_work_order(self): self.reason(self.request(handle='forged'), UnavailableReason.WORK_ORDER_SCOPE)
    def test_out_of_scope(self): self.reason(self.request(capability='root'), UnavailableReason.WORK_ORDER_SCOPE)
    def test_schema_mismatch(self): self.reason(self.request(schema='other'), UnavailableReason.SCHEMA_MISMATCH)

    def test_declaration_is_not_grant(self):
        root_handle = self.supervisor.issue_work_order({'root'})
        self.reason(self.request(capability='root', handle=root_handle), UnavailableReason.NOT_APPROVED)
        self.assertNotEqual(self.provider, 'declared')

    def test_missing_provider(self):
        self.supervisor.unmount('room', 'slot')
        self.reason(self.request(), UnavailableReason.NO_PROVIDER)

    def test_revoked_lease(self):
        self.supervisor.revoke_lease(self.lease)
        self.reason(self.request(), UnavailableReason.NO_LIVE_LEASE)

    def test_unknown_provider_cannot_receive_lease(self):
        with self.assertRaises(ValueError): self.supervisor.grant_lease('forged', 'read')

    def test_occupied_slot_cannot_orphan_authorized_provider(self):
        with self.assertRaises(ValueError):
            self.supervisor.mount('room', 'slot', ModuleDeclaration('new', '1', ('read',)), Echo())
        self.assertEqual(self.base.rooms[0].slots[0].occupant_id, self.provider)

    def test_unmount_preserves_room_slot_and_invalidates_old_route(self):
        original = self.base.rooms[0]
        self.supervisor.unmount('room', 'slot')
        self.assertEqual((self.base.rooms[0].room_id, self.base.rooms[0].purpose), (original.room_id, original.purpose))
        self.assertIsNone(self.base.rooms[0].slots[0].occupant_id)
        self.reason(self.request(), UnavailableReason.NO_PROVIDER)

    def test_module_failure_is_typed(self):
        def fail(*args): raise RuntimeError('private details')
        self.module.invoke = fail
        result = self.base.dispatch(self.request(), self.supervisor)
        self.assertEqual(result.reason, UnavailableReason.MODULE_FAILED)
        self.assertEqual(result.detail, 'RuntimeError')

    def test_nonmapping_output_is_refused(self):
        self.module.invoke = lambda *args: 'canonical'
        self.assertEqual(self.base.dispatch(self.request(), self.supervisor).reason, UnavailableReason.MODULE_FAILED)

    def test_mapping_copy_failure_is_typed(self):
        from collections.abc import Mapping
        class Broken(Mapping):
            def __len__(self): return 1
            def __iter__(self): raise RuntimeError('cannot copy')
            def __getitem__(self, key): raise KeyError(key)
        self.module.invoke = lambda *args: Broken()
        self.assertEqual(self.base.dispatch(self.request(), self.supervisor).reason, UnavailableReason.MODULE_FAILED)

    def test_grant_shape_cannot_be_string_or_empty(self):
        for value in ('read', set(), {''}, {1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.supervisor.issue_work_order(value)

    def test_canonical_claim_remains_noncanonical_payload(self):
        self.module.invoke = lambda *args: dict(response_class='CANONICAL', provider_id='forged', root=True)
        result = self.base.dispatch(self.request(), self.supervisor)
        self.assertEqual(result.response_class, 'NONCANONICAL_MODULE_OUTPUT')
        self.assertEqual(result.provider_id, self.provider)
        self.assertFalse(hasattr(self.base, 'admit'))

    def test_delegation_cannot_expand_and_revocation_cascades(self):
        with self.assertRaises(ValueError): self.supervisor.derive_work_order(self.handle, {'root'})
        with self.assertRaises(ValueError): self.supervisor.derive_work_order('forged', {'read'})
        child = self.supervisor.derive_work_order(self.handle, {'read'})
        grandchild = self.supervisor.derive_work_order(child, {'read'})
        self.assertIsInstance(self.base.dispatch(self.request(handle=grandchild), self.supervisor), ModuleOutput)
        self.supervisor.revoke_work_order(self.handle)
        for handle in (self.handle, child, grandchild): self.reason(self.request(handle=handle), UnavailableReason.WORK_ORDER_SCOPE)

    def test_structure_restart_never_restores_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'rooms.json'; save_rooms(self.base, path)
            # A new interpreter restores the saved file, not live objects.
            code = 'from levis_modular.rooms import load_rooms; import sys; b=load_rooms(sys.argv[1]); print(b.rooms[0].room_id); print(b.rooms[0].slots[0].occupant_id)'
            process = subprocess.run([sys.executable, '-c', code, str(path)], capture_output=True, text=True, timeout=10, cwd=Path(__file__).parent)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout.splitlines(), ['room', 'None'])
            restored = load_rooms(path)
            self.assertEqual(restored.rooms[0].slots[0].required_capabilities, frozenset({'read'}))
            result = restored.dispatch(self.request(), Supervisor(restored))
            self.assertEqual(result.reason, UnavailableReason.WORK_ORDER_SCOPE)
            self.assertNotIn(self.handle.encode(), path.read_bytes())

    def test_malformed_or_authority_bearing_snapshot_refused(self):
        valid = json.loads(snapshot_rooms(self.base))
        occupied = json.loads(snapshot_rooms(self.base)); occupied['rooms'][0]['slots'][0]['occupant_id'] = self.provider
        duplicates = json.loads(snapshot_rooms(self.base)); duplicates['rooms'].append(duplicates['rooms'][0])
        for raw in (b'{}', b'{"version":1,"version":1,"rooms":[]}', b'x' * (1024*1024+1),
                    json.dumps(dict(valid, grants=[self.handle])).encode(), json.dumps(occupied).encode(),
                    json.dumps(duplicates).encode(), json.dumps(dict(valid, version=True)).encode()):
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError): restore_rooms(raw)

    def test_failed_snapshot_does_not_replace_saved_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'rooms.json'; save_rooms(self.base, path); before = path.read_bytes()
            invalid = BaseRuntime((Room('room', 'x'*4097),))
            with self.assertRaises(ValueError): save_rooms(invalid, path)
            self.assertEqual(path.read_bytes(), before)

    def test_base_import_boundary(self):
        tree = ast.parse((Path(__file__).parent/'levis_modular/base.py').read_text())
        imports = [(node.level, node.module) for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertEqual(imports, [(0, 'dataclasses'), (0, 'typing'), (1, 'contracts')])
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))


if __name__ == '__main__': unittest.main(verbosity=2)
