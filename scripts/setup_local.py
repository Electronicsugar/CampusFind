"""Generate local-only credentials without printing them; never overwrite .env."""
from pathlib import Path
import secrets

root=Path(__file__).resolve().parents[1]
password=secrets.token_hex(24)
with (root/'.env').open('x',encoding='utf-8') as stream:
    stream.write(f'POSTGRES_PASSWORD={password}\nDATABASE_URL=postgresql+psycopg://campusfind:{password}@127.0.0.1:5433/campusfind\nCAMPUSFIND_ORIGIN=http://127.0.0.1:8000\nCAMPUSFIND_SECURE_COOKIE=false\n')
print('Created local .env. Start PostgreSQL with docker compose up -d, then run alembic upgrade head.')
