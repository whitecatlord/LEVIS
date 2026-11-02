"""Real Qt widgets/pixels and native coordinator integration, synthetic disposable data."""
import hashlib,json,os,socket,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from workbench import Workbench,ROOT
from scene import fixture,digest
from observation import MarkerAnalyzer
from scoped_files import ScopedFiles,CHUNK,MAX_FILE

APP=QApplication.instance() or QApplication([])
BASE=Path(os.environ.get('LEVIS_GUI_TEST_ROOT',str(ROOT.parent/'LEVIS_QT_TEST_PRIVATE'))).absolute();BASE.mkdir(parents=True,exist_ok=True)
def wait_until(predicate,seconds=12):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        APP.processEvents();QTest.qWait(15)
        if predicate():return
    raise AssertionError('Timed out waiting for GUI condition')

class GuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=BASE);self.root=Path(self.temp.name);self.w=Workbench(self.root/'ui');self.w.resize(1366,768);self.w.show();QTest.qWait(100);self.w.world.fit();APP.processEvents()
    def tearDown(self):self.w.close();APP.processEvents();self.temp.cleanup()
    def capture(self):
        self.w.observer.last_capture=0;fid=self.w.observer.capture_viewport();self.assertIsNotNone(fid);wait_until(lambda:not self.w.observer.busy);return self.w.observer.history[-1]
    def test_actual_canvas_capture_provenance_and_known_shape(self):
        self.w.world.data=dict(schema=1,source='KNOWN SHAPE TEST FIXTURE',nodes=[dict(id='known',x=500,y=400,radius=30,color='#3be6dd',shape='circle',basin=0)],edges=[],basins=[])
        self.w.world.render_scene();self.w.world.fit();APP.processEvents();r=self.capture()
        self.assertEqual(r['capture_status'],'CAPTURED');self.assertEqual(r['interpretation']['status'],'AVAILABLE');self.assertEqual(r['comparison']['expected'],1);self.assertEqual(r['comparison']['observed'],1);self.assertEqual(r['comparison']['shape_changes'],[])
        png=self.root/'ui/observations'/(r['frame_id']+'.png');self.assertEqual(hashlib.sha256(png.read_bytes()).hexdigest(),r['png_sha256']);image=QImage(str(png));self.assertEqual([image.width(),image.height()],r['pixel_size']);self.assertEqual(r['intended_scene']['source_sha256'],digest({k:v for k,v in r['intended_scene'].items() if k!='source_sha256'}))
        self.assertLess(image.width(),self.w.width());self.assertNotIn('confidence',r['interpretation'])
        self.w.world.faults={'known':'rectangle'};self.w.world.render_scene();APP.processEvents();changed=self.capture()
        self.assertEqual(changed['intended_scene']['source_sha256'],r['intended_scene']['source_sha256']);self.assertEqual(changed['comparison']['shape_changes'][0]['observed'],'rectangle');self.assertGreater(changed['pixel_delta']['changed_pixels'],0);self.assertEqual(changed['sequence'],r['sequence']+1)
    def test_missing_marker_detected_without_changing_expected_scene(self):
        r=self.capture();self.assertEqual(r['comparison']['missing'],[]);self.assertEqual(r['comparison']['unexpected'],[])
        self.w.world.faults={'0-0':'hidden'};self.w.world.render_scene();APP.processEvents();r2=self.capture();self.assertIn('0-0',r2['comparison']['missing'])
    def test_detached_and_failed_analysis_are_unavailable(self):
        self.w.observer.adapter=None;r=self.capture();self.assertEqual(r['interpretation']['status'],'UNAVAILABLE');self.assertIsNone(r['comparison']['missing']);self.assertTrue((self.root/'ui/observations'/(r['frame_id']+'.png')).exists())
        class Broken:
            name='deliberately-broken'
            def analyze(self,image):raise RuntimeError('synthetic analysis failure')
        self.w.observer.adapter=Broken();r=self.capture();self.assertIn('synthetic analysis failure',r['interpretation']['error']);self.assertEqual(r['comparison']['status'],'UNAVAILABLE')
    def test_observation_disable_and_backpressure(self):
        self.w.observer.enabled=False;self.assertIsNone(self.w.observer.capture_viewport());self.w.world.set_step(2);self.assertEqual(self.w.world.data['step'],2)
        self.w.observer.enabled=True;self.w.observer.last_capture=0;self.assertIsNotNone(self.w.observer.capture_viewport());self.assertIsNone(self.w.observer.capture_viewport());wait_until(lambda:not self.w.observer.busy)
    def test_history_and_layout_survive_reopen(self):
        r=self.capture();self.w.theme.setCurrentText('Light');self.w.obs_dock.hide();self.w.close();self.w=Workbench(self.root/'ui');self.w.show();APP.processEvents();self.assertEqual(self.w.observer.sequence,r['sequence']);self.assertEqual(self.w.observer.history[-1]['frame_id'],r['frame_id']);self.assertEqual(self.w.theme.currentText(),'Light');self.assertTrue(self.w.obs_dock.isHidden())
        newer=self.capture();self.assertGreater(newer['sequence'],r['sequence'])
    def test_long_logs_and_search_bounded(self):
        # Fill through the same retained-log filter without quadratic repeated painting.
        self.w.logs=[f'{i}: fixture event' for i in range(2500)];self.w.log('TEST','needle');self.assertEqual(len(self.w.logs),2000);self.w.search.setText('needle');self.assertIn('needle',self.w.console.toPlainText());self.assertNotIn('fixture event',self.w.console.toPlainText())
    def test_inspect_proposal_without_approval_and_no_source_overwrite(self):
        source=self.root/'source';source.mkdir();(source/'a.txt').write_text('original',encoding='utf-8');scope=ScopedFiles(source);self.w.catalogs['Workspace']['scope']=scope;self.w.catalogs['Workspace']['read']=scope.read('a.txt');self.w.draft_editor.setPlainText('proposed replacement');self.w.save_draft();wait_until(lambda:bool(self.w.proposals));self.w.proposal_list.setCurrentRow(0);self.assertIn('proposed replacement',self.w.proposal_detail.toPlainText());self.assertFalse((self.root/'ui/review-decisions.jsonl').exists());self.assertEqual((source/'a.txt').read_text(),'original');self.assertEqual(self.w.proposals[0]['approval'],'NOT_GRANTED')
        self.w.close();self.w=Workbench(self.root/'ui');self.assertEqual(len(self.w.proposals),1);self.assertEqual(self.w.proposals[0]['review'],'PENDING_REVIEW')
    def test_local_only_frontend_operations(self):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Network access forbidden')):
            self.capture();self.w.world.set_step(1);self.w.nav.setCurrentRow(8);self.assertIsNone(self.w.client)
    def test_responsive_sizes_and_saved_screenshots(self):
        measurements=[]
        for width,height in [(1366,768),(1920,1080)]:
            self.w.reset_layout();self.w.resize(width,height);QTest.qWait(150);APP.processEvents();self.w.world.fit();self.capture();QTest.qWait(50)
            self.assertGreaterEqual(self.w.world.viewport().width(),320);self.assertGreaterEqual(self.w.world.viewport().height(),230)
            self.assertGreaterEqual(self.w.obs_dock.width(),300)
            self.assertTrue(self.w.grab().save(str(BASE/f'workbench-{width}x{height}.png')))
            measurements.append(dict(requested_logical=[width,height],actual_logical=[self.w.width(),self.w.height()],device_pixel_ratio=self.w.devicePixelRatioF(),captured_pixels=[self.w.grab().width(),self.w.grab().height()],viewport_logical=[self.w.world.viewport().width(),self.w.world.viewport().height()]))
        (BASE/'display-measurements.json').write_text(json.dumps(measurements,indent=2),encoding='utf-8')

class FileTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory(dir=BASE);self.root=Path(self.temp.name);self.scope=ScopedFiles(self.root)
    def tearDown(self):self.temp.cleanup()
    def test_scope_traversal_and_ads_refused(self):
        for p in ['../outside','C:/Windows/win.ini','a.txt:stream']:
            with self.assertRaises(ValueError):self.scope.read(p)
    def test_sparse_five_gib_streaming_without_loading_whole_file(self):
        # seek/truncate sparse logical fixture; Windows allocation is bounded below.
        p=self.root/'large.bin'
        with p.open('wb') as f:
            if os.name=='nt':
                import ctypes,msvcrt
                returned=ctypes.c_ulong();handle=msvcrt.get_osfhandle(f.fileno())
                ok=ctypes.windll.kernel32.DeviceIoControl(ctypes.c_void_p(handle),0x900c4,None,0,None,0,ctypes.byref(returned),None)
                self.assertTrue(ok,'Sparse fixture setup failed')
            f.seek(MAX_FILE-4);f.write(b'tail')
        r=self.scope.read('large.bin',MAX_FILE-4);self.assertEqual(r['text'],'tail');self.assertEqual(r['size'],MAX_FILE)
        with p.open('ab') as f:f.write(b'x')
        with self.assertRaises(ValueError):self.scope.read('large.bin')
    def test_catalog_pages_are_bounded(self):
        for i in range(305):(self.root/f'file{i:04}.txt').write_text('fixture')
        page=self.scope.page();self.assertEqual(len(page['rows']),100);self.assertTrue(page['has_more']);second=self.scope.page(page['next_offset']);self.assertTrue({r['name'] for r in page['rows']}.isdisjoint({r['name'] for r in second['rows']}))
    def test_linked_scope_refused(self):
        # Windows junction requires no developer-mode symlink privilege.
        outside=self.root/'outside';outside.mkdir();linked=self.root/'linked'
        if os.name=='nt':
            subprocess.run(['cmd','/c','mklink','/J',str(linked),str(outside)],check=True,capture_output=True)
        else:linked.symlink_to(outside,target_is_directory=True)
        try:
            with self.assertRaises(ValueError):ScopedFiles(linked)
            with self.assertRaises(ValueError):self.scope.resolve('linked')
        finally:
            if os.name=='nt':os.rmdir(linked)
            else:linked.unlink()

