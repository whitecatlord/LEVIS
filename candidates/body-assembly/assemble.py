"""One entrypoint: PAUSED coordinator plus independently closable assembled GUI."""
import argparse,json,os,subprocess,sys,time,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime'))
from runtime_client import Client
from scoped_files import ordinary
_children={}

def ensure_runtime(home,adapter='none'):
    home=Path(home).absolute();home.mkdir(parents=True,exist_ok=True)
    for part in [home,*home.parents]:ordinary(part)
    profile=home/'runtime-profile'
    try:
        client=Client(profile,'body-launcher');status=client.request('status')
        if status['state'] not in ('STOPPING','STOPPED','ERROR'):return dict(profile=str(profile),started=False,status=status,requested_adapter_ignored_for_existing_runtime=True)
        raise RuntimeError('Existing runtime is stopping/stopped/error; inspect it before restarting')
    except (FileNotFoundError,OSError) as error:
        # A live writer with unavailable IPC will refuse a second native owner.
        pass
    create=not profile.exists()
    if not create:Client(profile,'body-launcher')  # Validate metadata/ACL; no reset or recreation.
    logs=home/'runtime-logs';logs.mkdir(exist_ok=True);stamp=str(time.time_ns());stderr=logs/(stamp+'.stderr.log');stdout=logs/(stamp+'.stdout.log')
    command=[sys.executable,str(ROOT/'runtime/runtime_coordinator.py'),'--profile',str(profile),'--adapter',adapter]
    if create:command.append('--init')
    with stdout.open('xb') as out,stderr.open('xb') as err:
        process=subprocess.Popen(command,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0),close_fds=True)
    _children[process.pid]=process
    threading.Thread(target=process.wait,daemon=True,name='LEVIS-child-reaper').start()
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError('Coordinator failed; inspect '+str(stderr))
        try:
            client=Client(profile,'body-launcher');status=client.request('status')
            if status['state'] in ('PAUSED','READY','WORKING'):return dict(profile=str(profile),started=True,pid=process.pid,status=status,adapter=adapter)
        except (OSError,FileNotFoundError,ValueError):pass
        except RuntimeError as error:
            if str(error)!='Profile initialization incomplete or incompatible with startup mode':raise
        time.sleep(.1)
    # Do not kill a coordinator that may own authorized work after an uncertain start.
    raise TimeoutError('Coordinator startup outcome unknown; inspect '+str(stderr))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--home',type=Path,default=ROOT.parent/'LEVIS_BODY_PRIVATE');parser.add_argument('--adapter',choices=['none','fake','ollama'],default='none');parser.add_argument('--no-gui',action='store_true');args=parser.parse_args()
    result=ensure_runtime(args.home,args.adapter);print(json.dumps(result,indent=2))
    if args.no_gui:return
    appdata=Path(args.home).absolute()/'workbench'
    child=subprocess.Popen([sys.executable,str(ROOT/'body_workbench.py'),'--data',str(appdata),'--profile',result['profile']],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return child.wait()  # Closing GUI never terminates the separate coordinator.
if __name__=='__main__':sys.exit(main())
