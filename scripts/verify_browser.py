"""Build and test the production frontend against an isolated test backend."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

root=Path(__file__).resolve().parents[1]
backend=root/'backend'
npm=shutil.which('npm')
if not npm:
    raise SystemExit('Install Node 22.12+ and npm first.')
for port in (8000,5173):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=.2):
            raise SystemExit(f'Port {port} is already in use. Stop the local service before running this isolated test.')
    except OSError:
        pass

env={**os.environ,'PYTHONPATH':str(backend),'VITE_BACKEND_URL':'','API_PROXY_TARGET':'http://127.0.0.1:8000'}
subprocess.run([npm,'run','build'],cwd=root/'frontend',env=env,check=True)
processes=[]
with tempfile.TemporaryDirectory(prefix='codeos-browser-logs-') as temporary:
    logs=[]
    try:
        commands=[([sys.executable,str(backend/'tests'/'ui_server.py')],backend,'backend.log'),
            ([npm,'run','preview','--','--host','127.0.0.1','--port','5173'],root/'frontend','frontend.log')]
        for command,cwd,name in commands:
            log=(Path(temporary)/name).open('w');logs.append(log)
            processes.append(subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT))
        for port in (8000,5173):
            deadline=time.monotonic()+30
            while True:
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.5): break
                except OSError:
                    if any(p.poll() is not None for p in processes) or time.monotonic()>deadline:
                        raise RuntimeError(f'Isolated test service {port} failed to start.')
                    time.sleep(.2)
        subprocess.run([sys.executable,str(backend/'tests'/'browser_smoke.py')],cwd=root,env=env,check=True,timeout=120)
    except Exception:
        for path in Path(temporary).glob('*.log'):
            print(path.name+':\n'+path.read_text(errors='replace')[-8000:],file=sys.stderr)
        raise
    finally:
        for p in processes:p.terminate()
        for p in processes:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for log in logs:log.close()
