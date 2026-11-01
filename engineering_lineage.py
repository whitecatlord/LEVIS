"""Portable engineering progress and bridge ledger. Python 3.12+, standard library.

Recorded assessments are attributed assertions, not independent certification.
This tool never executes a bridge or changes LEVIS source/authority.
"""
import argparse,datetime,hashlib,json,uuid
from pathlib import Path

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def digest_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def read_events(path):
    events=[];previous='0'*64
    if not path.exists():return events
    for line in path.read_text(encoding='utf-8').splitlines():
        event=json.loads(line);stored=event.pop('event_sha256')
        if event['previous_sha256']!=previous or hashlib.sha256(canonical(event)).hexdigest()!=stored:
            raise ValueError('Ledger hash-chain mismatch; preserve and reconcile the original log')
        event['event_sha256']=stored;events.append(event);previous=stored
    return events

def append(path,events,event):
    event={'event_id':str(uuid.uuid4()),'recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'previous_sha256':events[-1]['event_sha256'] if events else '0'*64,**event}
    event['event_sha256']=hashlib.sha256(canonical(event)).hexdigest()
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
    return event

def status(plan,events):
    rows=[]
    for level in plan['levels']:
        related=[e for e in events if e.get('level_id')==level['id']]
        assessments=[e for e in related if e['type']=='assessment']
        latest=assessments[-1] if assessments else None
        rows.append({'level_id':level['id'],'title':level['title'],
          'implementation':latest['implementation'] if latest else level['implementation'],
          'verification':latest['verification'] if latest else level['verification'],
          'acceptance':latest['acceptance'] if latest else level['acceptance'],
          'completion':latest['completion'] if latest else level['completion'],
          'basis':'recorded assessment; inspect evidence' if latest else 'compiled source assessment',
          'bridge_proposals':sum(e['type']=='bridge_proposal' for e in related),
          'last_event_sha256':related[-1]['event_sha256'] if related else None})
    return rows

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan',default='ENGINEERING_LEVELS.json');ap.add_argument('--ledger',default='ENGINEERING_EVENTS.jsonl')
    sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('status');sub.add_parser('verify-ledger')
    b=sub.add_parser('propose-bridge');b.add_argument('--file',required=True)
    a=sub.add_parser('record-assessment');a.add_argument('--file',required=True)
    args=ap.parse_args();plan=json.loads(Path(args.plan).read_text(encoding='utf-8'));ledger=Path(args.ledger)
    events=read_events(ledger);levels={x['id']:x for x in plan['levels']}
    if args.command=='status':print(json.dumps(status(plan,events),indent=2));return
    if args.command=='verify-ledger':print(json.dumps({'events':len(events),'hash_chain':'valid','authentication':'unsigned; no external trust anchor'}));return
    obj=json.loads(Path(args.file).read_text(encoding='utf-8'));level=levels[obj['level_id']]
    if set(obj)&{'type','event_id','recorded_at_utc','previous_sha256','event_sha256','assessment_authority','proposal_status'}:
        raise ValueError('Input cannot override reserved ledger fields')
    if args.command=='propose-bridge':
        required=['proposer','gap','source_artifacts','target_interfaces','dependencies','implementation_steps','acceptance_tests','negative_controls','rollback','authority_effect']
        for key in required:
            if key not in obj or obj[key] in ('',None,[]):raise ValueError('Missing bridge field: '+key)
        if obj['authority_effect']!='NONE':raise ValueError('Bridge proposals must have authority_effect NONE')
        event=append(ledger,events,{'type':'bridge_proposal','proposal_status':'PROPOSED_NOT_IMPLEMENTED',**obj})
    else:
        required=['assessor','artifact_sha256','implementation','verification','acceptance','completion','gate_results','evidence']
        for key in required:
            if key not in obj:raise ValueError('Missing assessment field: '+key)
        if len(obj['artifact_sha256'])!=64 or any(c not in '0123456789abcdef' for c in obj['artifact_sha256']):raise ValueError('Exact artifact SHA-256 required')
        for ev in obj['evidence']:
            if not ev.get('claim') or not ev.get('scope'):raise ValueError('Evidence requires claim and scope')
            ev['observed_sha256']=digest_file(ev['path'])
            if ev['observed_sha256']!=ev['expected_sha256']:raise ValueError('Evidence hash mismatch: '+ev['path'])
        if obj['completion']=='FINISHED_FOR_DECLARED_SCOPE':
            gates=obj['gate_results'];passed={x['gate'] for x in gates if x.get('result')=='PASS' and x.get('evidence_indices') and all(type(i) is int and 0<=i<len(obj['evidence']) for i in x['evidence_indices'])}
            if not set(level['required_gates']).issubset(passed):raise ValueError('Every planned completion gate needs passing scoped evidence')
            if obj['implementation']!='IMPLEMENTED' or obj['verification']!='PASS_FOR_DECLARED_SCOPE':raise ValueError('Finished requires implementation and scoped verification')
            if level.get('requires_acceptance') and obj['acceptance']!='EXPLICIT_ACCEPTANCE_RECORDED':raise ValueError('This level requires an explicit acceptance record')
            if not obj.get('scope'):raise ValueError('Finished requires declared scope')
        elif obj['completion'] not in {'OPEN','PARTIAL','HOLD_FOR_REPAIR','NOT_ASSESSED'}:raise ValueError('Unknown completion state')
        event=append(ledger,events,{'type':'assessment','assessment_authority':'ATTRIBUTED_ASSERTION_NOT_AUTOMATIC_CERTIFICATION',**obj})
    print(json.dumps(event,indent=2))

if __name__=='__main__':main()
