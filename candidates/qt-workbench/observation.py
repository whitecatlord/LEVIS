"""Intended scene, actual Qt-captured pixels and bounded interpretation stay distinct."""
import hashlib,json,time,uuid,math,re
from pathlib import Path
from datetime import datetime,timezone
from PySide6.QtCore import QObject,Signal,QRunnable,QThreadPool,QBuffer,QIODevice
from PySide6.QtGui import QImage

def utc():return datetime.now(timezone.utc).isoformat()
def encode_png(image):
    buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer,'PNG'):raise OSError('PNG encoding failed')
    return bytes(buffer.data())

class MarkerAnalyzer:
    """Measures exact fixture ink components; not general scene recognition or model vision."""
    name='fixture-marker-components-v1'
    def analyze(self,image):
        image=image.convertToFormat(QImage.Format.Format_RGBA8888)
        if image.width()*image.height()>4_000_000:raise ValueError('Pixel analysis limit: 4 million pixels')
        raw=bytes(image.constBits());stride=image.bytesPerLine();w,h=image.width(),image.height()
        colors={(59,230,221):'#3be6dd',(240,187,101):'#f0bb65',(173,156,255):'#ad9cff'}
        points={}
        for y in range(h):
            row=y*stride
            for x in range(w):
                i=row+x*4;color=colors.get((raw[i],raw[i+1],raw[i+2]))
                if color:points[(x,y)]=color
        components=[]
        while points:
            seed,color=points.popitem();stack=[seed];component=[seed]
            while stack:
                x,y=stack.pop()
                for p in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
                    if points.get(p)==color:points.pop(p);stack.append(p);component.append(p)
            xs=[p[0] for p in component];ys=[p[1] for p in component];bw=max(xs)-min(xs)+1;bh=max(ys)-min(ys)+1
            # Excludes same-color label glyphs and thin decorative basin outlines.
            if 4<=bw<=160 and 4<=bh<=160 and len(component)>=12 and .6<bw/bh<1.6:
                fill=len(component)/(bw*bh)
                if fill>.52:components.append(dict(x=(min(xs)+max(xs))/2,y=(min(ys)+max(ys))/2,color=color,pixels=len(component),shape='rectangle' if fill>.92 else 'circle',fill_ratio=round(fill,3)))
        return dict(status='AVAILABLE',adapter=self.name,markers=components,limitations='Exact palette connected components of fixture pixels only. Small/clipped/overlapping markers, selection outlines and labels can confound classification. No model vision or confidence score.')

def compare(expected,analysis):
    if analysis['status']!='AVAILABLE':return dict(status='UNAVAILABLE',reason=analysis.get('error','Analyzer detached'),missing=None,unexpected=None)
    remaining=list(analysis['markers']);missing=[];changed=[]
    for marker in expected['expected_visible_markers']:
        candidates=[m for m in remaining if m['color']==marker['color'] and math.hypot(m['x']-marker['x'],m['y']-marker['y'])<=8]
        if not candidates:missing.append(marker['id']);continue
        found=min(candidates,key=lambda m:math.hypot(m['x']-marker['x'],m['y']-marker['y']));remaining.remove(found)
        if found['shape']!=marker['shape']:changed.append(dict(id=marker['id'],expected=marker['shape'],observed=found['shape']))
    return dict(status='MEASURED_FIXTURE_MARKERS',expected=len(expected['expected_visible_markers']),observed=len(analysis['markers']),missing=missing,unexpected=remaining,shape_changes=changed,limitations='Counts refer to eligible viewport markers, not semantic nodes, edges, basins or truth.')

