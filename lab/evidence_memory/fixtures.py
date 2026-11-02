"""Synthetic, explicitly exportable fixtures; no personal conversations."""
from memory import Memory,source,note,citation
PUBLIC=dict(publication='PUBLIC',export_allowed=True)


def fixture():
    root=source('s1','The coordinator restarts PAUSED. Draft output remains unverified.','synthetic-spec',license='SYNTHETIC_FIXTURE',**PUBLIC)
    a=source('s2','The runtime comes back paused.','synthetic-summary-a',['s1'],license='SYNTHETIC_FIXTURE',**PUBLIC)
    b=source('s3','On restart the runtime is paused.','synthetic-summary-b',['s1'],license='SYNTHETIC_FIXTURE',**PUBLIC)
    other=source('s4','Alternative proposal: restart READY.','synthetic-counterproposal',license='SYNTHETIC_FIXTURE',**PUBLIC)
    first=note('c1','Restart is PAUSED.',citations=[citation(root)],epistemic='SOURCE_STATEMENT',**PUBLIC)
    repeated=note('c2','Three passages repeat one requirement.',citations=[citation(root),citation(a),citation(b)],epistemic='SOURCE_STATEMENT',**PUBLIC)
    opposed=note('c3','Consider restart READY instead.',citations=[citation(other)],epistemic='PROPOSAL',relations=[dict(type='contradicts',target='c1')],**PUBLIC)
    correction=note('c4','Clarification: this is a requirement statement, not proof of a qualified runtime.',kind='view',citations=[citation(root)],relations=[dict(type='supersedes',target='c1')],**PUBLIC)
    gap=note('g1','Target Windows qualification is not included in this synthetic fixture.',kind='gap',epistemic='UNKNOWN',relations=[dict(type='depends_on',target='c4')],**PUBLIC)
    return Memory([root,a,b,other,first,repeated,opposed,correction,gap])
