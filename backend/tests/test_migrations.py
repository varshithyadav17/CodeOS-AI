"""Upgrade existing data and compile the production PostgreSQL migration."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_existing_user_survives_google_subject_migration(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    path = tmp_path / "migration.sqlite"
    env = {**os.environ, "ENV": "test", "DATABASE_URL": f"sqlite+aiosqlite:///{path}"}
    def alembic(*args, environment=None):
        return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=backend,
            env=environment or env, capture_output=True, text=True, check=True)
    alembic("upgrade", "62243260b0ef")
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO users(id,email,name,provider,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            ("existing", "existing@example.com", "Existing", "local", "2026-10-19", "2026-10-19"))
    alembic("upgrade", "head")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT email,google_subject FROM users WHERE id='existing'").fetchone() == ("existing@example.com", None)
    assert "No new upgrade operations" in alembic("check").stdout
    sql = alembic("upgrade", "head", "--sql", environment={**env, "DATABASE_URL": "postgresql+asyncpg://example:example@localhost/example"}).stdout
    assert "uq_users_google_subject" in sql and "ALTER TABLE users ADD COLUMN google_subject" in sql
    alembic("downgrade", "62243260b0ef")
    alembic("upgrade", "head")
