"""Read-only LAB bridge from a committed draft observation to proposal memory.

The caller supplies an already authorized store object. This is no external
identity verifier or source-entailment checker, and grants no execution rights.
"""
from memory import Memory,Invalid,source,note,citation,sha


def import_verified_draft(memory,store,job_id):
    after=0
    job=None
    while True:
        snapshot=store.call('snapshot',dict(after=after,limit=25))
        job=next((row for row in snapshot['jobs'] if row['id']==job_id),None)
        if job is not None or not snapshot['has_more']:break
        after=snapshot['next_cursor']
    if job is None:raise Invalid('UNKNOWN_DRAFT_JOB')
    if job['state']!='DRAFT_READY' or job['completed'] is not True or not job['artifacts']:
        raise Invalid('NO_VERIFIED_COMPLETED_DRAFT')
    latest=job['artifacts'][-1]
    artifact=store.call('artifact',dict(attempt=latest['attempt']))
    if (latest['kind']!='draft' or latest['integrity']!='VALID' or artifact['kind']!='draft' or
            artifact['integrity']!='VALID' or artifact['attempt']!=latest['attempt'] or
            artifact['sha256']!=latest['sha256'] or type(artifact['text']) is not str or
            sha(artifact['text'].encode('utf-8'))!=artifact['sha256']):
        raise Invalid('DRAFT_ARTIFACT_INTEGRITY')
    source_id='draft_src_'+artifact['attempt']
    proposal_id='draft_note_'+artifact['attempt']
    src=source(source_id,artifact['text'],'draft-job-'+job_id)
    proposal=note(proposal_id,'Unverified draft for: '+job['goal'],scope='draft-proposals',kind='view',
                  citations=[citation(src)],epistemic='PROPOSAL')
    # Original input/model provenance is not exposed by this observation API.
    # Do not invent source parents or verified independent evidence.
    gap_id='draft_gap_'+artifact['attempt']
    gap=note(gap_id,'Original input bindings, model identity and authorization record are not exposed by this observation API.',scope='draft-proposals',kind='gap',epistemic='UNKNOWN',relations=[dict(type='depends_on',target=proposal_id)])
    existing={node['id']:node for node in memory.nodes}
    additions=[]
    for candidate in (src,proposal,gap):
        if candidate['id'] in existing:
            if existing[candidate['id']]!=candidate:raise Invalid('DRAFT_IMPORT_CONFLICT')
        else:additions.append(candidate)
    result=Memory(memory.nodes+additions)
    return result,dict(source=source_id,proposal=proposal_id,gap=gap_id,classification='UNVERIFIED_DRAFT_PROPOSAL',
                       original_input_provenance='NOT_EXPOSED_BY_OBSERVATION_API',authority_effect='NONE')
