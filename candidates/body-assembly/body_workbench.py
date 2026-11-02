"""Integrated observational workbench; runtime stays in a separate process."""
import argparse,json,sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication,QHBoxLayout,QListWidget,QLabel,QFileDialog
from workbench import Workbench,panel,label,button,textview,show_json
from body_memory import BodyMemory
from body_projection import BodyModules,project

class BodyWorkbench(Workbench):
    def __init__(self,data,profile=None):
        # Obtain memory ownership before opening a second UI against this root.
        self.body_memory=BodyMemory(Path(data)/'observational-memory')
        try:super().__init__(data,profile)
        except BaseException:self.body_memory.close();raise
        self.modules=BodyModules(self.body_memory);self.last_runtime=None;self.last_jobs=None
        self.setWindowTitle('LEVIS / BODY — integrated observational assembly')
        self.replay.currentIndexChanged.disconnect();self.replay.clear();self.replay.addItems(['Assembly observations','Fixture / baseline','Fixture / movement']);self.replay.currentIndexChanged.connect(self.world_mode)
        for widget in self.pages.widget(1).findChildren(QLabel):
            if widget.text()=='TEST FIXTURE • READ-ONLY LENS':widget.setText('ASSEMBLY STATE • PASSIVE PROJECTION')
        self.runtime_observed.connect(self.runtime_changed)
        page,l=panel();l.addWidget(label('MEMORY / COMPONENT CONNECTIONS','pageTitle'))
        l.addWidget(label('Private observational memory. Source text, model proposals and missing provenance stay distinct. No canonical Base admission or automatic public export.'))
        row=QHBoxLayout();row.addWidget(button('Remember selected source chunk',self.remember_chunk));row.addWidget(button('Remember selected completed job',self.remember_job));l.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('Inspect mounted module',self.inspect_module));row.addWidget(button('Save private transfer packet',self.export_memory));row.addWidget(button('Refresh memory',self.refresh_memory));l.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('Remember latest canvas observation',self.remember_observation));row.addWidget(button('Use selected record as draft context',self.use_memory_context));l.addLayout(row)
        l.addWidget(button('Import a selected closed legacy chat database…',self.choose_legacy))
        self.memory_status=label('');l.addWidget(self.memory_status);self.memory_list=QListWidget();self.memory_list.currentRowChanged.connect(self.inspect_memory);l.addWidget(self.memory_list);self.memory_detail=textview();l.addWidget(self.memory_detail,1);self.pages.addWidget(page);self.nav.addItem('Memory / Components')
        self.overview.setPlainText('INTEGRATED OBSERVATIONAL ASSEMBLY\n\nCoordinator → authenticated IPC → jobs → hash-checked draft → explicit private evidence memory → communication packet → passive world → actual viewport capture.\n\nThe local modular router mounts one read-only memory inspection provider with catalog, lease and work-order checks. It is an in-process prototype, not an OS sandbox.\n\nStart/reopen with assemble.py. Fresh runtime starts PAUSED; select Jobs → Resume dispatch only when ready. Closing this GUI preserves the runtime.\n\nOperator accepted the previous workbench’s demonstrated scope and authorized this assembly. New integration qualification is separate. Base promotion and unimplemented milestones are not implied.')
        self.diagnostics.appendPlainText('\nASSEMBLED CONNECTIONS\nPrivate immutable evidence-memory snapshots with one GUI writer lock. This is an observational sidecar, not a second runtime database actor.\nRuntime-backed scene is a paged projection, not canonical Base geometry. Nodes retain record identity and snapshot revision.\nThe communication codec wraps an exact memory packet; round-trip is checked. No compression/token or semantic-reconstruction gain is claimed.\nModule routing is an in-process prototype. No arbitrary modules, shell or source patch application is exposed.')
        self.statusBar().showMessage('ASSEMBLY PROJECTION | Private observational memory | Runtime separate | No Base promotion')
        self.refresh_memory();self.log('ASSEMBLY','Body components connected; source imports and draft-memory admissions require Operator actions')
    def runtime_changed(self,status,jobs):
        self.last_runtime=status;self.last_jobs={**jobs,'page_after':self.job_offset};self.refresh_world()
    def refresh_world(self):
        if not hasattr(self,'modules') or self.replay.currentIndex()!=0:return
        self.world.setSceneRect(0,0,1000,750)
        self.world.data=project(self.last_runtime,self.last_jobs,self.body_memory.nodes(),self.proposals,self.modules.records(),available=bool(self.client and self.status));self.world.faults={};self.world.render_scene()
        d=self.world.data;self.scene_note.setText(f"{len(d['nodes'])} displayed records · {len(d['edges'])} display links · paged observational projection | Select nodes for source identity")
    def world_mode(self,index):
        if index==0:self.refresh_world()
        else:self.world.set_step(index-1);self.scene_note.setText('TEST FIXTURE / not assembly state')
        QTimer.singleShot(0,self.world.fit)
    def refresh_memory(self):
        self.memory_nodes=self.body_memory.nodes();self.memory_list.clear()
        for node in self.memory_nodes:self.memory_list.addItem(node['kind']+' / '+node['id'])
        head=self.body_memory.head;self.memory_status.setText(f"{len(self.memory_nodes)} records • snapshot {head['sequence'] if head else 0} • PRIVATE • authority NONE")
        self.refresh_world()
    def inspect_memory(self,index):
        if 0<=index<len(self.memory_nodes):
            n=self.memory_nodes[index];show_json(self.memory_detail,dict(record=n,provenance=self.body_memory.memory.provenance(n['id'])))
    def memory_task(self,fn):
        if getattr(self,'memory_busy',False):self.log('WAIT','Memory operation is already running');return
        self.memory_busy=True
        def done(value,error):
            self.memory_busy=False
            if not error:self.log('MEMORY',json.dumps(value)[:700]);show_json(self.memory_detail,value);self.refresh_memory()
        self.async_run(fn,done)
    def remember_chunk(self):
        if not self.last_source:self.log('REFUSED','Explicitly read a selected Library/Workspace source chunk first');return
        chunk=dict(self.last_source);self.memory_task(lambda:self.body_memory.remember_chunk(chunk))
    def remember_job(self):
        job=self.selected_job()
        if not job or not self.client or not job['artifacts']:self.log('REFUSED','Select a completed job in Jobs first');return
        client=self.client
        def read():
            # Re-read the job through authenticated IPC, then verify its artifact.
            cursor=0;fresh=None
            for _ in range(41):
                snapshot=client.request('jobs',payload=dict(after=cursor,limit=25))['draft'];fresh=next((j for j in snapshot['jobs'] if j['id']==job['id']),None)
                if fresh or not snapshot['has_more']:break
                cursor=snapshot['next_cursor']
            if not fresh or not fresh['artifacts']:raise ValueError('No committed artifact observed')
            artifact=client.request('job-artifact',payload=dict(attempt=fresh['artifacts'][-1]['attempt']))['draft']
            return self.body_memory.remember_draft(fresh,artifact)
        self.memory_task(read)
    def inspect_module(self):
        try:show_json(self.memory_detail,self.modules.inspect());self.log('MODULE','Read-only capability routed; no Base admission')
        except Exception as error:self.log('ERROR',str(error))
    def export_memory(self):self.memory_task(self.body_memory.export_private)
    def remember_observation(self):
        if not self.last_frame:self.log('REFUSED','Capture the actual canvas first');return
        record=json.loads(json.dumps(self.last_frame));path=self.observer.root/(record['frame_id']+'.png')
        self.memory_task(lambda:self.body_memory.remember_observation(record,path.read_bytes()))
    def use_memory_context(self):
        index=self.memory_list.currentRow()
        if not 0<=index<len(self.memory_nodes):return
        from components.evidence_memory import canonical,sha
        record=self.memory_nodes[index];body=canonical(record).decode()
        if len(body)>8000:self.log('REFUSED','Selected record exceeds draft context limit; read an explicit smaller source preview');return
        self.last_source=dict(name='memory-'+record['id'],offset=0,next_offset=len(body.encode()),size=len(body.encode()),text=body,chunk_sha256=sha(body.encode()),classification='UNTRUSTED_PRIVATE_OBSERVATIONAL_RECORD')
        self.include_source.setChecked(True);self.nav.setCurrentRow(2);self.log('CONTEXT','Selected record staged for explicit DRAFT_ONLY submission; not sent yet')
    def choose_legacy(self):
        path,_=QFileDialog.getOpenFileName(self,'Select a closed/checkpointed legacy chat database (private import only)','', 'SQLite databases (*.sqlite3 *.sqlite *.db);;All files (*)')
        if path:self.import_legacy(path)
    def import_legacy(self,path):
        from legacy_chat import snapshot_legacy
        def run():
            nodes,report=snapshot_legacy(path,self.data/'legacy-snapshots');admission=self.body_memory.add_nodes(nodes)
            return dict(import_report=report,memory_admission=admission)
        self.memory_task(run)
    def update_reviews(self):
        super().update_reviews()
        if hasattr(self,'modules'):self.refresh_world()
    def detach(self):super().detach();self.refresh_world()
    def closeEvent(self,event):
        super().closeEvent(event);self.body_memory.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,required=True);parser.add_argument('--profile',type=Path,required=True);args=parser.parse_args()
    app=QApplication(sys.argv[:1]);app.setFont(QFont('Segoe UI',11));app.setApplicationName('LEVIS Body Assembly')
    window=BodyWorkbench(args.data,args.profile);screen=app.primaryScreen().availableGeometry();window.resize(min(1500,screen.width()),min(920,screen.height()));window.show();return app.exec()
if __name__=='__main__':sys.exit(main())
