"""Bounded ZIP intake: inspect in memory, never extract or execute archive members."""
import hashlib
import io
from pathlib import Path,PurePosixPath
import stat
import zipfile

MAX_ARCHIVE=64*1024*1024

def opened(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file():raise ValueError('Select an ordinary ZIP file.')
    with p.open('rb') as f:raw=f.read(MAX_ARCHIVE+1)
    if len(raw)>MAX_ARCHIVE:raise ValueError('ZIP exceeds the 64 MiB intake limit.')
    return raw,zipfile.ZipFile(io.BytesIO(raw))

def checked(z, allowed):
    infos=z.infolist()
    if len(infos)>2000:raise ValueError('ZIP has more than 2,000 entries.')
    seen=set();total=0;rows=[]
    for info in infos:
        name=info.filename
        if info.orig_filename!=name:raise ValueError("ZIP contains a normalized or truncated member name.")
        parts=PurePosixPath(name).parts
        if not name or '\\' in name or '\x00' in name or name.startswith('/') or any(p in ('..','.') or ':' in p for p in parts):raise ValueError('ZIP contains an unsafe member path.')
        key=name.rstrip('/').casefold()
        if key in seen:raise ValueError('ZIP contains duplicate or conflicting member names.')
        seen.add(key)
        mode=info.external_attr>>16
        if stat.S_ISLNK(mode):raise ValueError('ZIP symlinks are unsupported.')
        if info.flag_bits&1:raise ValueError('Encrypted ZIPs are unsupported.')
        total+=info.file_size
        if total>100*1024*1024:raise ValueError('ZIP declared content exceeds 100 MiB.')
        readable=(not info.is_dir() and PurePosixPath(name).suffix.lower() in allowed)
        if readable and (info.file_size>2*1024*1024 or info.file_size/max(info.compress_size,1)>200):raise ValueError('A text member exceeds the size/compression limit.')
        if info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):raise ValueError('Unsupported ZIP compression method.')
        if not info.is_dir():rows.append({'name':name,'bytes':info.file_size,'readable':readable,'crc32':f'{info.CRC:08x}'})
    return rows

def inspect(path,allowed):
    raw,z=opened(path)
    with z:rows=checked(z,allowed)
    return {'archive_path':str(Path(path).resolve()),'archive_sha256':hashlib.sha256(raw).hexdigest(),'members':rows}

def snapshots(path,names,expected_hash,allowed):
    if not names or len(names)!=len(set(names)):raise ValueError('Choose one or more distinct text/code members.')
    raw,z=opened(path)
    archive_hash=hashlib.sha256(raw).hexdigest()
    if archive_hash!=expected_hash:raise ValueError('ZIP changed since inspection. Choose it again.')
    result=[]
    with z:
        rows={r['name']:r for r in checked(z,allowed)}
        for name in names:
            if name not in rows or not rows[name]['readable']:raise ValueError('Only listed supported text/code members may be read.')
            with z.open(name) as f:content=f.read(2*1024*1024+1)
            if len(content)>2*1024*1024:raise ValueError('ZIP member exceeds the read limit.')
            text=content.decode('utf-8-sig')
            if '\x00' in text:raise ValueError('Binary text member is unsupported.')
            # Keep normal chunks on source line boundaries so review citations can
            # use actual file line numbers. A single exceptionally long line is
            # still split to preserve the prompt-size ceiling.
            pieces=[]; start=0; line=1
            while start<len(text):
                end=min(start+6000,len(text))
                if end<len(text):
                    boundary=text.rfind('\n',start,end)
                    if boundary>start: end=boundary+1
                piece=text[start:end]
                pieces.append((piece,start,line))
                line+=piece.count('\n');start=end
            if not pieces:pieces=[('',0,1)]
            for i,(piece,offset,line_start) in enumerate(pieces):
                result.append({'name':name,'archive_path':str(Path(path).resolve()),'archive_sha256':archive_hash,'sha256':hashlib.sha256(content).hexdigest(),'part':i+1,'parts':len(pieces),'character_offset':offset,'line_start':line_start,'text':piece})
                if len(result)>100:raise ValueError('Selection exceeds 100 small reading jobs. Select fewer files.')
    return result
