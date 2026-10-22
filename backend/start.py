"""HTTP entry point; --migrate supports free hosts without pre-deploy jobs."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

import uvicorn


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate", action="store_true",
                        help="Upgrade the database before accepting HTTP traffic")
    args = parser.parse_args()
    if args.migrate:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       cwd=Path(__file__).resolve().parent, check=True)
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")),
                proxy_headers=True)
