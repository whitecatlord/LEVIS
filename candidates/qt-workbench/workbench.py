"""Separate Qt instrument panel. No governed Base writer or desktop-wide observer."""
import argparse,difflib,hashlib,json,sys,time,uuid
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QSettings,Signal,QObject,QRunnable,QThreadPool,QSize
from PySide6.QtGui import QAction,QFont,QPixmap,QKeySequence
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QListWidget,QStackedWidget,QDockWidget,QPlainTextEdit,QLineEdit,QComboBox,QCheckBox,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView,QTabWidget,QToolButton,QMenu,QSplitter,QScrollArea)
from scene import WorldView
from observation import ObservationController,utc
from scoped_files import ScopedFiles,CHUNK

ROOT=Path(__file__).resolve().parent
class Result(QObject):finished=Signal(object,object)
class Task(QRunnable):
    def __init__(self,fn):super().__init__();self.fn=fn;self.signals=Result()
    def run(self):
        try:self.signals.finished.emit(self.fn(),None)
        except Exception as e:self.signals.finished.emit(None,e)

def panel():
    w=QWidget();l=QVBoxLayout(w);l.setContentsMargins(12,10,12,10);l.setSpacing(8);return w,l
def label(text,name=None):
    w=QLabel(text);w.setWordWrap(True)
    if name:w.setObjectName(name)
    return w
def button(text,fn):
    w=QPushButton(text);w.clicked.connect(fn);return w
def textview():
    t=QPlainTextEdit();t.setReadOnly(True);t.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth);return t
def show_json(widget,obj):widget.setPlainText(json.dumps(obj,ensure_ascii=False,indent=2))

