"""Consistent PostgreSQL + private-file backup. Never overwrites a destination.

All application/worker file mutations acquire the shared advisory guard. This
operator command holds its exclusive counterpart during snapshot and file copy.
Run only against a trusted operator-controlled backup directory.
"""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from backend.settings import Settings,ROOT
from backend.storage import location


def executable(name):
    explicit=os.getenv('CAMPUSFIND_PG_BIN')
    folder=Path(explicit) if explicit else ROOT/'.local'/'postgres'/'pgsql'/'bin'
    candidate=folder/(name+('.exe' if os.name=='nt' else ''))
    found=str(candidate) if candidate.is_file() else shutil.which(name)
    if not found:raise RuntimeError('Install PostgreSQL client tools or set CAMPUSFIND_PG_BIN.')
    return found


def pg_env(url):
    url=make_url(url)
    if url.drivername!='postgresql+psycopg':raise ValueError('PostgreSQL required.')
    env=dict(os.environ)
    # No password in command lines, outputs, manifests or exception messages.
    env.update(PGHOST=url.host or '127.0.0.1',PGPORT=str(url.port or 5432),PGUSER=url.username or '',PGPASSWORD=url.password or '',PGDATABASE=url.database or '',PGCONNECT_TIMEOUT='5')
    if url.query.get('sslmode'):env['PGSSLMODE']=url.query['sslmode']
    return env


def run_pg(name,args,url):
    result=subprocess.run([executable(name),*map(str,args)],env=pg_env(url),capture_output=True,timeout=300)
    if result.returncode:raise RuntimeError(f'{name} failed; inspect database availability and client version. Sensitive command output suppressed.')


def checksum(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def backup(settings,output):
    output=Path(output).resolve()
    if output==settings.storage.resolve() or settings.storage.resolve() in output.parents:raise ValueError('Backup must be outside private image storage.')
    output.mkdir(parents=True,exist_ok=False)
    engine=create_engine(settings.database_url);guard=None
    try:
        # Acquire the guard BEFORE opening the repeatable-read snapshot. A
        # transaction-level lock SELECT would establish its snapshot too early
        # when waiting behind an upload/delete transaction.
        guard=engine.connect().execution_options(isolation_level='AUTOCOMMIT')
        guard.execute(text("SET lock_timeout = '10s'"))
        guard.execute(text('SELECT pg_advisory_lock(72439107)'))
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as db:
            snapshot=db.scalar(text('SELECT pg_export_snapshot()'))
            # Operator tool backs up the normal public application schema only.
            if db.scalar(text('SELECT current_schema()'))!='public':raise ValueError('Backup requires the public application schema, not a search-path override.')
            rows=db.execute(text('SELECT storage_key, content_hash FROM item_images')).all()
            (output/'images').mkdir()
            records=[]
            for key,expected in rows:
                source=location(settings,key);target=location(type('Storage',(),{'storage':output/'images'})(),key)
                shutil.copyfile(source,target)
                actual=checksum(target)
                if actual!=expected:raise RuntimeError('Image checksum mismatch. Backup is incomplete.')
                records.append({'key':key,'sha256':actual})
            run_pg('pg_dump',['--format=custom','--no-owner','--no-privileges','--schema=public','--snapshot='+snapshot,'--file',output/'database.dump'],settings.database_url)
            manifest={'format':1,'database_sha256':checksum(output/'database.dump'),'images':records,'revision':db.scalar(text('SELECT version_num FROM alembic_version'))}
            (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        return manifest
    finally:
        if guard:
            try:guard.execute(text('SELECT pg_advisory_unlock(72439107)'))
            finally:guard.close()
        engine.dispose()


def validate_bundle(folder):
    folder=Path(folder);manifest=json.loads((folder/'manifest.json').read_text())
    if manifest.get('format')!=1 or checksum(folder/'database.dump')!=manifest['database_sha256']:raise ValueError('Invalid backup manifest or dump digest.')
    settings=type('Storage',(),{'storage':folder/'images'})()
    for record in manifest['images']:
        if checksum(location(settings,record['key']))!=record['sha256']:raise ValueError('Backup photo integrity check failed.')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    try:
        result=backup(Settings.from_env(),args.output)
        print(f"Backup complete: {len(result['images'])} private photos. Protect this directory as sensitive data.")
    except Exception:
        raise SystemExit('Backup incomplete. Do not use it for recovery; check configuration, storage and database access. No existing backup was overwritten.') from None
