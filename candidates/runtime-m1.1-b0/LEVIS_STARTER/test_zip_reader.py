import hashlib,json,tempfile,unittest,zipfile,stat
from pathlib import Path
import zip_reader
from away_work import Jobs,ALLOWED
class ZipTests(unittest.TestCase):
 def make(self,d,entries):
  p=Path(d)/'code.zip'
  with zipfile.ZipFile(p,'w',zipfile.ZIP_STORED) as z:
   for name,text in entries:
    info=zipfile.ZipInfo(name);info.filename=name;z.writestr(info,text)
  return p
 def test_code_chunk_snapshot_provenance_and_no_extraction(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.make(d,[('project/main.py','a'*6001),('binary.exe',b'\x00'),('nested.zip',b'zip')]);index=zip_reader.inspect(p,ALLOWED)
   self.assertEqual([r['readable'] for r in index['members']],[True,False,False])
   q=Jobs(Path(d)/'jobs');ids=q.add_zip('Review this source',p,['project/main.py'],index['archive_sha256'])
   self.assertEqual(len(ids),2);parts=[json.loads(r['snapshot'])[0] for r in q.rows()]
   self.assertEqual(''.join(r['text'] for r in parts),'a'*6001)
   self.assertEqual(parts[1]['character_offset'],6000);self.assertEqual(parts[0]['archive_sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
   self.assertFalse((Path(d)/'project').exists())
 def test_traversal_duplicate_and_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   for name in ('../evil.py','C:/evil.py','/evil.py','a\\evil.py'):
    p=self.make(d,[(name,'x')])
    with self.assertRaises(ValueError):zip_reader.inspect(p,ALLOWED)
   p=self.make(d,[('A.py','x'),('a.py','y')])
   with self.assertRaises(ValueError):zip_reader.inspect(p,ALLOWED)
   p=Path(d)/'link.zip';info=zipfile.ZipInfo('link.py');info.external_attr=(stat.S_IFLNK|0o777)<<16
   with zipfile.ZipFile(p,'w') as z:z.writestr(info,'target')
   with self.assertRaises(ValueError):zip_reader.inspect(p,ALLOWED)
 def test_changed_archive_and_binary_text_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.make(d,[('a.py','x')]);index=zip_reader.inspect(p,ALLOWED);self.make(d,[('a.py','y')])
   with self.assertRaises(ValueError):zip_reader.snapshots(p,['a.py'],index['archive_sha256'],ALLOWED)
   p=self.make(d,[('binary.py',b'\x00')]);index=zip_reader.inspect(p,ALLOWED)
   q=Jobs(Path(d)/'jobs')
   with self.assertRaises(ValueError):q.add_zip('Read',p,['binary.py'],index['archive_sha256'])
   self.assertEqual(q.rows(),[])
 def test_bomb_and_corrupt_archives_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bomb.zip'
   with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('a.py','a'*100000)
   with self.assertRaises(ValueError):zip_reader.inspect(p,ALLOWED)
   p.write_bytes(b'broken')
   with self.assertRaises(zipfile.BadZipFile):zip_reader.inspect(p,ALLOWED)
 def test_atomic_batch_rejects_excessive_jobs(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.make(d,[('a.py','a'*606001)]);index=zip_reader.inspect(p,ALLOWED);q=Jobs(Path(d)/'jobs')
   with self.assertRaises(ValueError):q.add_zip('Read',p,['a.py'],index['archive_sha256'])
   self.assertEqual(q.rows(),[])
if __name__=='__main__':unittest.main()
