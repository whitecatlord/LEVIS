"""Explicit-root, bounded read-only sources and save-new proposal drafts."""
import hashlib,json,os,stat,uuid
from pathlib import Path
MAX_FILE=5*1024**3
CHUNK=64*1024
def ordinary(path):
    info=path.lstat()
    if path.is_symlink() or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):raise ValueError('Linked/reparse paths refused')
    return info
class ScopedFiles:
    def __init__(self,root):
        self.root=Path(root).absolute()
        for part in [self.root,*self.root.parents]:ordinary(part)
        if not self.root.is_dir():raise ValueError('Select an ordinary folder')
    def resolve(self,name):
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts or ':' in str(name) or not rel.parts:raise ValueError('Relative scoped path required')
        current=self.root
        for part in rel.parts:current=current/part;ordinary(current)
        if not current.resolve().is_relative_to(self.root.resolve()):raise ValueError('Outside scope')
        return current
    def page(self,offset=0,limit=100):
        if type(offset)is not int or offset<0 or limit!=100:raise ValueError('Invalid catalog page')
        rows=[];skipped=0;more=False
        with os.scandir(self.root) as entries:
            for entry in entries:
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):continue
                try:info=ordinary(Path(entry.path))
                except (OSError,ValueError):continue
                if skipped<offset:skipped+=1;continue
                if len(rows)==limit:more=True;break
                rows.append(dict(name=entry.name,bytes=info.st_size))
        return dict(rows=rows,next_offset=offset+len(rows),has_more=more,ordering='Filesystem order; changing catalogs may move page boundaries')
    def read(self,name,offset=0):
        if type(offset)is not int or offset<0:raise ValueError('Nonnegative byte offset required')
        path=self.resolve(name)
        with path.open('rb') as f:
            info=os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_FILE:raise ValueError('Ordinary files up to 5 GiB only')
            f.seek(offset);raw=f.read(CHUNK)
        return dict(name=name,offset=offset,next_offset=offset+len(raw),size=info.st_size,text=raw.decode('utf-8',errors='replace'),chunk_sha256=hashlib.sha256(raw).hexdigest(),truncated=offset+len(raw)<info.st_size,classification='UNTRUSTED_SOURCE_TEXT; UTF-8 replacement preview; hash covers exact chunk bytes')
    def save_proposal(self,text,source=None):
        if not isinstance(text,str) or len(text)>128_000:raise ValueError('Draft limit 128,000 characters')
        # Creates a fresh draft directory; never overwrites a selected source.
        folder=self.root/'.levis-drafts'
        if folder.exists():ordinary(folder)
        else:folder.mkdir()
        ident=uuid.uuid4().hex;raw=text.encode();draft=folder/(ident+'.txt')
        with draft.open('xb') as f:f.write(raw)
        proposal=dict(id=ident,status='PROPOSED_NOT_APPROVED',source=source,draft=draft.name,sha256=hashlib.sha256(raw).hexdigest(),rationale='Operator saved draft for review',affected_files=[source['name']] if source else [],tests='NOT_RUN',approval='NOT_GRANTED',authority_effect='NONE')
        with (folder/(ident+'.json')).open('x',encoding='utf-8') as f:json.dump(proposal,f,indent=2)
        return proposal
