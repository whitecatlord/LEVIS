"""LAB evidence-memory contracts: exact provenance, never inferred authority.

No model, network, source acquisition, execution or Base admission route.
Snapshots are immutable files; this is not a shared append-writer service.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

VERSION = 'levis-memory/1'
SOURCE_FIELDS = ('id','kind','text','sha256','origin','license','parents','publication','export_allowed')
NOTE_FIELDS = ('id','kind','scope','body','citations','epistemic','authority','relations','publication','export_allowed')
MAX_BYTES = 8*1024*1024
MAX_NODES = 256


class Invalid(ValueError):
    pass


def canonical(value):
    try:
        return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    except (ValueError,TypeError,UnicodeError,RecursionError) as error:
        raise Invalid('INVALID_JSON_VALUE') from error


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    if type(raw) is not bytes or len(raw)>MAX_BYTES:
        raise Invalid('PACKET_SIZE_LIMIT')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:
                raise Invalid('DUPLICATE_KEY')
            result[key]=value
        return result
    def invalid(value):
        raise Invalid('NONFINITE_VALUE')
    try:
        result=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
    except (ValueError,UnicodeError,RecursionError) as error:
        raise Invalid('INVALID_JSON') from error
    def bounded(value,depth=0):
        if depth>16:
            raise Invalid('NESTING_LIMIT')
        if type(value) is dict:
            if len(value)>32:
                raise Invalid('OBJECT_LIMIT')
            for child in value.values():bounded(child,depth+1)
        elif type(value) is list:
            if len(value)>MAX_NODES:
                raise Invalid('ARRAY_LIMIT')
            for child in value:bounded(child,depth+1)
    bounded(result)
    return result


def fields(value,names):
    if type(value) is not dict or set(value)!=set(names):
        raise Invalid('UNKNOWN_FIELDS')


def identifier(value):
    if type(value) is not str or re.fullmatch('[A-Za-z0-9_-]{1,64}',value) is None:
        raise Invalid('INVALID_ID')


def text(value,limit,empty=False):
    if type(value) is not str or len(value)>limit or (not empty and not value.strip()) or '\x00' in value:
        raise Invalid('INVALID_TEXT')
    canonical(value)


def references(value,limit):
    if type(value) is not list or len(value)>limit:
        raise Invalid('REFERENCE_LIMIT')
    for item in value:identifier(item)
    if len(value)!=len(set(value)):
        raise Invalid('DUPLICATE_REFERENCE')


def validate_node(node):
    if type(node) is not dict:
        raise Invalid('INVALID_NODE')
    source=node.get('kind')=='source'
    fields(node,SOURCE_FIELDS if source else NOTE_FIELDS)
    identifier(node['id'])
    if node['publication'] not in ('PRIVATE','PUBLIC') or type(node['export_allowed']) is not bool:
        raise Invalid('PUBLICATION_FIELDS')
    if source:
        text(node['text'],64000,empty=True)
        text(node['origin'],128);text(node['license'],256)
        references(node['parents'],32)
        if node['sha256']!=sha(node['text'].encode('utf-8')):
            raise Invalid('SOURCE_HASH_MISMATCH')
        if node['id'] in node['parents']:
            raise Invalid('SELF_REFERENCE')
        return
    if node['kind'] not in ('claim','view','gap','boundary'):
        raise Invalid('UNKNOWN_KIND')
    text(node['scope'],128);text(node['body'],16000)
    if node['epistemic'] not in ('SOURCE_STATEMENT','HYPOTHESIS','PROPOSAL','UNKNOWN'):
        raise Invalid('UNKNOWN_EPISTEMIC')
    if node['authority']!='NONE':
        raise Invalid('AUTHORITY_UPGRADE_REFUSED')
    if type(node['citations']) is not list or len(node['citations'])>16:
        raise Invalid('CITATION_LIMIT')
    seen=set()
    for citation in node['citations']:
        fields(citation,('source','start','end','sha256'))
        identifier(citation['source'])
        if type(citation['start']) is not int or type(citation['end']) is not int or not 0<=citation['start']<citation['end']<=64000:
            raise Invalid('INVALID_CITATION_RANGE')
        if type(citation['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',citation['sha256']) is None:
            raise Invalid('INVALID_CITATION_HASH')
        key=(citation['source'],citation['start'],citation['end'])
        if key in seen:raise Invalid('DUPLICATE_CITATION')
        seen.add(key)
    if type(node['relations']) is not list or len(node['relations'])>32:
        raise Invalid('RELATION_LIMIT')
    seen=set()
    for relation in node['relations']:
        fields(relation,('type','target'))
        identifier(relation['target'])
        if relation['type'] not in ('contradicts','supersedes','depends_on'):
            raise Invalid('UNKNOWN_RELATION')
        key=(relation['type'],relation['target'])
        if relation['target']==node['id'] or key in seen:
            raise Invalid('INVALID_RELATION')
        seen.add(key)
    if not node['citations'] and node['epistemic']=='SOURCE_STATEMENT':
        raise Invalid('UNSOURCED_STATEMENT')


def source(identity,body,origin,parents=(),*,license='UNKNOWN',publication='PRIVATE',export_allowed=False):
    node=dict(id=identity,kind='source',text=body,sha256=sha(body.encode('utf-8')),origin=origin,license=license,
              parents=list(parents),publication=publication,export_allowed=export_allowed)
    validate_node(node)
    return node


def citation(node,start=0,end=None):
    if node.get('kind')!='source':raise Invalid('SOURCE_REQUIRED')
    end=len(node['text']) if end is None else end
    result=dict(source=node['id'],start=start,end=end,sha256=sha(node['text'][start:end].encode('utf-8')))
    return result


def note(identity,body,*,scope='lab',kind='claim',citations=(),relations=(),epistemic='HYPOTHESIS',publication='PRIVATE',export_allowed=False):
    node=dict(id=identity,kind=kind,scope=scope,body=body,citations=copy.deepcopy(list(citations)),
              epistemic=epistemic,authority='NONE',relations=copy.deepcopy(list(relations)),
              publication=publication,export_allowed=export_allowed)
    validate_node(node)
    return node


class Memory:
    def __init__(self,nodes=()):
        self._nodes=[]
        self._by_id={}
        for node in nodes:self.add(node)

    @property
    def nodes(self):
        return copy.deepcopy(self._nodes)

    def add(self,node):
        candidate=parse(canonical(node))
        validate_node(candidate)
        if len(self._nodes)>=MAX_NODES:raise Invalid('NODE_COUNT_LIMIT')
        if candidate['id'] in self._by_id:raise Invalid('DUPLICATE_ID')
        if candidate['kind']=='source':
            for parent in candidate['parents']:
                if parent not in self._by_id or self._by_id[parent]['kind']!='source':
                    raise Invalid('MISSING_SOURCE_PARENT')
        else:
            for cite in candidate['citations']:
                target=self._by_id.get(cite['source'])
                if target is None or target['kind']!='source':raise Invalid('MISSING_SOURCE')
                if cite['end']>len(target['text']) or sha(target['text'][cite['start']:cite['end']].encode('utf-8'))!=cite['sha256']:
                    raise Invalid('CITATION_MISMATCH')
            for relation in candidate['relations']:
                if relation['target'] not in self._by_id or self._by_id[relation['target']]['kind']=='source':
                    raise Invalid('MISSING_NOTE_TARGET')
        if len(canonical(self._nodes+[candidate]))>MAX_BYTES:
            raise Invalid('MEMORY_SIZE_LIMIT')
        self._nodes.append(candidate)
        self._by_id[candidate['id']]=candidate

    def _roots(self,source_id):
        pending=[source_id];visited=set();roots=set()
        while pending:
            identity=pending.pop()
            if identity in visited:continue
            visited.add(identity)
            node=self._by_id[identity]
            if node['parents']:pending.extend(node['parents'])
            else:roots.add(identity)
        return roots

    def provenance(self,record_id):
        if record_id not in self._by_id:raise Invalid('UNKNOWN_RECORD')
        node=self._by_id[record_id]
        roots=set()
        sources=[record_id] if node['kind']=='source' else [c['source'] for c in node['citations']]
        for identity in sources:roots.update(self._roots(identity))
        # Equal content OR a declared shared origin collapses conservative groups.
        groups=[{identity} for identity in sorted(roots)]
        changed=True
        while changed:
            changed=False
            for i in range(len(groups)):
                for j in range(i+1,len(groups)):
                    if any(self._by_id[a]['origin']==self._by_id[b]['origin'] or self._by_id[a]['sha256']==self._by_id[b]['sha256'] for a in groups[i] for b in groups[j]):
                        groups[i].update(groups.pop(j));changed=True;break
                if changed:break
        return dict(root_groups=[sorted(group) for group in groups],provenance_group_count=len(groups),independence_status='UNVERIFIED')

    def view(self,scope=None):
        result=[]
        for node in self._nodes:
            if node['kind']=='source' or (scope is not None and node['scope']!=scope):continue
            contradictions=set();superseded_by=[]
            for other in self._nodes:
                if other['kind']=='source':continue
                for relation in other['relations']:
                    if relation['type']=='contradicts' and (other['id']==node['id'] or relation['target']==node['id']):
                        contradictions.add(relation['target'] if other['id']==node['id'] else other['id'])
                    if relation['type']=='supersedes' and relation['target']==node['id']:superseded_by.append(other['id'])
            result.append(dict(record=copy.deepcopy(node),contradicts=sorted(contradictions),superseded_by=sorted(superseded_by),
                               **self.provenance(node['id']),authority_effect='NONE',truth_status='NOT_ADJUDICATED'))
        return result

    def select(self,identities):
        identities=list(identities)
        references(identities,MAX_NODES)
        wanted=set(identities)
        if not wanted<=set(self._by_id):raise Invalid('UNKNOWN_SELECTION')
        changed=True
        while changed:
            before=set(wanted)
            for node in self._nodes:
                if node['id'] in wanted:
                    if node['kind']=='source':wanted.update(node['parents'])
                    else:
                        wanted.update(c['source'] for c in node['citations'])
                        wanted.update(r['target'] for r in node['relations'])
                elif node['kind']!='source' and any(r['target'] in wanted and (r['type'] in ('contradicts','supersedes') or (node['kind']=='gap' and r['type']=='depends_on')) for r in node['relations']):
                    wanted.add(node['id'])
            changed=wanted!=before
        return Memory(node for node in self._nodes if node['id'] in wanted)

    def packet(self,*,public=False):
        if public and any(n['publication']!='PUBLIC' or n['export_allowed'] is not True for n in self._nodes):
            raise Invalid('PUBLIC_EXPORT_NOT_AUTHORIZED')
        rows=[['s' if n['kind']=='source' else 'n',[n[key] for key in (SOURCE_FIELDS if n['kind']=='source' else NOTE_FIELDS)]] for n in self._nodes]
        raw=canonical(dict(v=VERSION,dictionary=dict(source=list(SOURCE_FIELDS),note=list(NOTE_FIELDS)),rows=rows,sha256=sha(canonical(self._nodes))))
        if len(raw)>MAX_BYTES:raise Invalid('PACKET_SIZE_LIMIT')
        return raw

    @classmethod
    def from_packet(cls,raw):
        data=parse(raw)
        fields(data,('v','dictionary','rows','sha256'))
        if data['v']!=VERSION or data['dictionary']!=dict(source=list(SOURCE_FIELDS),note=list(NOTE_FIELDS)):
            raise Invalid('UNKNOWN_SCHEMA')
        if type(data['rows']) is not list:raise Invalid('INVALID_ROWS')
        nodes=[]
        for row in data['rows']:
            if type(row) is not list or len(row)!=2 or row[0] not in ('s','n') or type(row[1]) is not list:
                raise Invalid('INVALID_ROW')
            keys=SOURCE_FIELDS if row[0]=='s' else NOTE_FIELDS
            if len(row[1])!=len(keys):raise Invalid('ROW_LENGTH')
            node=dict(zip(keys,row[1]))
            if (node.get('kind')=='source')!=(row[0]=='s'):raise Invalid('ROW_KIND')
            nodes.append(node)
        if sha(canonical(nodes))!=data['sha256']:raise Invalid('PACKET_HASH_MISMATCH')
        return cls(nodes)

    def save(self,path):
        previous='0'*64
        lines=[]
        for sequence,node in enumerate(self._nodes,1):
            event=dict(sequence=sequence,previous=previous,node=node)
            previous=sha(canonical(event))
            lines.append(canonical(dict(**event,sha256=previous))+b'\n')
        raw=b''.join(lines)
        if len(raw)>MAX_BYTES:raise Invalid('LOG_SIZE_LIMIT')
        import os
        with Path(path).open('xb') as output:
            output.write(raw);output.flush();os.fsync(output.fileno())

    @classmethod
    def load(cls,path,*,expected_sha256=None):
        with Path(path).open('rb') as source_file:raw=source_file.read(MAX_BYTES+1)
        if expected_sha256 is not None and sha(raw)!=expected_sha256:raise Invalid('LOG_IDENTITY_MISMATCH')
        if len(raw)>MAX_BYTES or (raw and not raw.endswith(b'\n')):raise Invalid('TRUNCATED_OR_OVERSIZE_LOG')
        result=cls();previous='0'*64
        for sequence,line in enumerate(raw.splitlines(),1):
            event=parse(line)
            fields(event,('sequence','previous','node','sha256'))
            if type(event['sequence']) is not int or event['sequence']!=sequence or event['previous']!=previous:
                raise Invalid('LOG_SEQUENCE_MISMATCH')
            expected=sha(canonical({k:event[k] for k in ('sequence','previous','node')}))
            if expected!=event['sha256']:raise Invalid('LOG_HASH_MISMATCH')
            previous=expected;result.add(event['node'])
        return result


def reconstruction(nodes,expected_ids=None):
    """Inspect a deliberately incomplete context; do not fabricate missing nodes."""
    if type(nodes) is not list or len(nodes)>MAX_NODES:raise Invalid('NODE_COUNT_LIMIT')
    by_id={}
    for node in nodes:
        validate_node(node)
        if node['id'] in by_id:raise Invalid('DUPLICATE_ID')
        by_id[node['id']]=node
    order={node['id']:index for index,node in enumerate(nodes)}
    missing=set();unverified=[];contradictions=[]
    for node in nodes:
        if node['kind']=='source':
            missing.update(p for p in node['parents'] if p not in by_id)
            if any(p in by_id and (by_id[p]['kind']!='source' or order[p]>=order[node['id']]) for p in node['parents']):
                raise Invalid('INVALID_PARENT_GRAPH')
        else:
            for cite in node['citations']:
                target=by_id.get(cite['source'])
                if target is None:
                    missing.add(cite['source']);unverified.append(node['id'])
                elif target['kind']!='source' or order[cite['source']]>=order[node['id']] or cite['end']>len(target['text']) or sha(target['text'][cite['start']:cite['end']].encode())!=cite['sha256']:
                    raise Invalid('CITATION_MISMATCH')
            for relation in node['relations']:
                if relation['target'] not in by_id:missing.add(relation['target'])
                elif by_id[relation['target']]['kind']=='source' or order[relation['target']]>=order[node['id']]:raise Invalid('INVALID_RELATION_GRAPH')
                if relation['type']=='contradicts':contradictions.append([node['id'],relation['target']])
    reference_complete=not missing
    inventory_complete=None
    unexpected=[]
    if expected_ids is not None:
        references(expected_ids,MAX_NODES)
        expected=set(expected_ids)
        missing.update(expected-set(by_id))
        unexpected=sorted(set(by_id)-expected)
        inventory_complete=not (expected-set(by_id) or unexpected)
    complete=False if not reference_complete else inventory_complete
    return dict(available_ids=sorted(by_id),missing_ids=sorted(missing),unexpected_ids=unexpected,unverified_citation_records=sorted(set(unverified)),
                recorded_contradictions=contradictions,authority_effect='NONE',reference_complete=reference_complete,inventory_complete=inventory_complete,
                complete=complete,truth_status='NOT_ADJUDICATED')
