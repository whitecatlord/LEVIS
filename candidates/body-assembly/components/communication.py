"""LAB candidate. Explicit dictionary compression; no model or network access."""
import copy
import hashlib
import json
import unittest

FIELDS = ['id', 'kind', 'scope', 'body', 'sources', 'lineage', 'epistemic',
          'authority', 'supersedes', 'contradicts']
VERSION = 'levis-char/0.1'

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()

def validate(record):
    if not isinstance(record, dict) or set(record) != set(FIELDS):
        raise ValueError('SCHEMA_MISMATCH')
    for key in ['id','kind','scope','body','epistemic','authority']:
        if not isinstance(record[key], str) or not record[key]:
            raise ValueError('INVALID_FIELD:' + key)
    for key in ['sources','lineage','supersedes','contradicts']:
        if not isinstance(record[key], list) or not all(isinstance(v, str) and v for v in record[key]):
            raise ValueError('INVALID_FIELD:' + key)

def encode(record):
    validate(record)
    return canonical({'v': VERSION, 'r': [record[k] for k in FIELDS], 'h': digest(record)})

def decode(packet):
    envelope = json.loads(packet)
    if set(envelope) != {'v','r','h'} or envelope['v'] != VERSION:
        raise ValueError('UNKNOWN_SCHEMA')
    if not isinstance(envelope['r'], list) or len(envelope['r']) != len(FIELDS):
        raise ValueError('SCHEMA_MISMATCH')
    record = dict(zip(FIELDS, envelope['r']))
    validate(record)
    if digest(record) != envelope['h']:
        raise ValueError('HASH_MISMATCH')
    return record

def resolve_sources(record, available):
    missing = [s for s in record['sources'] if s not in available]
    if missing:
        raise ValueError('MISSING_SOURCE:' + ','.join(missing))
    return [available[s] for s in record['sources']]

def candidate():
    return dict(id='c1', kind='claim', scope='lab', body='Memory is not authority.',
                sources=['s1'], lineage=['g1'], epistemic='source_statement',
                authority='none', supersedes=[], contradicts=[])

class TransportChecks(unittest.TestCase):
    def test_roundtrip(self):
        r = candidate()
        self.assertEqual(decode(encode(r)), r)
    def test_unicode_and_delimiters(self):
        r = candidate(); r['body'] = 'Tink 🧚 | a→b\n"quoted" é é'
        self.assertEqual(decode(encode(r)), r)
    def test_tamper_detected(self):
        p = json.loads(encode(candidate())); p['r'][3] = 'opposite claim'
        with self.assertRaisesRegex(ValueError, 'HASH_MISMATCH'): decode(canonical(p))
    def test_unknown_version(self):
        p = json.loads(encode(candidate())); p['v'] = 'future'
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_SCHEMA'): decode(canonical(p))
    def test_truncated_record(self):
        p = json.loads(encode(candidate())); p['r'].pop()
        with self.assertRaisesRegex(ValueError, 'SCHEMA_MISMATCH'): decode(canonical(p))
    def test_missing_source(self):
        with self.assertRaisesRegex(ValueError, 'MISSING_SOURCE'): resolve_sources(candidate(), {})
    def test_correction_keeps_history(self):
        old = candidate(); new = copy.deepcopy(old)
        new.update(id='c2', body='Corrected statement.', supersedes=['c1'])
        history = [decode(encode(old)), decode(encode(new))]
        self.assertEqual(history[0], old)
        self.assertEqual(history[1]['supersedes'], ['c1'])
    def test_contradiction_kept(self):
        r = candidate(); r['contradicts'] = ['c0']
        self.assertEqual(decode(encode(r))['contradicts'], ['c0'])
    def test_authority_not_upgraded(self):
        self.assertEqual(decode(encode(candidate()))['authority'], 'none')
    def test_lineage_not_multiplied(self):
        r = candidate(); r['sources'] = ['s1','s2','s3']
        self.assertEqual(len(set(decode(encode(r))['lineage'])), 1)
    def test_null_and_empty_differ(self):
        r = candidate(); r['contradicts'] = None
        with self.assertRaisesRegex(ValueError, 'INVALID_FIELD'): encode(r)
    def test_empty_body_rejected(self):
        r = candidate(); r['body'] = ''
        with self.assertRaisesRegex(ValueError, 'INVALID_FIELD'): encode(r)

if __name__ == '__main__':
    unittest.main(verbosity=2)
