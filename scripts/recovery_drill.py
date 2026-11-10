"""End-to-end restoration into NEW guarded disposable databases only."""
import argparse,json,tempfile,time,uuid,shutil
from pathlib import Path
from contextlib import contextmanager
from datetime import date,timedelta
from io import BytesIO
import psycopg
from psycopg import sql
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.engine import make_url
from alembic.config import Config
from alembic import command
from PIL import Image
from types import SimpleNamespace
from backend.settings import Settings,ROOT
from backend.database import configure
from backend.models import User,Item,ItemImage,ClaimRequest,now
from backend.storage import save_upload
from scripts.backup import backup,validate_bundle,run_pg,checksum


@contextmanager
def disposable(admin,application_url):
    url=make_url(application_url);name='cf_restore_'+uuid.uuid4().hex
    with psycopg.connect(**admin,autocommit=True) as control:
        control.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(name),sql.Identifier(url.username)))
    target=url.set(database=name).render_as_string(hide_password=False)
    try:yield target
    finally:
        assert name.startswith('cf_restore_') and len(name)==43 and name[11:].isalnum() and name!=url.database
        with psycopg.connect(**admin,autocommit=True) as control:
            # No FORCE: unexpected live clients prevent deletion and require review.
            control.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


def drill():
    source=Settings.from_env();url=make_url(source.database_url)
    if url.host!='127.0.0.1' or url.port!=5433:raise ValueError('This drill is limited to the local portable PostgreSQL instance.')
    admin=dict(host='127.0.0.1',port=5433,dbname='postgres',user='campusfind_admin',password=(ROOT/'.local'/'pg-admin-password').read_text())
    started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='cf_recovery_') as temporary,disposable(admin,source.database_url) as original,disposable(admin,source.database_url) as restored:
        folder=Path(temporary);settings=Settings(database_url=original,storage=folder/'source-images',testing=True)
        config=Config('alembic.ini');config.set_main_option('sqlalchemy.url',original.replace('%','%%'));command.upgrade(config,'head')
        app=SimpleNamespace(state=SimpleNamespace());configure(app,settings)
        try:
            with app.state.sessions.begin() as db:
                user=User(email='synthetic@example.invalid',display_name='Recovery fixture',password_hash='disabled');db.add(user);db.flush()
                item=Item(owner_id=user.id,kind='FOUND',title='Synthetic recovery report',category='bottle',description='Synthetic data only',location='Test',event_date=date(2026,1,1),expires_at=now()+timedelta(days=1));db.add(item);db.flush()
                for position,color in enumerate(('red','blue')):
                    raw=BytesIO();Image.new('RGB',(100,120),color).save(raw,format='JPEG');raw.seek(0)
                    key,digest,_=save_upload(settings,SimpleNamespace(file=raw),None)
                    db.add(ItemImage(item_id=item.id,storage_key=key,content_hash=digest,position=position))
                db.add(ClaimRequest(item_id=item.id,claimant_id=user.id,evidence='Synthetic recovery evidence only.'))
            bundle=folder/'backup';manifest=backup(settings,bundle);validate_bundle(bundle)
            # Target was just created by disposable(); no overwrite/clean flags exist.
            empty=create_engine(restored)
            try:
                with empty.begin() as db:
                    assert db.scalar(text('SELECT current_database()')).startswith('cf_restore_')
                    assert db.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"))==0
                    db.execute(text('DROP SCHEMA public'))  # Empty schema in this newly created database only.
            finally:empty.dispose()
            run_pg('pg_restore',['--exit-on-error','--no-owner','--no-privileges','--dbname',make_url(restored).database,bundle/'database.dump'],restored)
            shutil.copytree(bundle/'images',folder/'restored-images')
            verify=create_engine(restored)
            try:
                from sqlalchemy.orm import Session
                with Session(verify) as db:
                    assert db.scalar(select(func.count()).select_from(Item))==1
                    photos=list(db.scalars(select(ItemImage)));assert len(photos)==2
                    assert db.scalar(select(ClaimRequest.evidence))=='Synthetic recovery evidence only.'
                    for photo in photos:assert checksum(folder/'restored-images'/photo.storage_key)==photo.content_hash
                    assert db.scalar(text('SELECT version_num FROM alembic_version'))==manifest['revision']
            finally:verify.dispose()
            # Exercise restored authorization, rather than treating copied bytes
            # as evidence that a restored web application remains private.
            from backend.platform import create_app
            from fastapi.testclient import TestClient
            restored_app=create_app(Settings(database_url=restored,storage=folder/'restored-images',testing=True,background_matching=False))
            try:
                with TestClient(restored_app) as client:
                    assert client.get('/api/v1/items').status_code==401
                    assert client.get('/api/v1/images/'+photos[0].id).status_code==401
                    assert client.get('/api/v1/claims').status_code==401
            finally:restored_app.state.engine.dispose()
            # Tampering must fail closed before restoration.
            (bundle/'images'/manifest['images'][0]['key']).write_bytes(b'corrupted fixture')
            try:validate_bundle(bundle)
            except ValueError:pass
            else:raise AssertionError('Corruption was not detected')
        finally:app.state.engine.dispose()
    return {'restored_reports':1,'restored_photos':2,'private_evidence_preserved':True,'schema_revision_verified':True,'restored_anonymous_access_denied':True,'corruption_rejected':True,'disposable_databases_removed':True,'seconds':round(time.perf_counter()-started,3),'scope':'synthetic fixture; not a backup of real user data'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output)
    if output.exists():raise SystemExit('Refusing to overwrite an existing result')
    result=drill();output.parent.mkdir(exist_ok=True,parents=True);output.write_text(json.dumps(result,indent=2));print(json.dumps(result))
