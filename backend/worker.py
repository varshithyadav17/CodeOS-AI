"""Optional separate worker: WORKER_ENABLED=false uvicorn server:app; python worker.py."""
import asyncio
from app.main import app, lifespan
from app.jobs import worker_loop


async def main():
    from app.config import settings
    settings.WORKER_ENABLED = False
    async with lifespan(app):
        await worker_loop()


if __name__ == "__main__":
    asyncio.run(main())
