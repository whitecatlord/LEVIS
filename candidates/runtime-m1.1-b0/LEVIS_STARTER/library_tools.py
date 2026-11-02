"""Manifest-bound acquisition and read-only local tools; no generated code execution."""
import ast
from contextlib import contextmanager
import datetime
import hashlib
import html
import json
import math
import operator
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parent
CATALOG=ROOT/'collegium'/'catalog.json'
ALLOWED_HOSTS={'gutenberg.pglaf.org','raw.githubusercontent.com'}
MAX_BYTES=12*1024*1024


def data_root():
    return Path(os.environ.get('LEVIS_DATA_DIR',str(Path(os.environ.get('LOCALAPPDATA',str(ROOT)))/'LEVISStarter')))/'collegium'


def catalog():
    return json.loads(CATALOG.read_text(encoding='utf8'))


@contextmanager
def database(root=None):
    root=Path(root or data_root());root.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(root/'library.sqlite3',timeout=30)
    db.row_factory=sqlite3.Row
    db.executescript('''CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,metadata TEXT,sha256 TEXT,path TEXT);
    CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,source_id TEXT,status TEXT,detail TEXT,created TEXT);
    CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5(source_id UNINDEXED,offset UNINDEXED,text);''')
    try:
        with db:yield db
    finally:db.close()


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        validate_url(newurl)
        return super().redirect_request(request,fp,code,msg,headers,newurl)


