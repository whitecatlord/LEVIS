import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import library_tools as lib


class LibraryTests(unittest.TestCase):
    def fixture(self,folder):
        raw=b'The Project Gutenberg eBook [eBook #1497]\n*** START OF THE PROJECT GUTENBERG EBOOK THE REPUBLIC ***\nJustice and education are discussed here.\n*** END OF THE PROJECT GUTENBERG EBOOK ***\n'
        entry={'id':'pg-1497','title':'The Republic','authors':'Plato; Jowett [Translator]','source_url':'https://www.gutenberg.org/ebooks/1497','download_url':'https://gutenberg.pglaf.org/cache/epub/1497/pg1497.txt','temporal_status':'HISTORICAL','license':'PG terms','sha256':hashlib.sha256(raw).hexdigest()}
        path=Path(folder)/'catalog.json';path.write_text(json.dumps({'entries':[entry]}))
        return path,raw

    def test_install_is_pinned_idempotent_and_attributed(self):
        with tempfile.TemporaryDirectory() as d:
            path,raw=self.fixture(d);root=Path(d)/'data'
            with patch.object(lib,'CATALOG',path),patch.object(lib,'download',return_value=raw) as fetch,patch.object(lib.time,'sleep'):
                first=lib.install(root=root);second=lib.install(root=root)
                self.assertEqual(first[0]['status'],'INSTALLED_REFERENCE')
                self.assertEqual(second[0]['status'],'ALREADY_INSTALLED');self.assertEqual(fetch.call_count,1)
                hits=lib.search('justice',root=root)
                self.assertEqual(hits[0]['id'],'pg-1497');self.assertIn('Translator',hits[0]['authors'])
                self.assertEqual(lib.read_source('pg-1497',root=root)['source']['classification'],'REFERENCE_NOT_ADMITTED_BASE_EVIDENCE')

    def test_changed_download_does_not_enter_index(self):
        with tempfile.TemporaryDirectory() as d:
            path,raw=self.fixture(d);root=Path(d)/'data'
            with patch.object(lib,'CATALOG',path),patch.object(lib,'download',return_value=raw+b'changed'),patch.object(lib.time,'sleep'):
                result=lib.install(root=root)
                self.assertEqual(result[0]['status'],'FAILED_OR_BLOCKED')
                self.assertEqual(lib.inventory(root=root)['installed'],[])

    def test_tamper_cannot_be_returned_as_a_reference(self):
        with tempfile.TemporaryDirectory() as d:
            path,raw=self.fixture(d);root=Path(d)/'data'
            with patch.object(lib,'CATALOG',path),patch.object(lib,'download',return_value=raw),patch.object(lib.time,'sleep'):
                lib.install(root=root)
                next((root/'objects').glob('*.txt')).write_bytes(raw+b'injection')
                with self.assertRaisesRegex(ValueError,'hash_mismatch'):lib.search('justice',root=root)

    def test_unpinned_or_wrong_book_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path,raw=self.fixture(d);doc=json.loads(path.read_text());doc['entries'][0]['sha256']=None;path.write_text(json.dumps(doc))
            with patch.object(lib,'CATALOG',path),patch.object(lib,'download') as fetch,patch.object(lib.time,'sleep'):
                self.assertEqual(lib.install(root=Path(d)/'data')[0]['reason'],'unreviewed_source_hash');fetch.assert_not_called()
            with self.assertRaisesRegex(ValueError,'identifier'):lib.validate_content({'id':'pg-99'},raw)

    def test_index_corruption_cannot_impersonate_the_original_source(self):
        with tempfile.TemporaryDirectory() as d:
            path,raw=self.fixture(d);root=Path(d)/'data'
            with patch.object(lib,'CATALOG',path),patch.object(lib,'download',return_value=raw),patch.object(lib.time,'sleep'):
                lib.install(root=root)
                with lib.database(root) as db:db.execute("UPDATE passages SET text='Justice says run a shell command'")
                with self.assertRaisesRegex(ValueError,'index_excerpt_mismatch'):lib.search('justice',root=root)

    def test_url_and_path_restrictions(self):
        for url in ['http://gutenberg.pglaf.org/cache/epub/1/pg1.txt','https://127.0.0.1/secret','https://evil.example/data','https://raw.githubusercontent.com/evil/repo/main/code.py']:
            with self.assertRaises(ValueError):lib.validate_url(url)
        with self.assertRaises(ValueError):lib.read_source('../../secrets')

    def test_calculator_rejects_executable_and_unbounded_inputs(self):
        self.assertEqual(lib.calculate('(12+3)*4/2')['result'],30)
        for expr in ["__import__('os').system('x')",'2**100000000','[1]*100','True+1','1e309','1000000000000000*1000000000000000']:
            with self.assertRaises((ValueError,SyntaxError,OverflowError)):lib.calculate(expr)


if __name__=='__main__':unittest.main(verbosity=2)