class Signals(QObject):done=Signal(object)
class AnalyzeTask(QRunnable):
    def __init__(self,record,image,adapter,root,previous):super().__init__();self.record=record;self.image=image;self.adapter=adapter;self.root=root;self.previous=previous;self.signals=Signals()
    def run(self):
        r=self.record
        try:
            png=encode_png(self.image);r['png_sha256']=hashlib.sha256(png).hexdigest();r['capture_status']='CAPTURED'
            (self.root/(r['frame_id']+'.png')).write_bytes(png)
            try:r['interpretation']=self.adapter.analyze(self.image) if self.adapter else dict(status='UNAVAILABLE',error='Analyzer detached; raw capture retained')
            except Exception as e:r['interpretation']=dict(status='UNAVAILABLE',error=str(e)[:500])
            r['comparison']=compare(r['intended_scene'],r['interpretation'])
            if self.previous:
                prior=QImage(str(self.root/(self.previous+'.png'))).convertToFormat(QImage.Format.Format_RGBA8888)
                now=self.image.convertToFormat(QImage.Format.Format_RGBA8888)
                r['pixel_delta']=dict(previous_frame_id=self.previous,same_dimensions=prior.size()==now.size(),changed_pixels=sum(a!=b for a,b in zip(memoryview(bytes(prior.constBits())).cast('I'),memoryview(bytes(now.constBits())).cast('I'))) if prior.size()==now.size() else None,measurement='Exact RGBA pixel difference; not a visual-match score')
        except Exception as e:r['capture_status']='ERROR';r['error']=str(e)[:500]
        try:
            (self.root/(r['frame_id']+'.json')).write_text(json.dumps(r,indent=2),encoding='utf-8')
            with (self.root/'history.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(r)+'\n')
        except Exception as e:r['storage_error']=str(e)[:500]
        self.signals.done.emit(r)

class ObservationController(QObject):
    completed=Signal(object)
    def __init__(self,viewport,root):
        super().__init__();self.viewport=viewport;self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.adapter=MarkerAnalyzer();self.enabled=True;self.busy=False;self.last_capture=0;self.history=[];self.sequence=0
        self.pool=QThreadPool(self);self.pool.setMaxThreadCount(1);self.closed=False
        history=self.root/'history.jsonl'
        if history.exists():
            # Bounded tail; incomplete/invalid final records remain on disk.
            with history.open('rb') as f:f.seek(max(0,history.stat().st_size-2_000_000));lines=f.read(2_000_000).splitlines()
            for line in lines:
                try:
                    r=json.loads(line)
                    if not re.fullmatch(r'[0-9]{8,20}-[a-f0-9]{32}',r['frame_id']) or type(r['sequence']) is not int or not 0<r['sequence']<2**63:continue
                    self.sequence=max(self.sequence,r['sequence']);self.history.append(r)
                except (ValueError,KeyError,TypeError):pass
            self.history=self.history[-200:]
        self.session=uuid.uuid4().hex
    def get_scene_snapshot(self):return self.viewport.get_scene_snapshot()
    def capture_viewport(self):
        if not self.enabled or self.busy or self.closed or time.monotonic()-self.last_capture<.5:return None
        self.last_capture=time.monotonic();self.sequence+=1;fid=f'{self.sequence:08d}-{uuid.uuid4().hex}'
        r=dict(frame_id=fid,sequence=self.sequence,session_id=self.session,captured_at_utc=utc(),captured_monotonic_ns=time.monotonic_ns(),capture_scope='LEVIS viewport widget only; off-screen widget render, not desktop scanout',intended_scene=self.get_scene_snapshot(),capture_status='PENDING',analyzer=getattr(self.adapter,'name',None))
        # grab is deliberately on the GUI thread; analysis and file IO are not.
        image=self.viewport.viewport().grab().toImage();image.setDevicePixelRatio(1)
        r['pixel_size']=[image.width(),image.height()];r['device_pixel_ratio']=self.viewport.devicePixelRatioF()
        if r['device_pixel_ratio']!=1:
            for m in r['intended_scene']['expected_visible_markers']:m['x']*=r['device_pixel_ratio'];m['y']*=r['device_pixel_ratio']
            from scene import digest
            del r['intended_scene']['source_sha256'];r['intended_scene']['source_sha256']=digest(r['intended_scene'])
        self.busy=True;previous=next((x['frame_id'] for x in reversed(self.history) if x.get('capture_status')=='CAPTURED'),None)
        self.task=AnalyzeTask(r,image,self.adapter,self.root,previous);self.task.signals.done.connect(self.finish);self.pool.start(self.task);return fid
    def finish(self,r):
        self.busy=False;self.history.append(r);self.history=self.history[-200:];self.completed.emit(r)
    def analyze_frame(self,frame_id):
        r=next(r for r in self.history if r['frame_id']==frame_id)
        return r.get('interpretation',dict(status='UNAVAILABLE',error=r.get('error','No analysis')))
    def compare_expected_observed(self,frame_id):
        r=next(r for r in self.history if r['frame_id']==frame_id)
        return r.get('comparison',dict(status='UNAVAILABLE',error=r.get('error','No comparison')))
    def get_observation_history(self):return json.loads(json.dumps(self.history))
    def close(self):self.closed=True;self.enabled=False;self.pool.waitForDone()
