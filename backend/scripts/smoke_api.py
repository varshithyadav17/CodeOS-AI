"""Live, complete repository lifecycle check via HTTP, including Gemini.

python scripts/smoke_api.py --base-url http://localhost:8080 --email ...
Password is read privately from getpass or CODEOS_SMOKE_PASSWORD.
Creates a small temporary repository in your account, then deletes it.
"""
import argparse
import getpass
import io
import os
import time
import zipfile
import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',default='http://localhost:8080')
    parser.add_argument('--email',required=True)
    args=parser.parse_args()
    password=os.getenv('CODEOS_SMOKE_PASSWORD') or getpass.getpass('CodeOS password: ')
    with httpx.Client(base_url=args.base_url.rstrip('/')+'/api',timeout=120) as client:
        def verify(response):
            response.raise_for_status()
            return response.json()
        verify(client.post('/auth/login',json={'email':args.email,'password':password}))
        repo_id=None
        try:
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w') as archive:
                archive.writestr('auth.py',"def authenticate(token):\n    return token == 'allowed'\n")
                archive.writestr('api.py',"from auth import authenticate\n\ndef login(token):\n    return authenticate(token)\n")
            repo=verify(client.post('/repos/upload',files={'file':('smoke-test.zip',data.getvalue(),'application/zip')}))
            repo_id=repo['id']
            def wait_ready():
                deadline=time.monotonic()+600
                while time.monotonic()<deadline:
                    current=verify(client.get(f'/repos/{repo_id}'))
                    if current['status']=='ready':return current
                    if current['status']=='failed':raise RuntimeError(current['message'])
                    time.sleep(2)
                raise TimeoutError('Repository ingestion timed out.')
            indexed=wait_ready()
            assert verify(client.get(f'/repos/{repo_id}/files'))
            assert 'authenticate' in verify(client.get(f'/repos/{repo_id}/files/content',params={'path':'auth.py'}))['content']
            graph=verify(client.get(f'/repos/{repo_id}/graph'))
            assert any(e['type']=='CALLS' for e in graph['edges'])
            answer=verify(client.post(f'/repos/{repo_id}/chat',json={'message':'Where is authentication handled, and what calls it?'}))
            assert answer['sources'] and answer['relationships']
            verify(client.post(f'/repos/{repo_id}/reingest'))
            assert wait_ready()['stats']==indexed['stats']
            print('PASS upload, durable ingestion, graph, file preview, grounded chat, and repeat ingestion')
        finally:
            if repo_id:
                verify(client.delete(f'/repos/{repo_id}'))
                deadline=time.monotonic()+180
                while time.monotonic()<deadline:
                    response=client.get(f'/repos/{repo_id}')
                    if response.status_code==404:
                        print('PASS coordinated repository deletion')
                        break
                    if response.is_success and response.json()['status']=='delete_failed':
                        raise RuntimeError('Cleanup incomplete; check the repository job history and retry Delete.')
                    time.sleep(2)
                else:
                    raise TimeoutError('Repository deletion did not complete.')


if __name__=='__main__':
    main()
