"""Disposable fake-adapter demonstration; no saved user profile or model."""
import json
from pathlib import Path
import tempfile
import time
from draft_store import DraftStore, digest
from draft_lane import DraftLane


def main():
    with tempfile.TemporaryDirectory(prefix='LEVIS-draft-lab-') as directory:
        store=DraftStore(Path(directory)/'profile',create=True)
        lane=DraftLane(store,lambda claim,cancel:dict(kind='draft',text='FAKE ADAPTER DRAFT: '+claim['goal']))
        try:
            source='print("source remains data")'
            payload=dict(goal='Suggest an improvement without running source',inputs=[dict(name='sample.py',text=source,sha256=digest(source.encode()))],authorization=dict(operator='demo-harness',scope='DRAFT_ONLY'))
            revision=store.call('snapshot')['revision']
            job=store.call('submit',payload,revision=revision)['result']['job']
            lane.start()
            print(json.dumps(dict(stage='submitted',paused=store.call('snapshot')['paused'],job=job)))
            lane.control('resume')
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                snapshot=store.call('snapshot')
                if snapshot['jobs'][0]['completed']:
                    break
                if lane.last_error:
                    raise RuntimeError(lane.last_error)
                time.sleep(.01)
            else:
                raise TimeoutError('fake adapter demonstration did not complete')
            outcome=snapshot['jobs'][0]
            artifact=store.call('artifact',dict(attempt=outcome['artifacts'][0]['attempt']))
            print(json.dumps(dict(stage='committed',state=outcome['display_state'],artifact=artifact,source_input=source,model_enabled=False,executor_enabled=False)))
        finally:
            result=lane.stop(timeout=5)
            if result['state']!='STOPPED':
                raise RuntimeError(str(result))
            store.close()


if __name__=='__main__':main()
