"""Run `python scripts/init_env.py` once per new project; never overwrites .env."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
content = (root / ".env.example").read_text(encoding="utf-8")
content = content.replace("replace-with-a-random-secret", secrets.token_urlsafe(48))
# URL-safe password works in the Compose database connection string without quoting.
content = content.replace("replace-with-a-database-password", secrets.token_urlsafe(32))
try:
    with (root / ".env").open("x", encoding="utf-8") as file:
        file.write(content)
except FileExistsError:
    raise SystemExit(".env already exists; it was not changed.") from None
print("Created .env with unique secrets. Keep this file private.")
