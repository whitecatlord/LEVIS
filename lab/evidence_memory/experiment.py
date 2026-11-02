"""Synthetic deterministic reconstruction controls; no model or token claims."""
import argparse
import copy
from pathlib import Path
from fixtures import fixture,PUBLIC
from memory import Memory,note,canonical,parse,sha,reconstruction


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    memory=fixture();nodes=memory.nodes;expected=[n['id'] for n in nodes]
    packet=memory.packet(public=True)
    restored=Memory.from_packet(packet)
    assert restored.nodes==nodes
    variants={
        'full':(nodes,[],[]),
        'root_source_removed':([n for n in nodes if n['id']!='s1'],['s1'],[]),
        'counterproposal_removed':([n for n in nodes if n['id']!='c3'],['c3'],[]),
        'correction_removed':([n for n in nodes if n['id']!='c4'],['c4'],[]),
        'decoy_added':(nodes+[note('decoy','Unrelated synthetic hypothesis',**PUBLIC)],[],['decoy']),
    }
    results=[]
    for name,(available,missing,unexpected) in variants.items():
        report=reconstruction(available,expected)
        assert report['missing_ids']==missing and report['unexpected_ids']==unexpected
        results.append(dict(condition=name,**report))
    full=canonical(nodes)
    dictionary=canonical(parse(packet)['dictionary'])
    report=dict(status='DETERMINISTIC_FIXTURE_CONTROLS_PASS',independent_model_trials='NOT_RUN',model_tokens=None,
                full_json_bytes=len(full),compact_packet_bytes=len(packet),dictionary_bytes=len(dictionary),
                compact_includes_dictionary=True,compact_to_full_byte_ratio=len(packet)/len(full),
                exact_roundtrip=True,shared_origin_groups=memory.provenance('c2'),conditions=results,
                authority_effect='NONE',semantic_entailment='NOT_TESTED',clinical_claim='NONE')
    (output/'fixture_full.json').write_bytes(full+b'\n')
    (output/'fixture_compact.json').write_bytes(packet+b'\n')
    memory.save(output/'fixture_ledger.jsonl')
    (output/'views.json').write_bytes(canonical(memory.view())+b'\n')
    (output/'report.json').write_bytes(canonical(report)+b'\n')
    print(canonical(report).decode())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
