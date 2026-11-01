"""Reconstruct the public LEVIS tree from its text transfer; executes no LEVIS code."""
import argparse,json
from pathlib import Path
from restore_levis import Transfer,write_new
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('transfer');ap.add_argument('--dest',required=True)
a=ap.parse_args();t=Transfer(a.transfer);dest=Path(a.dest)
if dest.exists() and any(dest.iterdir()):raise ValueError('Destination must be new or empty')
dest.mkdir(parents=True,exist_ok=True)
for row in t.catalog['public_files']:write_new(dest,row['path'],t.blob(row['sha256']))
print(json.dumps({'restored_files':len(t.catalog['public_files']),'code_executed':False}))