class Workbench(QMainWindow):
    def __init__(self,data,profile=None):
        super().__init__();self.data=Path(data).absolute();self.data.mkdir(parents=True,exist_ok=True)
        self.setWindowTitle('LEVIS / WORKBENCH — isolated GUI candidate');self.resize(1500,920);self.setMinimumSize(1000,650)
        self.settings=QSettings(str(self.data/'layout.ini'),QSettings.Format.IniFormat)
        self.pool=QThreadPool(self);self.pool.setMaxThreadCount(2);self.tasks=set();self.pending=False;self.client=None;self.profile=profile;self.status=None;self.jobs=None;self.job_offset=0;self.events_after=0;self.proposals=[];self.logs=[];self.catalogs={};self.last_source=None;self.last_frame=None;self.full_world=False
        self.setDockOptions(QMainWindow.DockOption.AllowNestedDocks|QMainWindow.DockOption.AllowTabbedDocks|QMainWindow.DockOption.AnimatedDocks)
        self.build();self.load_proposals();self.apply_theme(self.settings.value('theme','Dark'));self.restoreGeometry(self.settings.value('geometry',b''));self.restoreState(self.settings.value('docks',b''))
        self.observer=ObservationController(self.world,self.data/'observations');self.observer.completed.connect(self.observed)
        if self.observer.history:self.observed(self.observer.history[-1])
        self.capture_timer=QTimer(self);self.capture_timer.setInterval(2000);self.capture_timer.timeout.connect(self.capture)
        self.poll_timer=QTimer(self);self.poll_timer.setInterval(2500);self.poll_timer.timeout.connect(self.refresh_runtime);self.poll_timer.start()
        self.log('SYS','Workbench started. Fixture world; runtime detached; observation manual.')
        QTimer.singleShot(150,self.world.fit)
        if profile:QTimer.singleShot(250,lambda:self.attach(profile))
    def dock(self,title,widget,area,name):
        d=QDockWidget(title,self);d.setObjectName(name);d.setWidget(widget);d.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas);self.addDockWidget(area,d);return d
    def build(self):
        top=self.addToolBar('Runtime status');top.setObjectName('statusToolbar');top.setMovable(False)
        brand=label('◈  LEVIS / WORKBENCH','brand');brand.setWordWrap(False);top.addWidget(brand);top.addSeparator()
        self.runtime_label=label('RUNTIME / DETACHED','runtime');top.addWidget(self.runtime_label)
        self.model_label=label('MODEL  /  UNKNOWN');top.addWidget(self.model_label)
        top.addWidget(label('LOCAL • NO CLOUD','local'));self.approval_label=label('REVIEWS / 0');top.addWidget(self.approval_label);self.top_job=label('JOB / —');top.addWidget(self.top_job)
        top.addWidget(button('Attach…',self.choose_profile));top.addWidget(button('Detach',self.detach))
        self.nav=QListWidget();self.nav.setObjectName('navigation');self.nav.addItems(['Overview','World View','Chat / MUD','Library','Workspace','Jobs','Proposals','Evidence','Diagnostics']);self.nav.setMinimumWidth(160);self.nav.setMaximumWidth(210)
        self.pages=QStackedWidget();central=QSplitter();central.addWidget(self.nav);central.addWidget(self.pages);central.setStretchFactor(1,1);self.setCentralWidget(central)
        overview,ol=panel();ol.addWidget(label('YOUR LOCAL INSTRUMENT PANEL','pageTitle'));ol.addWidget(label('A separate GUI candidate for durable drafts and self-observation. The world is a deterministic scene fixture. It does not represent governed Base geometry.'))
        self.overview=textview();ol.addWidget(self.overview);self.overview.setPlainText('GUI candidate • acceptance NOT_GRANTED\n\n1  Attach to a separately started M1.2 coordinator.\n2  Inspect status and jobs before resuming.\n3  Capture the canvas to compare actual fixture pixels with intended markers.\n4  Select Library / Workspace roots explicitly.\n\nClosing this window leaves the coordinator and authorized jobs running.\nNo source overwrite, code executor, cloud endpoint or automatic approval exists.')
        self.pages.addWidget(overview)
        world_page,wl=panel();wl.addWidget(label('WORLD VIEW  /  Rendered geometry','pageTitle'))
        controls=QHBoxLayout();controls.addWidget(label('TEST FIXTURE • READ-ONLY LENS','local'));controls.addStretch();controls.addWidget(button('Fit  [F]',self.fit_world));controls.addWidget(button('−',lambda:self.world.scale(.85,.85)));controls.addWidget(button('+',lambda:self.world.scale(1.15,1.15)))
        layers=QToolButton();layers.setText('Layers');layers.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);menu=QMenu(layers)
        self.world=WorldView()
        for name in self.world.layers:
            a=menu.addAction(name);a.setCheckable(True);a.setChecked(True);a.toggled.connect(lambda checked,k=name:self.set_layer(k,checked))
        layers.setMenu(menu);controls.addWidget(layers);controls.addWidget(button('Focus  [F11]',self.focus_world));wl.addLayout(controls)
        replay=QHBoxLayout();replay.addWidget(label('Fixture replay'));self.replay=QComboBox();self.replay.addItems(['Frame 0 / baseline','Frame 1 / movement','Frame 2 / movement']);self.replay.currentIndexChanged.connect(self.world.set_step);replay.addWidget(self.replay);replay.addStretch();wl.addLayout(replay)
        wl.addWidget(self.world,1);self.scene_note=label('43 fixture nodes · 72 edges · 3 basins | Drag to pan · Wheel to zoom · Select a node to inspect');wl.addWidget(self.scene_note);self.world.inspected.connect(self.inspect_node);self.pages.addWidget(world_page)
        chat,cl=panel();cl.addWidget(label('CHAT / MUD  /  Durable draft requests','pageTitle'));cl.addWidget(label('Text is submitted as an unverified draft goal. No direct model worker or shell. /status, /jobs, /pause, /resume and /help are the only console commands.'))
        self.chat_history=textview();cl.addWidget(self.chat_history,1);self.goal=QPlainTextEdit();self.goal.setPlaceholderText('Ask LEVIS to draft a response…');self.goal.setMaximumHeight(120);self.goal.setAccessibleName('Draft goal');cl.addWidget(self.goal)
        self.include_source=QCheckBox('Include last explicitly read source chunk (first 8,000 characters)');cl.addWidget(self.include_source);self.authorize=QCheckBox('I authorize this request as DRAFT_ONLY; output remains unverified');cl.addWidget(self.authorize)
        row=QHBoxLayout();row.addWidget(button('Submit draft',self.submit));row.addWidget(button('Replay saved unconfirmed request',self.replay_request));cl.addLayout(row);self.pages.addWidget(chat)
        for kind in ['Library','Workspace']:self.pages.addWidget(self.files_page(kind))
        jobs,jl=panel();jl.addWidget(label('JOBS  /  Coordinator-owned history','pageTitle'))
        row=QHBoxLayout();row.addWidget(button('Refresh',self.refresh_runtime));row.addWidget(button('Pause',lambda:self.control('pause')));row.addWidget(button('Resume dispatch',lambda:self.control('resume')));row.addWidget(button('Previous jobs',self.previous_jobs));row.addWidget(button('Next jobs',self.next_jobs));jl.addLayout(row)
        self.job_table=QTableWidget(0,4);self.job_table.setHorizontalHeaderLabels(['Job','State','Goal','Integrity']);self.job_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch);self.job_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.job_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);jl.addWidget(self.job_table)
        row=QHBoxLayout();row.addWidget(button('Inspect result',self.inspect_job));row.addWidget(button('Cancel selected',lambda:self.job_action('job-cancel')));row.addWidget(button('Retry selected (authorized)',lambda:self.job_action('job-retry')));jl.addLayout(row)
        self.current_job=label('Current job / unknown until attached');jl.addWidget(self.current_job);self.answer=QLineEdit();self.answer.setPlaceholderText('Answer to a selected NEEDS_ANSWER job');jl.addWidget(self.answer);jl.addWidget(button('Submit answer (authorized)',lambda:self.job_action('job-answer')));self.job_detail=textview();jl.addWidget(self.job_detail);self.pages.addWidget(jobs)
        proposals,pl=panel();pl.addWidget(label('PROPOSALS  /  Inspect before deciding','pageTitle'));self.proposal_list=QListWidget();self.proposal_list.currentRowChanged.connect(self.inspect_proposal);pl.addWidget(self.proposal_list);self.proposal_detail=textview();pl.addWidget(self.proposal_detail,1)
        row=QHBoxLayout();row.addWidget(button('Defer',lambda:self.decide('DEFERRED')));row.addWidget(button('Reject draft',lambda:self.decide('REJECTED')));row.addWidget(button('Approve draft only',lambda:self.decide('APPROVED_DRAFT_ONLY')));pl.addLayout(row);pl.addWidget(label('Decisions are local review records. They never apply patches, change Base or grant runtime authority.'));self.pages.addWidget(proposals)
        evidence,el=panel();el.addWidget(label('EVIDENCE  /  Actual capture history','pageTitle'));self.frames=QListWidget();self.frames.currentRowChanged.connect(self.select_frame);el.addWidget(self.frames);self.evidence_detail=textview();el.addWidget(self.evidence_detail,1);self.pages.addWidget(evidence)
        diagnostics,dl=panel();dl.addWidget(label('DIAGNOSTICS  /  Candidate boundaries','pageTitle'));self.diagnostics=textview();self.diagnostics.setPlainText('No desktop-wide capture. No cloud API. No runtime database writer.\n\nRuntime: explicit authenticated attachment only. Model liveness is not inferred from configuration.\nScene: fixture only; authoritative engine adapter pending.\nObservation: widget pixels, not monitor scanout; marker analyzer only.\nLibrary: selected root; immediate file pages, 64 KiB chunks, up to 5 GiB.\nWorkspace: source reads and save-new drafts; no source replacement.\nLogs: latest 2,000 entries in memory, search applies to retained window.\nEvidence: latest 200 metadata records loaded; PNG/JSON history stays on local disk.\nSame-user path replacement races and hostile local processes are not sandboxed by this GUI.\n\nGUI integration acceptance NOT_GRANTED; wider performance, screen reader and soak qualification pending.');dl.addWidget(self.diagnostics);self.pages.addWidget(diagnostics)
        obs,ol=panel();ol.addWidget(label('PERCEPTION / SELF-OBSERVATION','panelTitle'));ol.addWidget(label('Own canvas only • actual Qt widget pixels','local'))
        row=QHBoxLayout();row.addWidget(button('Capture  [Ctrl+K]',self.capture));self.auto=QCheckBox('Every 2 s');self.auto.toggled.connect(self.toggle_auto);row.addWidget(self.auto);ol.addLayout(row)
        row=QHBoxLayout();self.observe_enabled=QCheckBox('Observation enabled');self.observe_enabled.setChecked(True);self.observe_enabled.toggled.connect(self.enable_observation);row.addWidget(self.observe_enabled);self.analyzer_enabled=QCheckBox('Pixel analyzer');self.analyzer_enabled.setChecked(True);self.analyzer_enabled.toggled.connect(self.toggle_analyzer);row.addWidget(self.analyzer_enabled);ol.addLayout(row)
        self.obs_tabs=QTabWidget();self.raw=QLabel('No capture yet');self.raw.setAlignment(Qt.AlignmentFlag.AlignCenter);self.raw.setMinimumSize(220,120);self.raw.setMaximumHeight(250);self.raw.setScaledContents(False);self.obs_tabs.addTab(self.raw,'Raw pixels');self.intended=textview();self.obs_tabs.addTab(self.intended,'Intended');self.comparison=textview();self.obs_tabs.addTab(self.comparison,'Analysis');ol.addWidget(self.obs_tabs,1)
        self.frame_meta=label('FRAME / none');ol.addWidget(self.frame_meta);self.obs_summary=label('Vision unavailable until a real capture is analyzed. No confidence score.');ol.addWidget(self.obs_summary)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(obs)
        self.obs_dock=self.dock('Self-observation',scroll,Qt.DockWidgetArea.RightDockWidgetArea,'observation');self.obs_dock.setMinimumWidth(300)
        activity,al=panel();row=QHBoxLayout();row.addWidget(label('ACTIVITY / MUD LOG','panelTitle'));self.search=QLineEdit();self.search.setPlaceholderText('Search retained events…');self.search.textChanged.connect(self.filter_logs);row.addWidget(self.search);al.addLayout(row);self.console=textview();self.console.setMaximumBlockCount(2000);self.console.setMinimumHeight(100);self.console.setFont(QFont('Consolas',11));al.addWidget(self.console)
        self.activity_dock=self.dock('Activity',activity,Qt.DockWidgetArea.BottomDockWidgetArea,'activity')
        review,rl=panel();self.review_summary=label('NO PENDING PROPOSAL','panelTitle');rl.addWidget(self.review_summary);rl.addWidget(label('Saved Workspace drafts appear here. Review source, diff, evidence and tests before recording a decision.'));rl.addWidget(button('Inspect proposals',lambda:self.nav.setCurrentRow(6)))
        self.review_dock=self.dock('Proposal review',review,Qt.DockWidgetArea.BottomDockWidgetArea,'review');self.splitDockWidget(self.activity_dock,self.review_dock,Qt.Orientation.Horizontal)
        self.resizeDocks([self.obs_dock],[360],Qt.Orientation.Horizontal);self.resizeDocks([self.activity_dock,self.review_dock],[190,190],Qt.Orientation.Vertical)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex);self.nav.setCurrentRow(1)
        view=self.menuBar().addMenu('View')
        for d in [self.obs_dock,self.activity_dock,self.review_dock]:view.addAction(d.toggleViewAction())
        view.addAction('Reset layout',self.reset_layout);view.addAction('Focus World View',self.focus_world)
        self.theme=QComboBox();self.theme.addItems(['Dark','Light']);self.theme.setCurrentText(self.settings.value('theme','Dark'));self.theme.currentTextChanged.connect(self.apply_theme);self.statusBar().addPermanentWidget(self.theme)
        self.statusBar().showMessage('FIXTURE WORLD  |  Library read-only  |  Workspace scoped  |  Runtime separate  |  CANDIDATE / NOT ACCEPTED')
        for key,fn in [('Ctrl+K',self.capture),('F11',self.focus_world),('F',self.fit_world)]:
            a=QAction(self);a.setShortcut(QKeySequence(key));a.triggered.connect(fn);self.addAction(a)
        for i in range(9):
            a=QAction(self);a.setShortcut(QKeySequence(f'Ctrl+{i+1}'));a.triggered.connect(lambda checked=False,n=i:self.nav.setCurrentRow(n));self.addAction(a)
    def apply_theme(self,name):
        self.settings.setValue('theme',name)
        bg,pan,fg,muted,border=('#09151e','#11232e','#e9f2f5','#9fb4c1','#29434f') if name=='Dark' else ('#edf3f6','#ffffff','#11232e','#455f70','#b6c9d3')
        self.setStyleSheet(f'''QMainWindow,QWidget {{background:{bg};color:{fg};font-family:"Segoe UI";font-size:11pt;}} QToolBar {{spacing:10px;padding:7px;border-bottom:1px solid {border};}} QMenuBar,QMenu,QStatusBar {{background:{pan};}} QDockWidget::title {{background:{pan};padding:7px;color:{muted};}} QDockWidget {{border:1px solid {border};}} QPushButton,QToolButton,QComboBox {{background:{pan};border:1px solid {border};border-radius:5px;padding:7px 10px;}} QPushButton:hover,QToolButton:hover {{border-color:#29cfc5;}} QPushButton:focus,QLineEdit:focus,QPlainTextEdit:focus {{border:2px solid #29cfc5;}} QLineEdit,QPlainTextEdit,QListWidget,QTableWidget {{background:{pan};border:1px solid {border};border-radius:4px;padding:5px;selection-background-color:#126c72;}} QListWidget#navigation {{background:{bg};border:0;font-size:12pt;}} QListWidget#navigation::item {{padding:8px 8px;}} QListWidget::item:selected {{background:#12616a;color:#ffffff;}} QLabel#brand {{font-size:16pt;font-weight:700;}} QLabel#pageTitle {{font-size:17pt;font-weight:650;}} QLabel#panelTitle {{font-size:12pt;font-weight:650;}} QLabel#local {{color:#35cfc4;font-weight:600;}} QLabel#runtime {{color:#e7b95f;font-weight:600;}} QHeaderView::section,QTabBar::tab {{background:{pan};color:{fg};padding:7px;border:1px solid {border};}} QTabBar::tab:selected {{border-bottom:2px solid #2bd8cd;}} QSplitter::handle {{background:{border};width:3px;}}''')
    def log(self,kind,msg):
        self.logs.append(f'[{time.strftime("%H:%M:%S")}] [{kind}] {msg}');self.logs=self.logs[-2000:];self.filter_logs()
    def filter_logs(self):
        query=self.search.text().casefold();self.console.setPlainText('\n'.join(s for s in self.logs if query in s.casefold()));self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
    def async_run(self,fn,done):
        task=Task(fn);self.tasks.add(task)
        def completed(value,error):
            self.tasks.discard(task)
            if error:self.log('ERROR',str(error)[:500])
            done(value,error)
        task.signals.finished.connect(completed);self.pool.start(task)
    def fit_world(self):self.world.fit()
    def set_layer(self,key,value):self.world.layers[key]=value;self.world.render_scene()
    def focus_world(self):
        self.full_world=not self.full_world
        for d in [self.obs_dock,self.activity_dock,self.review_dock]:d.setVisible(not self.full_world)
        self.nav.setVisible(not self.full_world);self.nav.setCurrentRow(1)
        if self.full_world:self.showFullScreen()
        else:self.showNormal()
        self.world.fit()
    def reset_layout(self):
        self.full_world=False;self.nav.show();self.showNormal()
        for d,area in [(self.obs_dock,Qt.DockWidgetArea.RightDockWidgetArea),(self.activity_dock,Qt.DockWidgetArea.BottomDockWidgetArea),(self.review_dock,Qt.DockWidgetArea.BottomDockWidgetArea)]:d.setFloating(False);self.addDockWidget(area,d);d.show()
        self.splitDockWidget(self.activity_dock,self.review_dock,Qt.Orientation.Horizontal);self.resizeDocks([self.obs_dock],[350],Qt.Orientation.Horizontal);self.resizeDocks([self.activity_dock,self.review_dock],[190,190],Qt.Orientation.Vertical)
    def inspect_node(self,body):self.intended.setPlainText(body);self.obs_tabs.setCurrentIndex(1)
    def capture(self):
        if not hasattr(self,'observer'):return
        fid=self.observer.capture_viewport()
        if fid:self.log('CAPTURE',f'{fid} queued; own viewport only')
    def toggle_auto(self,value):
        if not hasattr(self,'capture_timer'):return
        if value:self.capture_timer.start()
        else:self.capture_timer.stop()
    def enable_observation(self,value):
        if hasattr(self,'observer'):self.observer.enabled=value;self.log('PERCEPT','Enabled' if value else 'Disabled; coordinator unaffected')
    def toggle_analyzer(self,value):
        from observation import MarkerAnalyzer
        if hasattr(self,'observer'):self.observer.adapter=MarkerAnalyzer() if value else None
    def observed(self,r):
        self.last_frame=r;self.display_frame(r);self.frames.blockSignals(True);self.frames.clear()
        for item in reversed(self.observer.history):self.frames.addItem(f"{item['sequence']}  ·  {item['captured_at_utc'][11:19]}  ·  {item.get('capture_status')}")
        self.frames.blockSignals(False);self.log('VERIFY',r.get('comparison',{}).get('status',r.get('error','Unavailable')))
    def display_frame(self,r):
        pix=QPixmap(str(self.data/'observations'/(r['frame_id']+'.png')))
        if not pix.isNull():self.raw.setPixmap(pix.scaled(max(220,self.obs_dock.width()-40),220,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        else:self.raw.setText('Capture unavailable')
        show_json(self.intended,r['intended_scene']);show_json(self.comparison,dict(interpretation=r.get('interpretation'),comparison=r.get('comparison'),pixel_delta=r.get('pixel_delta'),error=r.get('error'),storage_error=r.get('storage_error')))
        self.frame_meta.setText(f"FRAME {r['sequence']}  /  {r['captured_at_utc'][11:19]} UTC\n{r['frame_id'][:25]}…\nPNG SHA256 {r.get('png_sha256','unavailable')[:20]}…")
        c=r.get('comparison',{});self.obs_summary.setText(f"{c.get('status','UNAVAILABLE')}\nExpected markers: {c.get('expected','—')} • Observed markers: {c.get('observed','—')}\nMissing: {len(c.get('missing') or [])} • Unexpected: {len(c.get('unexpected') or [])} • Shape changes: {len(c.get('shape_changes') or [])}\nFixture pixel measurements only; no semantic confidence score.")
        show_json(self.evidence_detail,r)
    def select_frame(self,index):
        if 0<=index<len(self.observer.history):self.display_frame(self.observer.history[-1-index])
    def choose_profile(self):
        path=QFileDialog.getExistingDirectory(self,'Select an existing M1.2 candidate profile')
        if path:self.attach(path)
    def attach(self,path):
        if self.pending:return
        self.pending=True;self.profile=str(Path(path).absolute())
        def connect():
            sys.path.insert(0,str(ROOT/'runtime'))
            from runtime_client import Client
            client=Client(self.profile,'qt-workbench');client.request('attach');return client
        def attached(value,error):
            self.pending=False
            if not error:self.client=value;self.events_after=0;self.job_offset=0;self.log('IPC','Authenticated candidate attachment; no automatic resume');self.refresh_runtime()
        self.async_run(connect,attached)
    def detach(self):
        if self.pending:return
        self.client=None;self.status=None;self.jobs=None;self.runtime_label.setText('COORDINATOR / DETACHED');self.model_label.setText('MODEL / UNKNOWN');self.log('IPC','GUI detached; coordinator and jobs left running')
    def refresh_runtime(self):
        if not self.client or self.pending:return
        client=self.client;offset=self.job_offset;cursor=self.events_after;self.pending=True
        def read():return client.request('status'),client.request('jobs',payload=dict(after=offset,limit=25)),client.request('events',payload=dict(after=cursor,limit=100))
        def updated(value,error):
            self.pending=False
            if error:self.status=None;self.runtime_label.setText('COORDINATOR / UNAVAILABLE');self.model_label.setText('MODEL / UNKNOWN');return
            self.status,jobs,events=value;self.jobs=jobs['draft'];self.runtime_label.setText('RUNTIME / '+self.status['state']);self.model_label.setText('MODEL / CONFIGURED' if self.status['model_enabled'] else 'MODEL / NO OLLAMA');self.model_label.setToolTip('Provider configuration only; model-service liveness and semantic accuracy are unknown')
            self.top_job.setText('JOB / '+(self.jobs.get('active_attempt') or '—')[:8])
            self.current_job.setText(f"Current attempt / {self.jobs.get('active_attempt') or 'none'}  •  {self.jobs['job_count']} jobs total  •  page after {offset}")
            self.job_table.setRowCount(len(self.jobs['jobs']))
            for row,j in enumerate(self.jobs['jobs']):
                for col,text in enumerate([j['id'][:12],j['display_state'],j['goal'],j['artifacts'][-1]['integrity'] if j['artifacts'] else 'No artifact']):self.job_table.setItem(row,col,QTableWidgetItem(text))
            for event in events.get('events',[]):self.log('COORD',f"{event['state']}  revision {event['revision']}  event {event['cursor']}")
            self.events_after=events.get('next_cursor',cursor)
        self.async_run(read,updated)
    def mutate(self,command,payload=None):
        if not self.client:self.log('REFUSED','Attach to a running M1.2 coordinator first');return
        if self.pending:self.log('WAIT','Runtime request in progress; try after refresh');return
        self.pending=True;client=self.client;rid=uuid.uuid4().hex
        def send():
            revision=client.request('status')['revision'] if command in ('pause','resume') else client.request('jobs')['draft']['revision']
            request=dict(client_id=client.client_id,request_id=rid,command=command,expected_revision=revision,payload=payload or {})
            (self.data/'last_request.json').write_text(json.dumps(request,indent=2),encoding='utf-8')
            try:result=client.request(command,revision,payload,rid)
            except Exception as e:
                if hasattr(e,'request'):
                    saved=dict(profile=str(client.profile),profile_sha256=hashlib.sha256((client.profile/'profile.json').read_bytes()).hexdigest(),request=e.request)
                    (self.data/'unconfirmed.json').write_text(json.dumps(saved,indent=2),encoding='utf-8')
                raise
            return result
        def done(value,error):
            self.pending=False
            if error:self.chat_history.appendPlainText('UNCONFIRMED / ERROR: '+str(error));return
            self.log('IPC',command+' → '+json.dumps(value)[:700]);self.chat_history.appendPlainText(command+' receipt:\n'+json.dumps(value,indent=2));self.refresh_runtime()
        self.async_run(send,done)
    def replay_request(self):
        if self.pending or not self.client:return
        path=self.data/'unconfirmed.json'
        if not path.exists():self.log('IPC','No saved unconfirmed mutation');return
        self.pending=True
        def replay():
            saved=json.loads(path.read_text(encoding='utf-8'))
            if saved['profile']!=str(self.client.profile) or saved['profile_sha256']!=hashlib.sha256((self.client.profile/'profile.json').read_bytes()).hexdigest():raise ValueError('Unconfirmed request belongs to a different profile; replay refused')
            r=saved['request']
            from runtime_client import Client
            return Client(self.profile,r['client_id']).request(r['command'],r['expected_revision'],r['payload'],r['request_id'])
        def done(value,error):
            self.pending=False
            if not error:self.chat_history.appendPlainText('EXACT REPLAY RECEIPT:\n'+json.dumps(value,indent=2));self.refresh_runtime()
        self.async_run(replay,done)
    def control(self,command):self.mutate(command)
    def submit(self):
        goal=self.goal.toPlainText()
        if goal.startswith('/'):
            command=goal.strip()
            if command in ('/status','/jobs'):self.refresh_runtime()
            elif command in ('/pause','/resume'):self.control(command[1:])
            else:self.log('MUD','Commands: /status /jobs /pause /resume /help. No shell or arbitrary commands.')
            return
        if not self.authorize.isChecked():self.log('REFUSED','Explicit DRAFT_ONLY authorization is required');return
        if not goal.strip() or len(goal)>3000:self.log('REFUSED','Draft goal must contain 1–3,000 characters');return
        inputs=[]
        if self.include_source.isChecked() and self.last_source:
            text=self.last_source['text'][:8000];inputs=[dict(name=self.last_source['name'],text=text,sha256=hashlib.sha256(text.encode()).hexdigest())]
        self.mutate('job-submit',dict(goal=goal,inputs=inputs,authorization=dict(operator='Qt Operator',scope='DRAFT_ONLY')));self.authorize.setChecked(False)
    def selected_job(self):
        row=self.job_table.currentRow()
        return self.jobs['jobs'][row] if self.jobs and 0<=row<len(self.jobs['jobs']) else None
    def inspect_job(self):
        job=self.selected_job()
        if not job:return
        show_json(self.job_detail,job)
        if job['artifacts'] and self.client and not self.pending:
            client=self.client;attempt=job['artifacts'][-1]['attempt'];self.pending=True
            def done(value,error):
                self.pending=False
                if not error:show_json(self.job_detail,value);self.chat_history.appendPlainText('UNVERIFIED DRAFT / '+json.dumps(value['draft'],ensure_ascii=False,indent=2))
            self.async_run(lambda:client.request('job-artifact',payload=dict(attempt=attempt)),done)
    def job_action(self,command):
        job=self.selected_job()
        if not job:return
        payload=dict(job=job['id'])
        if command in ('job-retry','job-answer'):
            if not self.authorize.isChecked():self.log('REFUSED','Enable explicit DRAFT_ONLY authorization in Chat / MUD');return
            payload['authorization']=dict(operator='Qt Operator',scope='DRAFT_ONLY')
        if command=='job-answer':payload['text']=self.answer.text()
        self.mutate(command,payload)
        if command in ('job-retry','job-answer'):self.authorize.setChecked(False)
    def next_jobs(self):
        if self.jobs and self.jobs['has_more']:self.job_offset=self.jobs['next_cursor'];self.refresh_runtime()
    def previous_jobs(self):self.job_offset=0;self.refresh_runtime()
    def files_page(self,kind):
        w,l=panel();l.addWidget(label(kind.upper()+'  /  '+('Read-only sources' if kind=='Library' else 'Scoped drafts and review'),'pageTitle'))
        info=label('No folder selected');l.addWidget(info);row=QHBoxLayout();row.addWidget(button('Select folder…',lambda:self.choose_root(kind)));row.addWidget(button('First page',lambda:self.catalog_page(kind,0)));row.addWidget(button('Next 100 files',lambda:self.catalog_next(kind)));l.addLayout(row)
        listing=QListWidget();l.addWidget(listing);preview=textview();l.addWidget(preview,1);row=QHBoxLayout();row.addWidget(button('Read first 64 KiB',lambda:self.read_selected(kind,0)));row.addWidget(button('Next chunk',lambda:self.read_next(kind)));l.addLayout(row)
        self.catalogs[kind]=dict(label=info,list=listing,preview=preview,scope=None,offset=0,page=None,read=None,busy=False)
        if kind=='Workspace':
            editor=QPlainTextEdit();editor.setPlaceholderText('Write a new draft. Selected sources are never overwritten.');editor.setAccessibleName('Workspace draft');l.addWidget(editor,1);self.draft_editor=editor;l.addWidget(button('Save new draft + proposal',self.save_draft))
        return w
    def choose_root(self,kind):
        path=QFileDialog.getExistingDirectory(self,'Select '+kind+' root')
        if path:
            try:self.catalogs[kind]['scope']=ScopedFiles(path);self.catalogs[kind]['label'].setText(path);self.catalog_page(kind,0)
            except (OSError,ValueError) as e:self.log('REFUSED',str(e))
    def catalog_page(self,kind,offset):
        c=self.catalogs[kind]
        if not c['scope'] or c['busy']:return
        c['busy']=True;scope=c['scope']
        def done(value,error):
            c['busy']=False
            if not error:
                c['page']=value;c['list'].clear()
                for row in value['rows']:c['list'].addItem(f"{row['name']}   ·   {row['bytes']:,} bytes")
        self.async_run(lambda:scope.page(offset),done)
    def catalog_next(self,kind):
        c=self.catalogs[kind]
        if c['page'] and c['page']['has_more']:self.catalog_page(kind,c['page']['next_offset'])
    def read_selected(self,kind,offset):
        c=self.catalogs[kind];index=c['list'].currentRow()
        if not c['scope'] or not c['page'] or index<0 or c['busy']:return
        c['busy']=True;scope=c['scope'];name=c['page']['rows'][index]['name']
        def done(value,error):
            c['busy']=False
            if not error:c['read']=value;self.last_source=value;c['preview'].setPlainText(f"{value['classification']}\nBytes {value['offset']:,}–{value['next_offset']:,} of {value['size']:,}\nChunk SHA256 {value['chunk_sha256']}\n\n{value['text']}");self.log('READ',f'{kind}: {name}; bounded chunk at {offset}')
        self.async_run(lambda:scope.read(name,offset),done)
    def read_next(self,kind):
        c=self.catalogs[kind]
        index=c['list'].currentRow()
        if c['read'] and c['read']['truncated']:
            if not c['page'] or index<0 or c['page']['rows'][index]['name']!=c['read']['name']:self.log('READ','Selection changed; read the first chunk of this source before continuing');return
            self.read_selected(kind,c['read']['next_offset'])
    def save_draft(self):
        c=self.catalogs['Workspace']
        if not c['scope'] or c['busy']:self.log('REFUSED','Select a Workspace folder first');return
        text=self.draft_editor.toPlainText();source=c['read'];scope=c['scope'];c['busy']=True
        def done(value,error):
            c['busy']=False
            if not error:
                value['diff']=''.join(difflib.unified_diff((source['text'] if source else '').splitlines(keepends=True),text.splitlines(keepends=True),fromfile='source chunk (bounded)',tofile='new draft'))[:64000];value['review']='PENDING_REVIEW';self.proposals.append(value);self.proposals=self.proposals[-100:];self.persist_proposals();self.load_proposals();self.log('PROPOSAL','New draft saved; source unchanged; '+value['id'])
        self.async_run(lambda:scope.save_proposal(text,source),done)
    def inspect_proposal(self,index):
        if 0<=index<len(self.proposals):show_json(self.proposal_detail,self.proposals[index])
    def decide(self,decision):
        index=self.proposal_list.currentRow()
        if not 0<=index<len(self.proposals):return
        p=self.proposals[index];p['review']=decision
        with (self.data/'review-decisions.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(at=utc(),proposal=p['id'],draft_sha256=p['sha256'],decision=decision,authority_effect='NONE',applied=False))+'\n')
        self.proposal_list.item(index).setText(p['id'][:12]+' / '+decision);self.persist_proposals();self.inspect_proposal(index);self.update_reviews()
    def persist_proposals(self):
        raw=json.dumps(self.proposals,ensure_ascii=False).encode('utf-8')
        if len(raw)>24_000_000:raise ValueError('Local proposal index limit exceeded; saved drafts remain in Workspace')
        temp=self.data/'proposals.tmp';temp.write_bytes(raw);temp.replace(self.data/'proposals.json')
    def load_proposals(self):
        path=self.data/'proposals.json'
        if path.exists():
            if path.stat().st_size>24_000_000:raise ValueError('Proposal index exceeds bound')
            self.proposals=json.loads(path.read_text(encoding='utf-8'))[-100:]
        self.proposal_list.clear()
        for p in self.proposals:self.proposal_list.addItem(p['id'][:12]+' / '+p.get('review','PENDING_REVIEW'))
        self.update_reviews()
    def update_reviews(self):
        count=sum(p.get('review')=='PENDING_REVIEW' for p in self.proposals);self.approval_label.setText(f'LOCAL REVIEWS / {count}');self.review_summary.setText(f'{count} PENDING LOCAL DRAFT REVIEW(S)')
    def closeEvent(self,event):
        self.poll_timer.stop();self.capture_timer.stop();self.observer.close();self.pool.waitForDone()
        self.settings.setValue('geometry',self.saveGeometry());self.settings.setValue('docks',self.saveState());self.settings.sync()
        # No stop/detach mutation, model termination, source write or profile migration.
        event.accept()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,default=ROOT.parent/'LEVIS_WORKBENCH_PRIVATE');parser.add_argument('--profile',type=Path);args=parser.parse_args()
    app=QApplication(sys.argv[:1]);app.setApplicationName('LEVIS Workbench Candidate');app.setFont(QFont('Segoe UI',11));window=Workbench(args.data,args.profile)
    available=app.primaryScreen().availableGeometry();window.resize(min(1500,available.width()),min(920,available.height()));window.show();return app.exec()
if __name__=='__main__':sys.exit(main())
