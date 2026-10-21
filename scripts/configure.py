"""Create local configuration without embedding shared default secrets."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    raise SystemExit(".env already exists; edit it directly to preserve your credentials.")
values = {"JWT_SECRET": secrets.token_urlsafe(48), "POSTGRES_PASSWORD": secrets.token_hex(24),
    "NEO4J_PASSWORD": secrets.token_hex(24), "MINIO_ROOT_PASSWORD": secrets.token_hex(24)}
text = (root / ".env.example").read_text()
for name, value in values.items():
    text = text.replace(name + "=\n", name + "=" + value + "\n")
target.write_text(text)
target.chmod(0o600)
print("Created .env. Add GEMINI_API_KEY, then run docker compose up --build -d.")
