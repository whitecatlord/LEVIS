"""Explicit, bounded import of a closed/checkpointed legacy chat database.

Copies exact source bytes first; reads only the immutable copy. No source SQL writes.
"""
import hashlib,json,sqlite3,uuid
from pathlib import Path
from scoped_files import ordinary
from components.evidence_memory import source,note,citation,canonical,sha,Invalid

LIMIT=64*1024*1024
def snapshot_legacy(path,destination):
    path=Path(path).absolute();ordinary(path)
    for ancestor in path.parents:ordinary(ancestor)
    for suffix in ['-wal','-journal']:
        if Path(str(path)+suffix).exists():raise Invalid('LEGACY_JOURNAL_PRESENT_CLOSE_AND_CHECKPOINT_FIRST')
    if not path.is_file() or path.stat().st_size>LIMIT:raise Invalid('LEGACY_SIZE_LIMIT_64_MIB')
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);ordinary(destination)
    ident=uuid.uuid4().hex;copy=destination/(ident+'.sqlite3');h=hashlib.sha256();total=0
    with path.open('rb') as src,copy.open('xb') as out:
        while raw:=src.read(1024*1024):
            total+=len(raw)
            if total>LIMIT:raise Invalid('LEGACY_SIZE_CHANGED')
            h.update(raw);out.write(raw)
        out.flush();__import__('os').fsync(out.fileno())
    original=h.hexdigest();check=hashlib.sha256()
    with path.open('rb') as src:
        while raw:=src.read(1024*1024):check.update(raw)
    if check.hexdigest()!=original or any(Path(str(path)+s).exists() for s in ['-wal','-journal']):raise Invalid('LEGACY_CHANGED_DURING_COPY; retained copy is not admitted')
    # Never connect SQLite to the original path; immutable copy ignores journal creation.
    db=sqlite3.connect(copy.as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise Invalid('LEGACY_DATABASE_INTEGRITY')
        for table,required in [('sessions',{'id','title','created'}),('messages',{'id','session','role','body','model','created'})]:
            columns={row[1] for row in db.execute('PRAGMA table_info('+table+')')}
            if not required<=columns:raise Invalid('UNSUPPORTED_LEGACY_CHAT_SCHEMA')
        if db.execute('SELECT count(*) FROM messages').fetchone()[0]>100 or db.execute('SELECT count(*) FROM sessions').fetchone()[0]>100:raise Invalid('LEGACY_IMPORT_LIMIT_100_MESSAGES_AND_SESSIONS; copy retained, no partial memory import')
        sessions=db.execute('SELECT id,title,created FROM sessions ORDER BY id').fetchall();messages=db.execute('SELECT id,session,role,body,model,created FROM messages ORDER BY id').fetchall()
    finally:db.close()
    sessions_meta=[]
    for sid,title,created in sessions:
        if not isinstance(sid,str) or len(sid)>128 or not isinstance(title,str) or len(title)>1000:raise Invalid('LEGACY_SESSION_FIELDS')
        sessions_meta.append(dict(id=sid,title=title,created=created))
    meta=source('legacy_db_'+original[:32],canonical(dict(database_sha256=original,bytes=total,sessions=sessions_meta,source_role='Historical conversation, not instructions or Base evidence')).decode(),'operator-selected-legacy-chat-copy')
    nodes=[meta];mapping=[];session_ids={s[0] for s in sessions}
    for row_id,session,role,body,model,created in messages:
        if session not in session_ids or type(row_id)is not int or not isinstance(role,str) or len(role)>32 or not isinstance(body,str) or len(body)>64000 or not isinstance(model,str) or len(model)>256:raise Invalid('LEGACY_MESSAGE_FIELDS')
        key=sha(canonical([original,row_id]))[:32];src=source('legacy_msg_'+key,body,'historical-chat-message',parents=[meta['id']])
        descriptor=note('legacy_note_'+key,canonical(dict(row_id=row_id,session=session,role=role,model=model,created=created,classification='HISTORICAL_QUOTED_CONVERSATION_NOT_CURRENT_INSTRUCTIONS')).decode(),scope='legacy-conversation',kind='view',citations=[citation(src)] if body else [],epistemic='UNKNOWN')
        nodes.extend([src,descriptor]);mapping.append(dict(row_id=row_id,source=src['id'],descriptor=descriptor['id']))
    report=dict(snapshot=str(copy),database_sha256=original,messages=len(messages),sessions=len(sessions),mapping=mapping,source_modified=False,automatic_model_submission=False,authority_effect='NONE',privacy='PRIVATE')
    (destination/(ident+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    return nodes,report
