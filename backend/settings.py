"""Explicit environment configuration; no database creation at import time."""
from dataclasses import dataclass
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]


def campus_today():
    return datetime.now(ZoneInfo(os.getenv('CAMPUSFIND_TIMEZONE','Asia/Kolkata'))).date()


def load_env():
    path=ROOT/'.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key,value=line.split('=',1)
                os.environ.setdefault(key.strip(),value.strip())


@dataclass
class Settings:
    database_url: str=''
    storage: Path=ROOT/'.local'/'private-images'
    origin: str='http://127.0.0.1:8000'
    secure_cookie: bool=False
    domains: tuple=()
    session_hours: int=12
    retention_days: int=180
    testing: bool=False
    background_matching: bool=True
    environment: str='development'

    @classmethod
    def from_env(cls):
        load_env()
        origin=os.getenv('CAMPUSFIND_ORIGIN','http://127.0.0.1:8000').rstrip('/')
        environment=os.getenv('CAMPUSFIND_ENV','development')
        if environment not in {'development','production'}:raise ValueError('CAMPUSFIND_ENV must be development or production.')
        parsed=urlsplit(origin)
        if not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or parsed.scheme not in {'http','https'}:
            raise ValueError('Configure a single origin without credentials, path, query or fragment.')
        secure=os.getenv('CAMPUSFIND_SECURE_COOKIE','true' if origin.startswith('https:') else 'false')=='true'
        if not secure and origin not in {'http://127.0.0.1:8000','http://localhost:8000','http://127.0.0.1:8010'}:
            raise ValueError('Non-local deployments require HTTPS and Secure cookies.')
        if secure and not origin.startswith('https://'):
            raise ValueError('Secure sessions require an HTTPS origin.')
        if environment=='production' and (not secure or not os.getenv('CAMPUSFIND_STORAGE')):
            raise ValueError('Production requires HTTPS, Secure cookies and an explicit private storage directory.')
        retention=int(os.getenv('CAMPUSFIND_RETENTION_DAYS','180'))
        if not 1<=retention<=365:raise ValueError('Retention must be between 1 and 365 days.')
        campus_today()  # Fail early for an invalid configured IANA timezone.
        return cls(database_url=os.getenv('DATABASE_URL',''),storage=Path(os.getenv('CAMPUSFIND_STORAGE',str(ROOT/'.local'/'private-images'))).resolve(),
                   origin=origin,secure_cookie=secure,retention_days=retention,environment=environment,
                   background_matching=environment!='production' and os.getenv('CAMPUSFIND_BACKGROUND_MATCHING','true')=='true',
                   domains=tuple(x.strip().lower() for x in os.getenv('CAMPUSFIND_EMAIL_DOMAINS','').split(',') if x.strip()))