@unittest.skipUnless(os.name=='nt','Native coordinator requires Windows')
class NativeIntegration(unittest.TestCase):
    def test_gui_close_reopen_preserves_running_durable_job_and_paused_start(self):
        sys.path.insert(0,str(ROOT/'runtime'));from runtime_client import Client
        with tempfile.TemporaryDirectory(dir=BASE) as td:
            root=Path(td);profile=root/'profile';process=subprocess.Popen([sys.executable,str(ROOT/'runtime/runtime_coordinator.py'),'--profile',str(profile),'--init','--adapter','fake','--fake-delay','2'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            w=None
            try:
                wait_until(lambda:(profile/'discovery.json').exists());client=Client(profile,'qt-native-test');self.assertEqual(client.request('status')['state'],'PAUSED')
                w=Workbench(root/'ui',profile);w.show();wait_until(lambda:w.client is not None and not w.pending);self.assertEqual(w.status['state'],'PAUSED')
                w.authorize.setChecked(True);w.goal.setPlainText('Synthetic durable GUI continuity draft');w.submit();wait_until(lambda:not w.pending and client.request('jobs')['draft']['job_count']==1)
                w.control('resume');wait_until(lambda:not w.pending and client.request('status')['state']=='WORKING')
                w.observer.enabled=False;w.close();w=None;self.assertIsNone(process.poll())
                wait_until(lambda:client.request('jobs')['draft']['jobs'][0]['completed']);w=Workbench(root/'ui',profile);w.show();wait_until(lambda:w.jobs is not None and not w.pending);self.assertTrue(w.jobs['jobs'][0]['completed']);self.assertEqual(w.status['state'],'READY')
                self.assertFalse((root/'ui/runtime.sqlite3').exists());w.job_table.selectRow(0);w.inspect_job();wait_until(lambda:not w.pending);self.assertIn('integrity',w.job_detail.toPlainText())
                client.request('pause',client.request('status')['revision'])
                from runtime_client import UnconfirmedRequest
                actual=w.client
                class LoseReply:
                    profile=actual.profile
                    client_id=actual.client_id
                    def request(self,command,revision=None,payload=None,request_id=None,**kw):
                        reply=actual.request(command,revision,payload,request_id,**kw)
                        if command=='job-submit':raise UnconfirmedRequest(dict(protocol_version=1,client_id=self.client_id,request_id=request_id,expected_revision=revision,command=command,payload=payload))
                        return reply
                w.client=LoseReply();w.mutate('job-submit',dict(goal='Synthetic lost reply draft',inputs=[],authorization=dict(operator='GUI fixture',scope='DRAFT_ONLY')));wait_until(lambda:not w.pending)
                self.assertEqual(client.request('jobs')['draft']['job_count'],2);self.assertTrue((root/'ui/unconfirmed.json').exists());w.client=actual
                w.replay_request();wait_until(lambda:not w.pending);self.assertEqual(client.request('jobs')['draft']['job_count'],2);self.assertIn('EXACT REPLAY RECEIPT',w.chat_history.toPlainText())
                saved=json.loads((root/'ui/unconfirmed.json').read_text());saved['profile_sha256']='0'*64;(root/'ui/unconfirmed.json').write_text(json.dumps(saved));w.replay_request();wait_until(lambda:not w.pending);self.assertIn('different profile',w.console.toPlainText());self.assertEqual(client.request('jobs')['draft']['job_count'],2)
            finally:
                if w:w.close()
                if process.poll() is None:
                    try:client.request('stop',client.request('status')['revision']);process.communicate(timeout=12)
                    except Exception:process.kill();process.communicate()

if __name__=='__main__':unittest.main(verbosity=2)
