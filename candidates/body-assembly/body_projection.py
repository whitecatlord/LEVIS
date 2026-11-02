"""Passive projection of observed assembly records, never an authoritative engine."""
import math
from components.levis_modular.base import BaseRuntime,Room,ModuleSlot
from components.levis_modular.supervisor import Supervisor
from components.levis_modular.contracts import CapabilityRequest,ModuleDeclaration,ModuleOutput

class InspectionModule:
    def __init__(self,memory):self.memory=memory
    def invoke(self,capability_id,payload,input_artifact_refs):
        if capability_id!='memory.inspect' or payload or input_artifact_refs:raise ValueError('Read-only empty inspection request required')
        nodes=self.memory.nodes()
        return dict(nodes=len(nodes),sources=sum(n['kind']=='source' for n in nodes),proposals=sum(n.get('epistemic')=='PROPOSAL' for n in nodes),authority='NONE',classification='OBSERVATIONAL_MEMORY_COUNTS')
class BodyModules:
    def __init__(self,memory):
        self.base=BaseRuntime((Room('observation','Read-only assembly inspection',(ModuleSlot('memory-inspector'),)),));self.supervisor=Supervisor(self.base)
        self.provider=self.supervisor.mount('observation','memory-inspector',ModuleDeclaration('memory-inspector','1',('memory.inspect',)),InspectionModule(memory))
        self.supervisor.approve_capability('memory.inspect',self.provider,'body-inspection-v1');self.lease=self.supervisor.grant_lease(self.provider,'memory.inspect')
    def inspect(self):
        # Grant is created only by this trusted, Operator-invoked read surface.
        handle=self.supervisor.issue_work_order({'memory.inspect'})
        try:
            result=self.base.dispatch(CapabilityRequest('memory.inspect','body-inspection-v1',handle),self.supervisor)
            if not isinstance(result,ModuleOutput):raise RuntimeError(result)
            return dict(provider=result.provider_id,classification=result.response_class,payload=dict(result.payload),isolation='IN_PROCESS_PROTOTYPE_NOT_OS_SANDBOX')
        finally:self.supervisor.revoke_work_order(handle)
    def records(self):return [dict(id='memory-inspector',capability='memory.inspect',classification='READ_ONLY_IN_PROCESS_MODULE',mounted=True)]

def project(status,jobs,nodes,proposals,modules,*,available=False):
    """Bounded snapshots, explicit page/truncation metadata and source identities."""
    groups=[('Runtime',250,190,'#3be6dd',[]),('Memory',750,190,'#ad9cff',[]),('Proposals',250,530,'#f0bb65',[]),('Modules',750,530,'#3be6dd',[])]
    groups[0][4].append(dict(id='runtime',state=status.get('state','UNAVAILABLE') if status else 'DETACHED'))
    for j in (jobs or {}).get('jobs',[]):groups[0][4].append(dict(id=j['id'],state=j['display_state'],kind='job'))
    groups[1][4].extend(dict(id=n['id'],kind=n['kind'],epistemic=n.get('epistemic'),publication=n['publication']) for n in nodes[:32])
    groups[2][4].extend(dict(id=p['id'],review=p.get('review','UNKNOWN')) for p in proposals[:32])
    groups[3][4].extend(modules[:32]);render=[];edges=[];basins=[]
    for b,(title,cx,cy,color,items) in enumerate(groups):
        basins.append(dict(id=b,title=title,x=cx,y=cy,color=color,nodes=len(items)))
        for i,item in enumerate(items):
            angle=i*math.tau/max(1,len(items));r=110 if len(items)>1 else 0;ident=f'{b}-{i}'
            render.append(dict(id=ident,record_id=item['id'],record=item,x=round(cx+r*math.cos(angle),2),y=round(cy+r*.85*math.sin(angle),2),color=color,shape='circle',radius=5,basin=b))
            if i:edges.append([f'{b}-{i-1}',ident])
    if groups[1][4]:edges.append(['0-0','1-0'])
    if groups[2][4]:edges.append(['0-0','2-0'])
    if groups[3][4]:edges.append(['0-0','3-0'])
    return dict(schema=1,source='ASSEMBLY OBSERVATION PROJECTION — NOT CANONICAL BASE GEOMETRY',step=0,nodes=render,edges=edges,basins=basins,provenance=dict(runtime='Authenticated IPC snapshot' if available else 'Detached/stale; last observed records only',runtime_generation=(status or {}).get('runtime_generation'),runtime_revision=(status or {}).get('revision'),job_page_after=(jobs or {}).get('page_after',0),job_page_has_more=(jobs or {}).get('has_more',False),job_total=(jobs or {}).get('job_count'),memory_total=len(nodes),memory_visible=min(32,len(nodes)),proposal_total=len(proposals),proposal_visible=min(32,len(proposals)),modules='Local in-process prototype catalog; not process isolation',projection_relationships='Display grouping/connectivity, not inferred causal or evidential entailment'))
