import socket
import stat
import zipfile
import pytest
from app import database as db
from app.config import settings
from app.repository.archive import UnsafeZipError, safe_extract, validate_archive
from app.repository.service import UnsafeGitURLError, validate_branch, validate_git_url
from tests.test_lifecycle import ready_repo, source_zip, upload


async def test_auth_signup_login_cookie_logout_and_duplicate_email(system):
    client, _, _, _ = system
    body = {"email": "User@example.com", "name": "User", "password": "unicode-password-😀-1234567890"}
    response = await client.post("/api/auth/signup", json=body)
    assert response.status_code == 200
    assert "password_hash" not in response.json()["user"]
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert (await client.post("/api/auth/signup", json=body)).status_code == 409
    assert (await client.get("/api/auth/me")).status_code == 200
    await client.post("/api/auth/logout")
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.post("/api/auth/login", json={"email":body["email"], "password":"wrong"})).status_code == 401
    assert (await client.post("/api/auth/login", json={"email":body["email"], "password":body["password"]})).status_code == 200
    assert (await client.get("/api/auth/me", headers={"Authorization":"Bearer invalid"})).status_code == 401


async def test_schema_bounds_and_origin_protection(system):
    client, _, _, _ = system
    assert (await client.post("/api/auth/signup", json={"email":"a@example.com", "name":"A", "password":"short"})).status_code == 422
    assert (await client.post("/api/auth/signup", json={"email":"a@example.com", "name":"A", "password":"x"*129})).status_code == 422
    assert (await client.post("/api/auth/login", json={"email":"a@example.com", "password":"password"}, headers={"Origin":"https://evil.example"})).status_code == 403
    assert (await client.post("/api/auth/logout", headers={"Sec-Fetch-Site":"cross-site"})).status_code == 403
    response = await client.get("/api/health/live")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert (await client.get("/api/health/ready")).status_code == 401


async def test_cross_user_repo_conversation_memory_and_stats_isolation(logged_in):
    client, graph, _, _ = logged_in
    repo = await ready_repo(client)
    chat = (await client.post(f"/api/repos/{repo['id']}/chat", json={"message":"authentication"})).json()
    memory = (await client.post("/api/memory", json={"repo_id":repo["id"],"category":"note","title":"private"})).json()
    response = await client.post("/api/auth/signup", json={"email":"bob@example.com", "name":"Bob", "password":"bob-password-123"})
    assert response.status_code == 200
    assert (await client.get("/api/repos")).json() == []
    assert (await client.get("/api/stats")).json()["llm_calls"] == 0
    assert (await client.get("/api/memory")).json() == []
    for path in [f"/api/repos/{repo['id']}",f"/api/repos/{repo['id']}/graph", f"/api/repos/{repo['id']}/files",f"/api/repos/{repo['id']}/jobs",f"/api/repos/{repo['id']}/docs/types",f"/api/conversations/{chat['conversation_id']}"]:
        assert (await client.get(path)).status_code == 404
    assert (await client.post(f"/api/repos/{repo['id']}/reingest")).status_code == 404
    assert (await client.delete(f"/api/repos/{repo['id']}")).status_code == 404
    assert (await client.patch(f"/api/memory/{memory['id']}",json={"title":"attack"})).status_code == 404
    other = await ready_repo(client)
    injected = await client.post(f"/api/repos/{other['id']}/chat", json={"message":"auth", "conversation_id": chat["conversation_id"]})
    assert injected.status_code == 404


async def test_upload_validation_pagination_secrets_and_file_traversal(logged_in, monkeypatch):
    client, _, _, _ = logged_in
    bad = await client.post("/api/repos/upload", files={"file":("file.zip", b"not-a-zip")})
    assert bad.status_code == 400
    response = await client.post("/api/repos/upload", files={"file":("file.txt", b"text")})
    assert response.status_code == 400
    data = source_zip({"wrapper/app.py":"def run():\n    return 1\n", "wrapper/.env":"API_KEY=private", "wrapper/.env.example":"API_KEY=", "wrapper/secret.pem":"key"})
    repo = await upload(client, data)
    from app.jobs import run_once
    await run_once()
    files = (await client.get(f"/api/repos/{repo['id']}/files", params={"limit":1,"offset":0})).json()
    assert len(files) == 1
    all_files=(await client.get(f"/api/repos/{repo['id']}/files")).json()
    assert {f["path"] for f in all_files} == {"app.py", ".env.example"}
    assert (await client.get(f"/api/repos/{repo['id']}/files",params={"offset":2})).json() == []
    assert (await client.get(f"/api/repos/{repo['id']}/files/content",params={"path":"app.py"})).status_code == 200
    for path in ("../other.py", "/etc/passwd", "C:\\file.py"):
        assert (await client.get(f"/api/repos/{repo['id']}/files/content",params={"path":path})).status_code == 400
    for path in (".env", "secret.pem", "missing.py"):
        assert (await client.get(f"/api/repos/{repo['id']}/files/content",params={"path":path})).status_code == 404
    monkeypatch.setattr(settings,"MAX_ARCHIVE_BYTES",10)
    assert (await client.post("/api/repos/upload", files={"file":("file.zip",data)})).status_code == 413


