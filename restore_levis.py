"""Read a LEVIS text transfer without running its code. Standard-library Python 3.12+."""
import argparse,base64,hashlib,io,json,os,stat,zipfile
from pathlib import Path,PurePosixPath,PureWindowsPath

MAGIC=b'LEVIS-TEXT-TRANSFER v1\n'
PREFIX=b'@@LEVIS-RECORD '

class Transfer:
    def __init__(self,path):
        self.path=Path(path);self.records=[];self.blobs={};self.sections={};self.parents={};self._resolved={};self._unavailable=set()
        with self.path.open('rb') as f:
            if f.readline()!=MAGIC:raise ValueError('Unknown transfer format')
            while True:
                line=f.readline()
                if not line:break
                if not line.startswith(PREFIX):raise ValueError('Invalid record boundary at '+str(f.tell()))
                m=json.loads(line[len(PREFIX):]);offset=f.tell();self.records.append((m,offset))
                if m['type']=='blob':self.blobs[m['sha256']]=(m,offset)
                elif m['type']=='section':self.sections[m['name']]=(m,offset)
                f.seek(m['payload_bytes'],1)
                if f.read(1)!=b'\n':raise ValueError('Missing record separator')
        self.catalog=json.loads(self.section('SOURCE_CATALOG.json'))
        self.archives=self.catalog['archives']
        for ah,a in self.archives.items():
            for e in a['entries']:
                if e.get('sha256'):self.parents.setdefault(e['sha256'],[]).append((ah,e))

    def payload(self,record):
        m,offset=record
        with self.path.open('rb') as f:f.seek(offset);return f.read(m['payload_bytes'])

    def section(self,name):return self.payload(self.sections[name])

    def blob(self,h,trail=()):
        if h in self._resolved:return self._resolved[h]
        if h in self._unavailable:raise KeyError('Original container bytes not embedded: '+h)
        if h in self.blobs:
            m,offset=self.blobs[h];p=self.payload((m,offset))
            b=base64.b64decode(p,validate=False) if m['encoding']=='base64' else p
        else:
            if h in trail:raise ValueError('Cyclic archive reference')
            b=None
            for parent,e in self.parents.get(h,[]):
                if parent==h or self.archives[parent].get('format','zip')!='zip':continue
                try:
                    parent_bytes=self.blob(parent,trail+(h,))
                    with zipfile.ZipFile(io.BytesIO(parent_bytes)) as z:b=z.read(z.infolist()[e['index']])
                    break
                except (KeyError,ValueError,zipfile.BadZipFile):continue
            if b is None:
                self._unavailable.add(h)
                raise KeyError('Original container bytes not embedded: '+h)
        if hashlib.sha256(b).hexdigest()!=h:raise ValueError('SHA-256 mismatch: '+h)
        if h in self.archives:self._resolved[h]=b
        return b

    def verify(self):
        total=0
        for h in self.blobs:total+=len(self.blob(h))
        expected=set(self.catalog['embedded_blob_sha256s'])
        if expected!=set(self.blobs):raise ValueError('Embedded blob inventory mismatch')
        missing=[]
        for a in self.archives.values():
            for e in a['entries']:
                h=e.get('sha256')
                if h and h not in self.blobs and h not in self.archives and h not in self.catalog.get('omitted_blob_sha256s',{}):missing.append(h)
        if missing:raise ValueError('Missing leaf payloads: '+str(missing[:5]))
        return {'embedded_blobs':len(self.blobs),'decoded_bytes':total,'archive_maps':len(self.archives),'blob_sha256':'all matched','meaning':'transfer integrity; not runtime qualification'}

def safe_target(dest,name):
    if '\\' in name or '\x00' in name:raise ValueError('Unsafe member path: '+name)
    p=PurePosixPath(name)
    if p.is_absolute() or PureWindowsPath(name).drive or '..' in p.parts:raise ValueError('Unsafe member path: '+name)
    target=dest.joinpath(*p.parts)
    if not target.resolve().is_relative_to(dest.resolve()):raise ValueError('Path escapes destination')
    return target

def write_new(dest,name,b):
    p=safe_target(dest,name);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(b)

def restore_archive(t,h,dest,expand_nested=False):
    if dest.exists() and any(dest.iterdir()):raise ValueError('Destination must be new or empty')
    a=t.archives[h];seen=set();planned=[]
    for e in a['entries']:
        name=e['path'];safe_target(dest,name)
        key=name.casefold() if os.name=='nt' else name
        if key in seen:raise ValueError('Duplicate/colliding member; restore on a compatible filesystem: '+name)
        seen.add(key)
        if stat.S_ISLNK(e.get('external_attr',0)>>16) or e.get('member_type') in {'1','2'}:raise ValueError('Refusing archive link: '+name)
        if e.get('directory'):planned.append((name,None,None));continue
        bh=e.get('sha256')
        if not bh:raise ValueError('Member is unavailable: '+name)
        try:b=t.blob(bh);planned.append((name,b,None))
        except KeyError:
            if expand_nested and bh in t.archives:planned.append((name+'.unpacked',None,bh))
            else:raise ValueError('Historical nested container is mapped but raw bytes are not embedded. Use --expand-nested: '+name)
    dest.mkdir(parents=True,exist_ok=True)
    for name,b,nested in planned:
        if nested:restore_archive(t,nested,safe_target(dest,name),True)
        elif b is None:safe_target(dest,name).mkdir(parents=True,exist_ok=True)
        else:write_new(dest,name,b)
    return len(planned)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('transfer')
    sp=ap.add_subparsers(dest='command',required=True)
    sp.add_parser('verify');sp.add_parser('list-archives')
    r=sp.add_parser('restore-archive');r.add_argument('--sha256',required=True);r.add_argument('--dest',required=True);r.add_argument('--expand-nested',action='store_true')
    s=sp.add_parser('support');s.add_argument('--dest',required=True)
    b=sp.add_parser('blob');b.add_argument('--sha256',required=True);b.add_argument('--output',required=True)
    args=ap.parse_args();t=Transfer(args.transfer)
    if args.command=='verify':print(json.dumps(t.verify(),indent=2))
    elif args.command=='list-archives':
        for h,a in t.archives.items():print(h,a.get('format','zip'),a['source_example'])
    elif args.command=='restore-archive':print(json.dumps({'members':restore_archive(t,args.sha256,Path(args.dest),args.expand_nested),'code_executed':False}))
    elif args.command=='support':
        dest=Path(args.dest)
        if dest.exists() and any(dest.iterdir()):raise ValueError('Destination must be new or empty')
        dest.mkdir(parents=True,exist_ok=True)
        for name in t.sections:
            if name!='SOURCE_CATALOG.json':write_new(dest,name,t.section(name))
        print('Support files restored. No LEVIS code executed.')
    elif args.command=='blob':
        p=Path(args.output)
        with p.open('xb') as f:f.write(t.blob(args.sha256))
        print('Blob hash verified and bytes saved.')

if __name__=='__main__':main()
