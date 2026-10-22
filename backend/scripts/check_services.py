"""Verify configured services. --ai performs two small live Gemini requests."""
import argparse
import asyncio
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app import database as db
from app.config import validate_startup_config
from app.ai.chat import LlmChat, UserMessage, close_clients


async def main(ai):
    validate_startup_config()
    failures=[]
    async def check(name, operation):
        try:
            async with asyncio.timeout(60):
                await operation()
            print(f"PASS {name}")
        except Exception as exc:
            failures.append(name)
            print(f"FAIL {name}: {type(exc).__name__} (check configuration and service logs)")
    async def postgres():
        async with db.get_engine().connect() as conn:
            await conn.execute(select(db.users).limit(1))
    await check("PostgreSQL connection and schema",postgres)
    await check("S3 bucket access",db.get_storage().ping)
    await check("Neo4j connection and constraints",db.get_graph_service().initialize)
    await check("Qdrant collection and embedding schema",db.get_vector_store().initialize)
    if ai:
        await check("Gemini document embedding",lambda:db.get_vector_store().embedder.embed(["def hello(): return 'world'"]))
        await check("Gemini generation",lambda:LlmChat(system_message="Reply briefly.").send_message(UserMessage("Reply with the word ready.")))
    else:
        print("SKIP live Gemini calls; add --ai to verify the configured key and models.")
    await close_clients()
    await db.get_graph_service().close()
    await db.get_vector_store().close()
    await db.get_engine().dispose()
    raise SystemExit(1 if failures else 0)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--ai",action="store_true",help="Also call live Gemini embedding and generation APIs")
    asyncio.run(main(parser.parse_args().ai))
