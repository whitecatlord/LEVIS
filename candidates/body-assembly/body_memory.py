"""Private observational memory, exclusive GUI writer, immutable lab snapshots.

This is not canonical Base state or a second runtime SQLite writer.
"""
import hashlib,json,re,threading,uuid,os
from pathlib import Path
from PySide6.QtCore import QLockFile
from scoped_files import ordinary
from components.evidence_memory import Memory,Invalid,source,note,citation,canonical,sha
from components import communication

class BodyMemory:
    def __init__(self,root):
        self.root=Path(root).absolute();self.root.mkdir(parents=True,exist_ok=True)
        for part in [self.root,*self.root.parents]:ordinary(part)
        self.writer=QLockFile(str(self.root/'memory-writer.lock'));self.writer.setStaleLockTime(0)
        if not self.writer.tryLock(0):raise RuntimeError('Observational memory already has a GUI writer')
        self.guard=threading.RLock();self.memory=Memory();self.head=None
        try:
            head=self.root/'HEAD.json'
            if head.exists():
                ordinary(head)
                with head.open('rb') as f:raw=f.read(2049)
                if len(raw)>2048:raise Invalid('HEAD_SIZE')
                self.head=json.loads(raw)
                if set(self.head)!={'sequence','file','sha256','previous_sha256'} or type(self.head['sequence']) is not int or not 0<self.head['sequence']<2**63 or not re.fullmatch(r'memory_[0-9]{8,20}_[a-f0-9]{32}\.jsonl',self.head['file']):raise Invalid('HEAD_SHAPE')
                for key in ['sha256','previous_sha256']:
                    if not re.fullmatch('[0-9a-f]{64}',self.head[key]):raise Invalid('HEAD_HASH')
                path=self.root/self.head['file'];ordinary(path);self.memory=Memory.load(path,expected_sha256=self.head['sha256'])
        except BaseException:self.writer.unlock();raise
    def close(self):self.writer.unlock()
    def nodes(self):
        with self.guard:return self.memory.nodes
    def _commit(self,candidate):
        seq=(self.head['sequence'] if self.head else 0)+1;name=f'memory_{seq:08d}_{uuid.uuid4().hex}.jsonl';path=self.root/name
        candidate.save(path)
        head=dict(sequence=seq,file=name,sha256=sha(path.read_bytes()),previous_sha256=self.head['sha256'] if self.head else '0'*64)
        target=self.root/'HEAD.json'
        if target.exists():ordinary(target)
        temp=self.root/(uuid.uuid4().hex+'.tmp')
        with temp.open('xb') as f:f.write(canonical(head));f.flush();os.fsync(f.fileno())
        temp.replace(target);self.head=head;self.memory=candidate;return dict(head=head,nodes=len(candidate.nodes),authority='NONE',publication='PRIVATE')
    def add_nodes(self,nodes):
        with self.guard:
            existing={n['id']:n for n in self.memory.nodes};additions=[]
            for n in nodes:
                if n['id'] in existing:
                    if n!=existing[n['id']]:raise Invalid('IMPORT_CONFLICT')
                else:additions.append(n);existing[n['id']]=n
            if not additions:return dict(head=self.head,nodes=len(existing),idempotent=True,authority='NONE')
            return self._commit(Memory(self.memory.nodes+additions))
    def remember_chunk(self,chunk):
        text=chunk['text']
        if not isinstance(text,str) or len(text)>65536:raise Invalid('CHUNK_LIMIT')
        metadata={k:chunk[k] for k in ['name','offset','next_offset','size','chunk_sha256','classification']}
        ident=sha(canonical(metadata)+text.encode())[:32];root=source('chunk_meta_'+ident,canonical(metadata).decode(),'selected-source-preview')
        pieces=[source('chunk_'+ident+'_'+str(i),text[start:start+64000],'selected-preview-'+ident,parents=[root['id']]) for i,start in enumerate(range(0,len(text),64000))]
        if not pieces:pieces=[source('chunk_'+ident+'_0','','selected-preview-'+ident,parents=[root['id']])]
        view=note('chunk_note_'+ident,'Selected text preview; byte-chunk identity and UTF-8 replacement classification are retained. This is not full-file ingestion or verified source truth.',scope='selected-sources',kind='view',citations=[citation(n) for n in pieces if n['text']],epistemic='UNKNOWN')
        return self.add_nodes([root,*pieces,view])
    def remember_draft(self,job,artifact):
        if job['state']!='DRAFT_READY' or job['completed'] is not True or not job['artifacts']:raise Invalid('NO_COMPLETED_DRAFT')
        latest=job['artifacts'][-1]
        if (artifact.get('kind')!='draft' or latest['kind']!='draft' or artifact.get('integrity')!='VALID' or latest['integrity']!='VALID' or artifact.get('attempt')!=latest['attempt'] or artifact.get('sha256')!=latest['sha256'] or type(artifact.get('text')) is not str or sha(artifact['text'].encode())!=artifact['sha256'] or artifact.get('provider')!=latest['provider']):raise Invalid('DRAFT_INTEGRITY')
        ident=artifact['attempt'];src=source('draft_src_'+ident,artifact['text'],'draft-job-'+job['id'])
        provider=source('provider_'+ident,canonical(artifact['provider']).decode(),'configured-provider-'+ident)
        proposal=note('draft_note_'+ident,'Unverified draft for: '+job['goal'],scope='draft-proposals',kind='view',citations=([citation(src)] if src['text'] else [])+[citation(provider)],epistemic='PROPOSAL')
        gap=note('draft_gap_'+ident,'Original input bindings and authorization SID are not exposed by this artifact observation API. Provider records describe configuration, not atomic model weight attestation.',scope='draft-proposals',kind='gap',epistemic='UNKNOWN',relations=[dict(type='depends_on',target=proposal['id'])])
        return self.add_nodes([src,provider,proposal,gap])
    def export_private(self):
        with self.guard:
            packet=self.memory.packet(public=False)
            record=dict(id='memory_'+str(self.head['sequence'] if self.head else 0),kind='memory-packet',scope='private-observational',body=packet.decode(),sources=[n['id'] for n in self.memory.nodes if n['kind']=='source'],lineage=[self.head['sha256']] if self.head else [],epistemic='UNVERIFIED_MEMORY_SNAPSHOT',authority='NONE',supersedes=[],contradicts=[])
            transport=communication.encode(record).encode();decoded=communication.decode(transport.decode());restored=Memory.from_packet(decoded['body'].encode())
            if restored.nodes!=self.memory.nodes:raise Invalid('ROUND_TRIP_FAILED')
            directory=self.root/'exports'
            if directory.exists():ordinary(directory)
            else:directory.mkdir()
            path=directory/(uuid.uuid4().hex+'.json')
            with path.open('xb') as f:f.write(transport);f.flush();os.fsync(f.fileno())
            return dict(file=str(path),sha256=sha(transport),nodes=len(restored.nodes),round_trip=True,publication='PRIVATE',authority='NONE',formats=[communication.VERSION,'levis-memory/1'])
    def remember_observation(self,record,png):
        if record.get('capture_status')!='CAPTURED' or sha(png)!=record.get('png_sha256'):raise Invalid('OBSERVATION_IMAGE_INTEGRITY')
        body=canonical(record).decode();ident=sha(body.encode())[:32]
        src=source('observation_'+ident,body,'own-viewport-capture')
        view=note('observation_note_'+ident,'Actual viewport capture and bounded pixel interpretation. Intended scene is separate from observed image. No general model vision or semantic confidence is implied.',scope='self-observation',kind='view',citations=[citation(src)],epistemic='UNKNOWN')
        return self.add_nodes([src,view])