async def test_gemini_failure_is_503_not_an_assistant_message(logged_in, monkeypatch):
    from app.ai.chat import LlmChat
    client, _, _, _ = logged_in
    repo = await ready_repo(client)
    async def unavailable(self,message):
        raise RuntimeError("provider token = do-not-leak")
    monkeypatch.setattr(LlmChat,"send_message",unavailable)
    response = await client.post(f"/api/repos/{repo['id']}/chat",json={"message":"authentication"})
    assert response.status_code == 503
    assert "do-not-leak" not in response.text
    assert await db.get_message_repo().count() == 0
    monkeypatch.setattr(settings,"GEMINI_API_KEY","")
    assert (await client.post(f"/api/repos/{repo['id']}/chat",json={"message":"authentication"})).status_code == 503


async def test_quota_limit_is_enforced(logged_in, monkeypatch):
    client, _, _, _ = logged_in
    monkeypatch.setattr(settings,"MAX_REPOSITORIES_PER_USER",1)
    await upload(client)
    response = await client.post("/api/repos/upload",files={"file":("file.zip",source_zip())})
    assert response.status_code == 409


@pytest.mark.parametrize("name",["../evil.py","/etc/evil.py","C:/evil.py","dir\\evil.py","dir/../../evil.py"])
def test_archive_rejects_unsafe_paths(tmp_path,name):
    path = tmp_path/"bad.zip"
    with zipfile.ZipFile(path,"w") as archive:
        archive.writestr(name,"evil")
    with pytest.raises(UnsafeZipError):
        safe_extract(path,tmp_path/"out")
    assert not (tmp_path/"evil.py").exists()


def test_archive_rejects_symlinks_duplicates_and_bombs(tmp_path, monkeypatch):
    path = tmp_path/"bad.zip"
    info=zipfile.ZipInfo("link")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path,"w") as archive:
        archive.writestr(info,"/etc/passwd")
    with pytest.raises(UnsafeZipError): validate_archive(path)
    with zipfile.ZipFile(path,"w") as archive:
        archive.writestr("APP.py","one")
        archive.writestr("app.py","two")
    with pytest.raises(UnsafeZipError): validate_archive(path)
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bomb.py","a"*(2*1024**2))
    with pytest.raises(UnsafeZipError): validate_archive(path)
    monkeypatch.setattr(settings,"MAX_FILES",1)
    with zipfile.ZipFile(path,"w") as archive:
        archive.writestr("one.py","one")
        archive.writestr("two.py","two")
    with pytest.raises(UnsafeZipError): validate_archive(path)


@pytest.mark.parametrize("url",["http://github.com/owner/repo","https://localhost/owner/repo","file:///tmp/repo","git@github.com:owner/repo","https://token@github.com/owner/repo","https://github.com:444/owner/repo","https://github.com/owner/repo?token=secret","https://github.com/owner/repo/tree/main","https://github.com.evil/owner/repo"])
def test_rejects_ssrf_git_urls(url):
    with pytest.raises(UnsafeGitURLError): validate_git_url(url,resolve=False)


def test_dns_rebinding_and_branch_validation(monkeypatch):
    monkeypatch.setattr(socket,"getaddrinfo",lambda *a,**kw:[(2,1,6,"",("127.0.0.1",443))])
    with pytest.raises(UnsafeGitURLError): validate_git_url("https://github.com/owner/repo")
    for branch in ("--upload-pack=evil","../main","a//b","a.lock","main;rm"):
        with pytest.raises(ValueError): validate_branch(branch)
    validate_branch("feature/working_branch")


async def test_private_github_token_is_encrypted_and_never_exposed(logged_in):
    client,_,_,_=logged_in
    token="github_pat_private_test_value"
    response=await client.post("/api/repos/github",json={"url":"https://github.com/example/private","token":token})
    assert response.status_code==202,response.text
    assert token not in response.text
    repo_id=response.json()["id"]
    async with db.get_engine().connect() as connection:
        row=(await connection.execute(db.select(db.jobs.c.details).where(db.jobs.c.repo_id==repo_id))).scalar_one()
    assert row["github_credential"] != token
    from app.security import decrypt_credential
    assert decrypt_credential(row["github_credential"])==token
    history=await client.get(f"/api/repos/{repo_id}/jobs")
    assert token not in history.text and "github_credential" not in history.text


async def test_chunked_upload_is_bounded_before_multipart_spooling(logged_in, monkeypatch):
    client, *_ = logged_in
    monkeypatch.setattr(settings, "MAX_ARCHIVE_BYTES", 64)
    delivered = 0
    async def stream():
        nonlocal delivered
        yield b'--bound\r\nContent-Disposition: form-data; name="file"; filename="large.zip"\r\nContent-Type: application/zip\r\n\r\n'
        for _ in range(40):
            delivered += 1
            yield b"x" * 65536
        yield b'\r\n--bound--\r\n'
    response = await client.post("/api/repos/upload", content=stream(), headers={"Content-Type": "multipart/form-data; boundary=bound"})
    assert response.status_code == 413, response.text
    assert delivered < 40
    assert await db.get_repo_repo().count() == 0


async def test_transient_github_dns_failure_is_retryable(logged_in, monkeypatch):
    from app.jobs import run_once
    client, *_ = logged_in
    def unavailable(*args, **kwargs):
        raise socket.gaierror("temporary DNS failure")
    monkeypatch.setattr(socket, "getaddrinfo", unavailable)
    response = await client.post("/api/repos/github", json={"url": "https://github.com/example/project"})
    assert response.status_code == 202
    repo_id = response.json()["id"]
    assert await run_once()
    job = (await client.get(f"/api/repos/{repo_id}/jobs")).json()[0]
    assert job["status"] == "retry" and job["attempts"] == 1
    assert (await client.get(f"/api/repos/{repo_id}")).json()["status"] == "queued"
