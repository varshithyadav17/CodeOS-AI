import io
import json
import zipfile
import pytest
from app import database as db
from app.jobs import run_once
from app.prompts import DOC_TYPES
from tests.test_lifecycle import ready_repo


async def test_review_architecture_memory_and_documentation(logged_in,monkeypatch):
    from app.ai.chat import LlmChat
    client, _, _, _ = logged_in
    repo=await ready_repo(client)
    repo_id=repo['id']
    async def response(self,message):
        if self.session_id.startswith('review-manager-'):
            return json.dumps({'summary':'Review complete','action_plan':['Add regression tests']})
        if self.session_id.startswith('review-'):
            return json.dumps({'summary':'Checked supplied evidence','score':85,'findings':[{'category':'testing','title':'Add token tests','description':'Cover token validation','severity':'low','confidence':0.8,'file_path':'auth.py','line':1}]})
        return '# Repository documentation\n\nAuthentication lives in auth.py.\n'
    monkeypatch.setattr(LlmChat,'send_message',response)
    response=await client.post(f'/api/repos/{repo_id}/reviews')
    assert response.status_code==202,response.text
    review_id=response.json()['id']
    await run_once()
    review=(await client.get(f'/api/reviews/{review_id}')).json()
    assert review['status']=='done',review
    assert len(review['agents'])==6
    assert all(a['status']=='done' for a in review['agents'])
    memories=(await client.get('/api/memory')).json()
    assert len(memories)==6
    assert any(m['category']=='architecture' for m in memories)
    assert (await client.post(f'/api/memory/import/{review_id}')).json()['added']==0
    assert (await client.get('/api/memory/search',params={'q':'token'})).json()
    mid=memories[0]['id']
    assert (await client.patch(f'/api/memory/{mid}',json={'status':'resolved'})).json()['status']=='resolved'
    for view in ('call','dependency','package','service'):
        result=await client.get(f'/api/repos/{repo_id}/architecture/graph',params={'view':view})
        assert result.status_code==200,result.text
        assert 'nodes' in result.json()
    for endpoint in ('cycles','dead-code'):
        assert (await client.get(f'/api/repos/{repo_id}/architecture/{endpoint}')).status_code==200
    graph=(await client.get(f'/api/repos/{repo_id}/graph')).json()
    symbol=next(n for n in graph['nodes'] if n['name']=='authenticate')
    for endpoint in ('impact','flow'):
        result=await client.get(f'/api/repos/{repo_id}/architecture/{endpoint}/{symbol["id"]}')
        assert result.status_code==200,result.text
        if endpoint=='impact':
            assert any(n['name']=='login' for n in result.json()['callers'])
            assert any(n['file_path']=='api.py' for n in result.json()['dependents'])
    doc_type=next(iter(DOC_TYPES))
    generated=await client.post(f'/api/repos/{repo_id}/docs/generate',json={'doc_type':doc_type})
    assert generated.status_code==200,generated.text
    again=await client.post(f'/api/repos/{repo_id}/docs/generate',json={'doc_type':doc_type})
    assert generated.json()['id']==again.json()['id']
    assert len((await client.get(f'/api/repos/{repo_id}/docs')).json())==1
    exported=await client.get(f'/api/repos/{repo_id}/docs/export')
    assert exported.status_code==200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        assert archive.namelist()==[doc_type+'.md']
        assert b'auth.py' in archive.read(doc_type+'.md')
    assert (await client.delete(f'/api/memory/{mid}')).json()['ok']


async def test_all_failed_review_specialists_do_not_report_success(logged_in,monkeypatch):
    from app.ai.chat import LlmChat
    client, _, _, _ = logged_in
    repo=await ready_repo(client)
    async def invalid(self,message):
        return 'not valid review JSON'
    monkeypatch.setattr(LlmChat,'send_message',invalid)
    response=await client.post(f'/api/repos/{repo["id"]}/reviews')
    await run_once()
    review=await db.get_review_repo().get(response.json()['id'])
    assert review.status=='failed'
    assert review.overall_score==0


async def test_memory_search_preserves_filters_and_owner(logged_in):
    client, _, _, _ = logged_in
    repo = await ready_repo(client)
    other = await ready_repo(client)
    records = []
    for rid, category, severity in ((repo['id'], 'note', 'medium'),
        (repo['id'], 'security', 'high'), (other['id'], 'note', 'medium')):
        response = await client.post('/api/memory', json={
            'repo_id': rid, 'category': category, 'severity': severity, 'title': 'token validation'})
        assert response.status_code == 200
        records.append(response.json())
    params = {'q': 'token', 'repo_id': repo['id'], 'category': 'note', 'severity': 'medium', 'status': 'open'}
    found = (await client.get('/api/memory/search', params=params)).json()
    assert [m['id'] for m in found] == [records[0]['id']]
    await client.patch('/api/memory/' + records[0]['id'], json={'status': 'resolved'})
    assert (await client.get('/api/memory/search', params=params)).json() == []
    assert (await client.get('/api/memory/search', params={**params, 'status': 'resolved'})).json()[0]['id'] == records[0]['id']
    await client.post('/api/auth/signup', json={'email': 'different@example.com', 'name': 'Other', 'password': 'other-password-123'})
    assert (await client.get('/api/memory/search', params={**params, 'status': 'resolved'})).json() == []


