"""Passive fixture scene. No runtime state or geometric truth is inferred here."""
import copy, hashlib, json, math
from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem

COLORS=['#3be6dd','#f0bb65','#ad9cff']
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def fixture(step=0):
    nodes=[];edges=[];basins=[]
    for b,(cx,cy,count,title) in enumerate([(250,200,18,'Infrastructure'),(760,220,11,'Proposals'),(500,490,14,'Evidence')]):
        ids=[]
        for i in range(count):
            angle=i*math.tau/count+b*.4
            radius=105 if i%2 else 155
            node=dict(id=f'{b}-{i}',x=round(cx+radius*math.cos(angle),2),y=round(cy+radius*.72*math.sin(angle)+step*(i%3-1)*5,2),color=COLORS[b],shape='circle',radius=5,basin=b)
            nodes.append(node);ids.append(node['id'])
            if i:edges.append([ids[i-1],ids[i]])
        edges.append([ids[-1],ids[0]])
        for i in range(count//2):edges.append([ids[i],ids[(i+4)%count]])
        basins.append(dict(id=b,title=title,x=cx,y=cy,color=COLORS[b],nodes=count))
    edges.extend([['0-0','1-5'],['1-2','2-0'],['2-5','0-6']])
    while len(edges)<72:edges.append([f'0-{len(edges)%18}',f'2-{len(edges)%14}'])
    return dict(schema=1,source='DETERMINISTIC TEST FIXTURE — NOT LIVE ENGINE',step=step,nodes=nodes,edges=edges,basins=basins)

class WorldView(QGraphicsView):
    inspected=Signal(str)
    def __init__(self):
        super().__init__();self.setScene(QGraphicsScene(self));self.setSceneRect(0,0,1000,660)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor('#07151d'));self.setMinimumSize(324,234)
        self.layers={k:True for k in ['Nodes','Edges','Basins','Fields','Plates']}
        self.data=fixture();self.faults={};self.zoom=1.;self.render_scene()
        self.scene().selectionChanged.connect(self.selection)
    def selection(self):
        items=self.scene().selectedItems()
        if items:self.inspected.emit(str(items[0].data(0)))
    def render_scene(self):
        s=self.scene();s.clear();data=self.data;lookup={n['id']:n for n in data['nodes']}
        if self.layers['Fields']:
            for y in range(0,801,40):s.addLine(0,y,1000,y,QPen(QColor('#102934'),.7))
            for x in range(0,1001,40):s.addLine(x,0,x,800,QPen(QColor('#102934'),.7))
        for b in data['basins']:
            if self.layers['Basins']:
                color=QColor(b['color']);color.setAlpha(25)
                path=QPainterPath();path.addEllipse(QPointF(b['x'],b['y']),195,148)
                outline=QColor(b['color']);outline.setAlpha(100)
                s.addPath(path,QPen(outline,1),QBrush(color))
                label=s.addText(f"{b['title'].upper()}  /  {b['nodes']} NODES");label.setDefaultTextColor(QColor('#a5bac9'));label.setPos(b['x']-150,b['y']-180)
            if self.layers['Plates']:
                s.addRect(b['x']-120,b['y']-90,240,180,QPen(QColor('#244350'),1,Qt.PenStyle.DashLine))
        if self.layers['Edges']:
            for a,b in data['edges']:
                a,b=lookup[a],lookup[b];s.addLine(a['x'],a['y'],b['x'],b['y'],QPen(QColor('#327481'),1.4))
        if self.layers['Nodes']:
            for n in data['nodes']:
                shape=self.faults.get(n['id'],n['shape'])
                if shape=='hidden':continue
                r=n['radius'];args=(-r,-r,r*2,r*2,QPen(Qt.PenStyle.NoPen),QBrush(QColor(n['color'])))
                item=s.addRect(*args) if shape=='rectangle' else s.addEllipse(*args)
                item.setPos(n['x'],n['y']);item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable);item.setData(0,json.dumps(n,indent=2));item.setToolTip(n['id'])
    def fit(self):self.fitInView(self.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio);self.zoom=1.
    def wheelEvent(self,event):
        factor=1.15 if event.angleDelta().y()>0 else 1/1.15
        if .2<self.zoom*factor<8:self.scale(factor,factor);self.zoom*=factor
    def get_scene_snapshot(self):
        result=copy.deepcopy(self.data);result['layers']=dict(self.layers);result['viewport']=[self.viewport().width(),self.viewport().height()]
        marks=[]
        if self.layers['Nodes']:
            for n in self.data['nodes']:
                p=self.mapFromScene(QPointF(n['x'],n['y']))
                if 10<p.x()<self.viewport().width()-10 and 10<p.y()<self.viewport().height()-10:
                    marks.append(dict(id=n['id'],x=p.x(),y=p.y(),shape=n['shape'],color=n['color']))
        result['expected_visible_markers']=marks
        result['transform']=[self.transform().m11(),self.transform().m22(),self.horizontalScrollBar().value(),self.verticalScrollBar().value()]
        result['source_sha256']=digest(result);return result
    def set_step(self,step):self.data=fixture(step);self.render_scene()
