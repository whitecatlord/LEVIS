"""Synthetic integrated local-model smoke, new output folder only."""
import argparse,json,sys,time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from assemble import ensure_runtime,_children
from runtime_client import Client
from body_workbench import BodyWorkbench
from scoped_files import ScopedFiles

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--adapter',choices=['fake','ollama'],default='fake');args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    app=QApplication([]);result=ensure_runtime(args.output,args.adapter);process=_children[result['pid']];client=Client(Path(result['profile']),'body-smoke');window=None
    def wait(fn,seconds=150):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            app.processEvents();QTest.qWait(100)
            if fn():return
        raise TimeoutError('Integrated smoke timed out')
    try:
        window=BodyWorkbench(args.output/'workbench',Path(result['profile']));window.resize(1366,768);window.show();wait(lambda:window.jobs is not None and not window.pending)
        fixtures=args.output/'synthetic-inputs';fixtures.mkdir();(fixtures/'roles.txt').write_text('Synthetic roles: Aster proposes, Birch reviews, Cedar archives. Nothing is executed.',encoding='utf-8')
        window.last_source=ScopedFiles(fixtures).read('roles.txt');window.remember_chunk();wait(lambda:not window.memory_busy)
        window.goal.setPlainText('Draft a brief summary preserving these roles and the no-execution boundary.');window.include_source.setChecked(True);window.authorize.setChecked(True);window.submit();wait(lambda:not window.pending);window.control('resume');wait(lambda:not window.pending)
        def terminal():
            jobs=client.request('jobs')['draft']['jobs'];return bool(jobs and jobs[0]['state'] not in ('QUEUED','RUNNING'))
        wait(terminal);window.refresh_runtime();wait(lambda:not window.pending);job=window.jobs['jobs'][0]
        if not job['completed']:raise RuntimeError(job)
        window.job_table.selectRow(0);window.remember_job();wait(lambda:not window.memory_busy);window.refresh_world();window.world.fit();window.observer.last_capture=0;window.observer.capture_viewport();wait(lambda:not window.observer.busy)
        frame=window.observer.history[-1];window.remember_observation();wait(lambda:not window.memory_busy);packet=window.body_memory.export_private();module=window.modules.inspect();artifact=client.request('job-artifact',payload=dict(attempt=job['artifacts'][-1]['attempt']))['draft']
        window.nav.setCurrentRow(1);window.world.fit();QTest.qWait(100);window.grab().save(str(args.output/'assembled-body.png'))
        report=dict(adapter=args.adapter,job=job['id'],completed=job['completed'],artifact=artifact,memory_nodes=len(window.body_memory.nodes()),memory_head=window.body_memory.head,packet_round_trip=packet['round_trip'],module=module,frame_id=frame['frame_id'],png_sha256=frame['png_sha256'],comparison=frame['comparison'],scene_source=frame['intended_scene']['source'],synthetic_only=True,authority_effect='NONE',base_promoted=False)
        (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
    finally:
        if window:window.close()
        if process.poll() is None:client.request('stop',client.request('status')['revision']);process.wait(timeout=20)
if __name__=='__main__':main()