async def test_graph_pagination_has_no_missing_nodes_or_unrelated_edges(logged_in):
    client, graph, _, _ = logged_in
    repo = await ready_repo(client)
    pages, offset = [], 0
    while True:
        response = await client.get(f'/api/repos/{repo["id"]}/graph', params={'limit': 2, 'offset': offset})
        assert response.status_code == 200, response.text
        page = response.json()
        assert page['offset'] == offset
        assert page['total'] == await graph.count_nodes(repo['id'])
        ids = {n['id'] for n in page['nodes']}
        assert all(e['source_id'] in ids and e['target_id'] in ids for e in page['edges'])
        pages.extend(ids)
        if not page['has_more']:
            break
        offset += page['limit']
    assert len(pages) == len(set(pages)) == await graph.count_nodes(repo['id'])
    empty = (await client.get(f'/api/repos/{repo["id"]}/graph', params={'offset': 100000})).json()
    assert empty['nodes'] == empty['edges'] == []
    assert empty['has_more'] is False


@pytest.mark.parametrize("output,status,score", [
    ({"score": 0, "findings": []}, "done", 0),
    ({"score": 101, "findings": []}, "failed", 0),
    ({"score": 90, "findings": "invalid"}, "failed", 0),
    ({"score": 90, "findings": [{"title": "Issue", "severity": "severe", "description": "Invalid severity"}]}, "failed", 0),
    ({"score": 90, "findings": [{"title": "Issue", "severity": "low", "description": "Unknown file", "file_path": "does-not-exist.py"}]}, "failed", 0),
])
async def test_review_output_is_validated_and_zero_score_preserved(monkeypatch, output, status, score):
    from app.ai.chat import LlmChat
    from app.ai.review import ReviewContext, run_agent_with_llm
    async def answer(self, message):
        return json.dumps(output)
    monkeypatch.setattr(LlmChat, "send_message", answer)
    context = ReviewContext("repo", "Example", [], [], [], [], [], {})
    report = await run_agent_with_llm("security", "Review evidence", context)
    assert report.status == status
    if status == "done":
        assert report.score == score


async def test_all_document_types_timeline_health_and_private_endpoints(logged_in, monkeypatch):
    client, graph, *_ = logged_in
    repo = await ready_repo(client)
    rid = repo["id"]
    available = (await client.get(f"/api/repos/{rid}/docs/types")).json()
    assert {item["key"] for item in available} == set(DOC_TYPES)
    for doc_type in DOC_TYPES:
        response = await client.post(f"/api/repos/{rid}/docs/generate", json={"doc_type": doc_type})
        assert response.status_code == 200, response.text
    assert len((await client.get(f"/api/repos/{rid}/docs")).json()) == len(DOC_TYPES) == 10
    assert (await client.post(f"/api/repos/{rid}/docs/generate", json={"doc_type": "unknown"})).status_code == 400
    snapshot = {"available": True, "shallow": True, "commits": [{"sha": "a" * 40, "message": "Test snapshot"}],
        "hotspots": [{"path": "auth.py"}], "contributors": [{"name": "Test"}], "complexity": [], "files": {"auth.py": [{"sha": "a" * 40}]}}
    await db.get_repo_repo().update(rid, {"timeline": snapshot})
    commits = (await client.get(f"/api/repos/{rid}/timeline/commits")).json()
    assert commits["shallow"] and commits["commits"] == snapshot["commits"]
    endpoints = ["docs", "docs/export", "reviews", "conversations", "timeline/commits", "timeline/hotspots", "timeline/contributors", "timeline/complexity", "timeline/file?path=auth.py"]
    for endpoint in endpoints:
        assert (await client.get(f"/api/repos/{rid}/{endpoint}")).status_code == 200
    assert (await client.get("/api/health/ready")).status_code == 200
    async def unavailable():
        raise ConnectionError("private service detail")
    monkeypatch.setattr(graph, "ping", unavailable)
    response = await client.get("/api/health/ready")
    assert response.status_code == 503 and response.json()["services"]["neo4j"] == "unavailable"
    assert "private" not in response.text
    await client.post("/api/auth/signup", json={"email": "other-docs@example.com", "name": "Other", "password": "other-password-123"})
    for endpoint in endpoints:
        assert (await client.get(f"/api/repos/{rid}/{endpoint}")).status_code == 404
    assert (await client.post(f"/api/repos/{rid}/docs/generate", json={"doc_type": "readme"})).status_code == 404
