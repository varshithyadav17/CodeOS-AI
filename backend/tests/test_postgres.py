"""Opt-in PostgreSQL concurrency test using a temporary, isolated schema.

CODEOS_TEST_POSTGRES_URL=postgresql+asyncpg://... pytest -q tests/test_postgres.py
The database user needs CREATE SCHEMA permission. Existing schemas are untouched.
"""
import asyncio
import os
import uuid
import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import create_async_engine
from app import database as db
from app.jobs import run_once
from tests.test_lifecycle import upload

pytestmark=pytest.mark.skipif(not os.getenv('CODEOS_TEST_POSTGRES_URL'),reason='Live PostgreSQL connection not provided')


async def test_postgresql_job_claim_fencing_and_expired_lease(system,monkeypatch):
    client,_,vectors,_=system
    url=os.environ['CODEOS_TEST_POSTGRES_URL']
    schema='codeos_test_'+uuid.uuid4().hex
    admin=create_async_engine(url)
    await db._engine.dispose()
    async with admin.begin() as connection:
        await connection.execute(text('CREATE SCHEMA '+schema))
    engine=create_async_engine(url,connect_args={'server_settings':{'search_path':schema}})
    db._engine=engine
    try:
        async with engine.begin() as connection:
            await connection.run_sync(db.metadata.create_all)
        signed=await client.post('/api/auth/signup',json={'email':'pg@example.com','name':'PG Tester','password':'pg-password-123'})
        assert signed.status_code==200,signed.text
        repo=await upload(client)
        entered,release=asyncio.Event(),asyncio.Event()
        original=vectors.upsert
        async def pause(chunks):
            entered.set()
            await release.wait()
            return await original(chunks)
        monkeypatch.setattr(vectors,'upsert',pause)
        first=asyncio.create_task(run_once())
        await asyncio.wait_for(entered.wait(),15)
        async with engine.begin() as connection:
            await connection.execute(update(db.jobs).where(db.jobs.c.repo_id==repo['id']).values(lease_until=0))
        assert await run_once() is False
        release.set()
        await first
        assert (await db.get_repo_repo().get(repo['id'])).status=='ready'
        monkeypatch.setattr(vectors,'upsert',original)
        await client.post(f'/api/repos/{repo["id"]}/reingest')
        results=await asyncio.gather(*(run_once() for _ in range(4)))
        assert sum(results)==1
        assert (await db.get_repo_repo().get(repo['id'])).status=='ready'
    finally:
        await engine.dispose()
        db._engine=None
        async with admin.begin() as connection:
            await connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        await admin.dispose()
