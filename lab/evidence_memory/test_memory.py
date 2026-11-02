import copy
import json
from pathlib import Path
import tempfile
import unittest
from memory import Memory,Invalid,source,note,citation,canonical,sha,parse,reconstruction,SOURCE_FIELDS,NOTE_FIELDS
from fixtures import fixture,PUBLIC


class MemoryTests(unittest.TestCase):
    def test_full_packet_roundtrip_is_exact(self):
        memory=fixture();self.assertEqual(Memory.from_packet(memory.packet()).nodes,memory.nodes)
    def test_unicode_and_citation_offsets_are_codepoints(self):
        s=source('s','🧚 é é\n"quoted" | →','origin')
        n=note('n','Exact Unicode retained.',citations=[citation(s,2,7)])
        memory=Memory([s,n]);self.assertEqual(Memory.from_packet(memory.packet()).nodes,[s,n])
        self.assertNotEqual(s['sha256'],sha(s['text'].encode('utf-8-sig')))
    def test_citation_must_match_exact_passage(self):
        s=source('s','evidence','origin');n=note('n','claim',citations=[citation(s)])
        n['citations'][0]['sha256']='0'*64
        with self.assertRaises(Invalid):Memory([s,n])
    def test_missing_source_cannot_become_complete_memory(self):
        s=source('s','evidence','origin');n=note('n','claim',citations=[citation(s)])
        with self.assertRaises(Invalid):Memory([n])
        report=reconstruction([n]);self.assertEqual(report['missing_ids'],['s']);self.assertFalse(report['complete'])
    def test_authority_upgrade_is_refused(self):
        n=note('n','A proposal');n['authority']='ROOT'
        with self.assertRaises(Invalid):Memory([n])
    def test_unsourced_source_statement_refused(self):
        with self.assertRaises(Invalid):note('n','Claimed observation',epistemic='SOURCE_STATEMENT')
    def test_three_repetitions_have_one_provenance_group(self):
        result=fixture().provenance('c2');self.assertEqual(result['provenance_group_count'],1)
        self.assertEqual(result['root_groups'],[['s1']]);self.assertEqual(result['independence_status'],'UNVERIFIED')
    def test_identical_content_with_new_origin_does_not_multiply_roots(self):
        a=source('a','identical','origin-a');b=source('b','identical','origin-b')
        n=note('n','Claim',citations=[citation(a),citation(b)])
        self.assertEqual(Memory([a,b,n]).provenance('n')['provenance_group_count'],1)
    def test_declared_shared_origin_groups_different_passages(self):
        a=source('a','first','one-study');b=source('b','second','one-study')
        n=note('n','Claim',citations=[citation(a),citation(b)])
        self.assertEqual(Memory([a,b,n]).provenance('n')['provenance_group_count'],1)
    def test_separate_roots_do_not_claim_verified_independence(self):
        a=source('a','first','origin-a');b=source('b','second','origin-b')
        n=note('n','Claim',citations=[citation(a),citation(b)])
        result=Memory([a,b,n]).provenance('n');self.assertEqual(result['provenance_group_count'],2)
        self.assertEqual(result['independence_status'],'UNVERIFIED')
    def test_shared_ancestor_dag_is_traversed_without_duplicate_roots(self):
        nodes=[source('root','root','origin')];parents=['root']
        for i in range(30):
            row=[source('a'+str(i),'a'+str(i),'a'+str(i),parents),source('b'+str(i),'b'+str(i),'b'+str(i),parents)]
            nodes.extend(row);parents=[n['id'] for n in row]
        nodes.append(note('n','Claim',citations=[citation(nodes[-1])]))
        self.assertEqual(Memory(nodes).provenance('n')['root_groups'],[['root']])
    def test_contradiction_is_retained_from_both_views(self):
        views={v['record']['id']:v for v in fixture().view()}
        self.assertEqual(views['c1']['contradicts'],['c3']);self.assertEqual(views['c3']['contradicts'],['c1'])
        self.assertEqual(views['c1']['truth_status'],'NOT_ADJUDICATED')
    def test_successor_keeps_original_and_has_no_truth_effect(self):
        views={v['record']['id']:v for v in fixture().view()}
        self.assertEqual(views['c1']['superseded_by'],['c4'])
        self.assertEqual(views['c1']['record']['body'],'Restart is PAUSED.')
        self.assertTrue(all(v['authority_effect']=='NONE' for v in views.values()))
    def test_selection_closes_over_counterevidence_and_sources(self):
        memory=fixture().select(['c1']);ids={n['id'] for n in memory.nodes}
        self.assertTrue({'c1','c3','c4','g1','s1','s4'}<=ids)
        self.assertNotIn('c2',ids)
    def test_selection_accepts_one_shot_iterator(self):
        self.assertEqual(fixture().select(iter(['c1'])).nodes,fixture().select(['c1']).nodes)
    def test_private_source_blocks_public_export_even_with_public_claim(self):
        s=source('s','private evidence','origin');n=note('n','public-looking claim',citations=[citation(s)],**PUBLIC)
        with self.assertRaises(Invalid):Memory([s,n]).packet(public=True)
    def test_private_counterevidence_cannot_be_silently_omitted(self):
        a=note('a','public proposal',**PUBLIC);b=note('b','private contradiction',relations=[dict(type='contradicts',target='a')])
        memory=Memory([a,b]).select(['a']);self.assertEqual(len(memory.nodes),2)
        with self.assertRaises(Invalid):memory.packet(public=True)
    def test_public_label_alone_is_not_export_permission(self):
        with self.assertRaises(Invalid):Memory([note('n','proposal',publication='PUBLIC')]).packet(public=True)
    def test_explicit_public_fixture_can_export(self):
        self.assertEqual(Memory.from_packet(fixture().packet(public=True)).nodes,fixture().nodes)
    def test_input_and_returned_nodes_cannot_mutate_memory(self):
        n=note('n','original');memory=Memory([n]);n['body']='changed'
        returned=memory.nodes;returned[0]['body']='also changed'
        self.assertEqual(memory.nodes[0]['body'],'original')
    def test_duplicate_ids_and_unknown_reference_refused(self):
        n=note('n','original')
        with self.assertRaises(Invalid):Memory([n,n])
        with self.assertRaises(Invalid):Memory([note('n','original',relations=[dict(type='depends_on',target='missing')])])
    def test_parent_and_relation_self_reference_refused(self):
        with self.assertRaises(Invalid):source('s','source','origin',['s'])
        with self.assertRaises(Invalid):note('n','note',relations=[dict(type='supersedes',target='n')])
    def test_citation_range_rejects_bool_and_empty(self):
        s=source('s','body','origin')
        for start,end in ((True,3),(0,0),(0,5)):
            n=note('n','note');n['citations']=[dict(source='s',start=start,end=end,sha256=sha(b'x'))]
            with self.subTest(start=start,end=end),self.assertRaises(Invalid):Memory([s,n])
    def test_packet_hash_tamper_refused(self):
        data=parse(fixture().packet());data['rows'][-1][1][3]='tampered'
        with self.assertRaises(Invalid):Memory.from_packet(canonical(data))
    def test_unknown_dictionary_or_version_refused(self):
        for change in ('version','dictionary'):
            data=parse(fixture().packet())
            if change=='version':data['v']='future'
            else:data['dictionary']['note'].reverse()
            with self.subTest(change=change),self.assertRaises(Invalid):Memory.from_packet(canonical(data))
    def test_duplicate_keys_truncation_and_nan_refused(self):
        for raw in (b'{"a":1,"a":2}',b'{',b'{"a":NaN}'):
            with self.subTest(raw=raw),self.assertRaises(Invalid):parse(raw)
    def test_immutable_log_roundtrip_and_exclusive_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ledger.jsonl';fixture().save(path)
            self.assertEqual(Memory.load(path).nodes,fixture().nodes)
            with self.assertRaises(FileExistsError):fixture().save(path)
    def test_append_successor_uses_new_snapshot_preserving_prior_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            first=Path(directory)/'first.jsonl';second=Path(directory)/'second.jsonl'
            memory=fixture();memory.save(first);before=first.read_bytes()
            memory.add(note('next','Next explicit proposal',relations=[dict(type='supersedes',target='c4')],**PUBLIC))
            memory.save(second);self.assertEqual(first.read_bytes(),before);self.assertTrue(second.read_bytes().startswith(before))
    def test_log_mutation_reorder_and_partial_write_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ledger.jsonl';fixture().save(path);raw=path.read_bytes();lines=raw.splitlines(True)
            for changed in (raw[:-1],raw.replace(b'PAUSED',b'READY',1),b''.join([lines[1],lines[0],*lines[2:]])):
                path.write_bytes(changed)
                with self.subTest(size=len(changed)),self.assertRaises(Invalid):Memory.load(path)
    def test_complete_line_truncation_requires_external_identity_anchor(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ledger.jsonl';fixture().save(path);raw=path.read_bytes();expected=sha(raw)
            path.write_bytes(b''.join(raw.splitlines(True)[:-1]))
            self.assertEqual(len(Memory.load(path).nodes),len(fixture().nodes)-1)
            with self.assertRaises(Invalid):Memory.load(path,expected_sha256=expected)
    def test_context_loss_exposes_omitted_parent_and_source(self):
        nodes=[n for n in fixture().nodes if n['id']!='s1'];report=reconstruction(nodes)
        self.assertEqual(report['missing_ids'],['s1']);self.assertFalse(report['complete'])
        self.assertIn('c1',report['unverified_citation_records'])
        self.assertIn(['c3','c1'],report['recorded_contradictions'])
    def test_partial_context_rejects_present_cycle_or_wrong_target_type(self):
        a=source('a','a','a');b=source('b','b','b',['a']);a['parents']=['b']
        with self.assertRaises(Invalid):reconstruction([a,b])
        n=note('n','note');a=source('a','a','a',['n'])
        with self.assertRaises(Invalid):reconstruction([n,a])
    def test_hypothesis_without_citations_stays_hypothesis(self):
        memory=Memory([note('n','Unknown proposition')]);result=memory.view()[0]
        self.assertEqual(result['record']['epistemic'],'HYPOTHESIS');self.assertEqual(result['provenance_group_count'],0)
    def test_missing_unreferenced_counterevidence_needs_inventory(self):
        full=fixture().nodes;partial=[n for n in full if n['id']!='c3']
        unknown=reconstruction(partial);self.assertTrue(unknown['reference_complete']);self.assertIsNone(unknown['complete'])
        known=reconstruction(partial,[n['id'] for n in full]);self.assertEqual(known['missing_ids'],['c3']);self.assertFalse(known['complete'])
    def test_extra_decoy_is_visible_against_frozen_inventory(self):
        full=fixture().nodes;expected=[n['id'] for n in full]
        result=reconstruction(full+[note('decoy','Not in original packet')],expected)
        self.assertEqual(result['unexpected_ids'],['decoy']);self.assertFalse(result['complete'])
    def test_complete_context_requires_matching_inventory(self):
        full=fixture().nodes;result=reconstruction(full,[n['id'] for n in full])
        self.assertTrue(result['complete']);self.assertEqual(result['truth_status'],'NOT_ADJUDICATED')
    def test_scope_filters_views_without_changing_saved_history(self):
        memory=Memory([note('a','first',scope='one'),note('b','second',scope='two')]);before=memory.packet()
        self.assertEqual([v['record']['id'] for v in memory.view('one')],['a']);self.assertEqual(memory.packet(),before)

if __name__=='__main__':unittest.main(verbosity=2)