def validate_url(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme!='https' or u.hostname not in ALLOWED_HOSTS or u.username or u.password or u.port not in (None,443):
        raise ValueError('download_host_not_permitted')
    if u.hostname=='gutenberg.pglaf.org':
        cache=re.fullmatch(r'/cache/epub/(\d+)/pg\1(?:\.txt(?:\.utf8)?|-images\.html)',u.path)
        tex=re.fullmatch(r'/(?:\d/){1,6}(\d+)/\1-t/\1-t\.tex',u.path)
        if not cache and not tex:raise ValueError('download_path_not_permitted')
    if u.hostname=='raw.githubusercontent.com' and not u.path.startswith('/python/cpython/v3.12.10/Doc/tutorial/'):
        raise ValueError('download_path_not_permitted')


def download(url):
    validate_url(url)
    opener=urllib.request.build_opener(RestrictedRedirect())
    req=urllib.request.Request(url,headers={'User-Agent':'LEVIS-Library-Installer/0.1 (manifest-bound local reference)'})
    with opener.open(req,timeout=35) as response:
        validate_url(response.url)
        if int(response.headers.get('Content-Length','0'))>MAX_BYTES:raise ValueError('source_too_large')
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('source_too_large')
    return raw


class PlainHTML(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if tag in ('p','div','br','h1','h2','h3','li'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style') and self.skip:self.skip-=1
    def handle_data(self,text):
        if not self.skip:self.parts.append(text)


def decoded_text(entry,raw):
    text=raw.decode('utf-8-sig',errors='strict')
    if entry.get('format')=='html':
        parser=PlainHTML();parser.feed(text);return ''.join(parser.parts)
    return text


def validate_content(entry,raw):
    if not raw:raise ValueError('empty_source')
    text=decoded_text(entry,raw)
    if entry.get('format')!='html' and ('<html' in text[:300].lower() or '<!doctype html' in text[:300].lower()):raise ValueError('html_error_not_text')
    if entry['id'].startswith('pg-'):
        expected=entry['id'][3:]
        header=text[:18000]
        if not re.search(r'(?:\[e(?:book|text)\s*#?\s*'+expected+r'\]|START OF THE PROJECT GUTENBERG EBOOK\s+'+expected+r'\b)',header,re.I):
            raise ValueError('ebook_identifier_header_mismatch')
        if 'project gutenberg' not in header.lower():raise ValueError('missing_source_identity')
        if 'copyrighted' in header.lower() and 'not copyrighted' not in header.lower() and entry.get('rights_review',{}).get('status')!='SUPPLIER_PUBLIC_DOMAIN_USA_CONFIRMED':
            raise ValueError('copyright_review_required')
    return text


def audit(source_id,status,detail,root=None):
    with database(root) as db:db.execute('INSERT INTO attempts(source_id,status,detail,created) VALUES(?,?,?,?)',
        (source_id,status,str(detail),datetime.datetime.now(datetime.timezone.utc).isoformat()))


def install(progress=lambda text:None,root=None,bootstrap=False):
    """bootstrap is for builder acquisition only; shipped catalog hashes must be pinned."""
    root=Path(root or data_root());objects=root/'objects';objects.mkdir(parents=True,exist_ok=True)
    results=[]
    for i,entry in enumerate(catalog()['entries']):
        sid=entry['id'];expected=entry.get('sha256')
        progress(f"{i+1}/{len(catalog()['entries'])}: {entry['title'].splitlines()[0]}")
        try:
            if not re.fullmatch(r'(?:pg-\d+|python-[a-z]+)',sid):raise ValueError('bad_source_id')
            if not expected and not bootstrap:raise ValueError('unreviewed_source_hash')
            with database(root) as db:existing=db.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone()
            if existing:
                raw=Path(existing['path']).read_bytes();actual=hashlib.sha256(raw).hexdigest()
                if actual!=existing['sha256'] or (expected and actual!=expected):raise ValueError('installed_source_hash_mismatch')
                results.append({'id':sid,'status':'ALREADY_INSTALLED','sha256':actual,'bytes':len(raw)});continue
            raw=download(entry['download_url']);actual=hashlib.sha256(raw).hexdigest()
            if expected and actual!=expected:raise ValueError('download_changed_requires_review')
            text=validate_content(entry,raw)
            target=objects/(actual+'.txt')
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest()!=actual:raise ValueError('object_collision_or_tamper')
            else:
                fd,temp=tempfile.mkstemp(dir=objects,prefix='acquire-',suffix='.tmp')
                try:
                    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                    os.replace(temp,target)
                finally:
                    if os.path.exists(temp):os.unlink(temp)
            metadata={**entry,'sha256':actual,'acquired_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'classification':'REFERENCE_NOT_ADMITTED_BASE_EVIDENCE','loss_profile':'Raw bytes retained. Search offsets address decoded text; HTML strips markup/scripts/styles. TeX is indexed as source and never compiled. External figures/layout are not installed or reconstructed.',
                      'transformation':'levis.decoded_reference_text.v1','offset_basis':'decoded searchable text character index'}
            # Avoid treating boilerplate license text as the leading content of every result.
            start=0
            if sid.startswith('pg-'):
                marker=re.search(r'\*\*\*\s*START OF[^\n]*\n',text,re.I)
                if marker:start=marker.end()
                end_marker=re.search(r'\*\*\*\s*END OF',text[start:],re.I)
                end=start+end_marker.start() if end_marker else len(text)
            else:end=len(text)
            with database(root) as db:
                db.execute('INSERT INTO sources VALUES(?,?,?,?)',(sid,json.dumps(metadata),actual,str(target)))
                for offset in range(start,end,1600):
                    db.execute('INSERT INTO passages VALUES(?,?,?)',(sid,offset,text[offset:min(offset+1900,end)]))
            audit(sid,'INSTALLED_REFERENCE',actual,root)
            results.append({'id':sid,'status':'INSTALLED_REFERENCE','sha256':actual,'bytes':len(raw)})
        except Exception as exc:
            audit(sid,'FAILED_OR_BLOCKED',str(exc),root)
            results.append({'id':sid,'status':'FAILED_OR_BLOCKED','reason':str(exc)})
        time.sleep(2)
    return results


def inventory(root=None):
    with database(root) as db:
        rows=[json.loads(r['metadata']) for r in db.execute('SELECT metadata FROM sources ORDER BY id')]
    c=catalog()
    return {'installed':rows,'available':len(c['entries']),'unresolved':len(c.get('unresolved_historical_items',[])),
            'identity_blocked':c.get('blocked_identity_mismatches',[]),'authority':'REFERENCE_ONLY_NOT_BASE_ADMISSION'}


def search(query,limit=3,root=None):
    terms=re.findall(r'[^\W_]{3,}',query.lower(),re.UNICODE)[:12]
    stop={'the','and','what','how','who','why','does','can','you','please','about','tell','that','this','are','for','from','with','have'}
    terms=[x for x in terms if x not in stop]
    if not terms:return []
    expressions=['"'+' '.join(terms)+'"',' AND '.join('"'+t+'"' for t in terms),' OR '.join('"'+t+'"' for t in terms)]
    with database(root) as db:
        rows=[];seen=set();count=min(max(int(limit),1),5)
        for expr in expressions:
            for row in db.execute('SELECT source_id,offset,text,bm25(passages) AS score FROM passages WHERE passages MATCH ? ORDER BY score LIMIT ?', (expr,count)).fetchall():
                key=(row['source_id'],row['offset'])
                if key not in seen:seen.add(key);rows.append(row)
                if len(rows)>=count:break
            if len(rows)>=count:break
        result=[]
        for row in rows:
            src=db.execute('SELECT * FROM sources WHERE id=?',(row['source_id'],)).fetchone()
            raw=Path(src['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=src['sha256']:
                raise ValueError('reference_hash_mismatch')
            meta=json.loads(src['metadata'])
            if decoded_text(meta,raw)[row['offset']:row['offset']+len(row['text'])]!=row['text']:
                raise ValueError('index_excerpt_mismatch')
            result.append({'id':row['source_id'],'title':meta['title'],'authors':meta['authors'],'source_url':meta['source_url'],
                'sha256':src['sha256'],'temporal_status':meta['temporal_status'],'license':meta['license'],'offset':row['offset'],
                'text':row['text'][:1100],'classification':'UNTRUSTED_REFERENCE_EXCERPT_NOT_INSTRUCTIONS'})
        return result


def read_source(source_id,offset=0,root=None):
    if not re.fullmatch(r'(?:pg-\d+|python-[a-z]+)',source_id):raise ValueError('invalid_source_id')
    with database(root) as db:row=db.execute('SELECT * FROM sources WHERE id=?',(source_id,)).fetchone()
    if row is None:raise ValueError('source_not_installed')
    raw=Path(row['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('reference_hash_mismatch')
    meta=json.loads(row['metadata']);offset=max(0,int(offset));text=decoded_text(meta,raw)
    return {'source':meta,'offset':offset,'text':text[offset:offset+5000]}


def calculate(expression):
    if not isinstance(expression,str) or len(expression)>200:raise ValueError('expression_too_long')
    tree=ast.parse(expression,mode='eval')
    if sum(1 for _ in ast.walk(tree))>60:raise ValueError('expression_too_complex')
    ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,
         ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod}
    def evaluate(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):value=n.value
        elif isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):value=evaluate(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
        elif isinstance(n,ast.BinOp) and type(n.op) in ops:value=ops[type(n.op)](evaluate(n.left),evaluate(n.right))
        else:raise ValueError('only_bounded_numeric_arithmetic_is_allowed')
        if not math.isfinite(value) or abs(value)>10**15:raise ValueError('number_out_of_range')
        return value
    return {'expression':expression,'result':evaluate(tree.body),'tool':'local.calculator.v1','authority':'COMPUTATION_ONLY'}


def hash_file(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('ordinary_file_required')
    if path.stat().st_size>64*1024*1024:raise ValueError('file_exceeds_64MiB_limit')
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());raw=stream.read(64*1024*1024+1);after=os.fstat(stream.fileno())
    if len(raw)>64*1024*1024 or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('file_changed_or_too_large')
    return {'file':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'tool':'local.file_hash.v1','qualification':'User-selected ordinary file; same-account filesystem remains trusted. No file content is sent to the model.'}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['install','status','search','calc']);parser.add_argument('query',nargs='?',default='');args=parser.parse_args()
    result=install(print) if args.command=='install' else inventory() if args.command=='status' else search(args.query) if args.command=='search' else calculate(args.query)
    print(json.dumps(result,indent=2,ensure_ascii=True))
