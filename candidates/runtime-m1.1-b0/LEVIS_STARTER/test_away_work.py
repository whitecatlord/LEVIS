import tempfile,unittest,json
from pathlib import Path
from away_work import Jobs
class AwayTests(unittest.TestCase):
 def test_snapshot_and_draft_never_modify_original(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'code.py';p.write_text('print(1)')
   q=Jobs(Path(d)/'jobs');jid=q.add('Improve code',[p]);p.write_text('print(2)')
   q.run_one(lambda j:{'kind':'draft','text':json.loads(j['snapshot'])[0]['text']})
   self.assertEqual(p.read_text(),'print(2)');self.assertIn('print(1)',Path(q.rows()[0]['result']).read_text());self.assertEqual(q.rows()[0]['state'],'DRAFT_READY')
 def test_questions_resume_and_restart_interrupts(self):
  with tempfile.TemporaryDirectory() as d:
   q=Jobs(d);jid=q.add('Need clarification',[]);q.run_one(lambda j:{'kind':'question','text':'Which version?'})
   self.assertEqual(q.rows()[0]['state'],'NEEDS_ANSWER');q.update(jid,'RUNNING');self.assertEqual(Jobs(d).rows()[0]['state'],'INTERRUPTED')
 def test_invalid_and_oversize_are_refused(self):
  with tempfile.TemporaryDirectory() as d:
   q=Jobs(Path(d)/'jobs');p=Path(d)/'large.py';p.write_text('a'*10001)
   with self.assertRaises(ValueError):q.add('Read',[p])
   q.add('Draft',[]);q.run_one(lambda j:{'kind':'execute','text':'cmd.exe'})
   self.assertEqual(q.rows()[0]['state'],'FAILED');self.assertFalse(list((Path(d)/'jobs').glob('*/draft.md')))
if __name__=='__main__':unittest.main()
