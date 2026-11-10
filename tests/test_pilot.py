"""Pilot regressions use synthetic fixtures and disposable databases only."""
from datetime import timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_platform import app,account,report,photo
from backend.models import Item,ClaimRequest,now
import pytest


def test_expired_evidence_redacted_without_worker(app):
    finder=account(app);claimant=account(app,'claimant@example.edu');admin=account(app,'admin@example.edu','admin')
    item=report(finder).json()
    claim=claimant.post('/api/v1/items/'+item['id']+'/claims',json={'evidence':'PRIVATE EVIDENCE which must disappear at expiry.'}).json()
    with app.state.sessions.begin() as db:db.get(Item,item['id']).expires_at=now()-timedelta(seconds=1)
    for client in (finder,claimant,admin):
        data=client.get('/api/v1/claims').json();assert 'PRIVATE EVIDENCE' not in str(data)
        assert data['claims'][0]['unavailable'] and not data['claims'][0]['can_review']
        assert client.get(item['images'][0]['url']).status_code==404
    assert not admin.get('/api/v1/admin/items').json()['items']


def test_legacy_upload_body_bounded_before_parsing(app):
    c=TestClient(app)
    for path,mb in [('/api/search',77),('/api/compare',47),('/api/suggest-crops',47)]:
        response=c.post(path,content=b'x',headers={'Content-Type':'multipart/form-data; boundary=test','Content-Length':str(mb*1024*1024)})
        assert response.status_code==413


def test_failed_atomic_upload_leaves_no_photo(app):
    c=account(app)
    with patch('backend.storage.os.replace',side_effect=OSError('synthetic interrupted rename')):
        with TestClient(app,raise_server_exceptions=False) as transport:
            transport.cookies.update(c.cookies);transport.headers.update(c.headers)
            assert report(transport).status_code==500
    assert not list(app.state.settings.storage.glob('*'))
    assert not c.get('/api/v1/items?mine=true').json()['items']


def test_admin_whitespace_reason_rejected(app):
    c=account(app);admin=account(app,'admin@example.edu','admin');item=report(c).json()
    assert admin.post('/api/v1/admin/items/'+item['id']+'/moderate',json={'action':'hide','reason':' '*12}).status_code==400


def test_file_deletion_failure_is_durable_and_retried(app):
    from backend.models import FileDeletion,ItemImage
    from backend.worker import purge
    c=account(app);item=report(c).json()
    with patch('backend.storage.remove',side_effect=PermissionError('synthetic busy file')):
        assert c.delete('/api/v1/items/'+item['id']).status_code==200
    with app.state.sessions() as db:
        assert db.scalar(select(FileDeletion)) and db.scalar(select(ItemImage)) is None
    assert c.get(item['images'][0]['url']).status_code==404
    purge(app.state.sessions,app.state.settings)
    with app.state.sessions() as db:assert db.scalar(select(FileDeletion)) is None
    assert not list(app.state.settings.storage.glob('*.jpg'))


def test_stale_orphan_files_only(app):
    import os,time
    from backend.worker import purge
    c=account(app);report(c);root=app.state.settings.storage
    old=root/('a'*32+'.jpg');part=root/('b'*32+'.part');fresh=root/('c'*32+'.jpg');unknown=root/'operator-notes.txt'
    for path in (old,part,fresh,unknown):path.write_bytes(b'fixture')
    for path in (old,part,unknown):os.utime(path,(time.time()-90000,time.time()-90000))
    purge(app.state.sessions,app.state.settings)
    assert not old.exists() and not part.exists() and fresh.exists() and unknown.exists()
    assert len(list(root.glob('*.jpg')))==2


def test_equivalent_matching_and_persisted_warm_cache(app,monkeypatch):
    import numpy as np
    from backend.matching import process_job
    from backend.gallery import rank_gallery
    from backend.models import ItemImage,MatchSuggestion,MatchJob
    from backend import storage
    class Fake:
        model_version='equivalence';calls=0
        def describe(self,image):
            self.calls+=1
            vector=np.array([float(image[:,:,0].mean()),float(image[:,:,2].mean()),1],dtype=np.float32);vector/=np.linalg.norm(vector)
            return {'vector':vector,'label':'bottle' if vector[1]>vector[0] else 'phone','margin':.1}
    model=Fake();monkeypatch.setattr('backend.matching.get_model',lambda:model)
    a=account(app);b=account(app,'second@example.edu');lost=report(a,'LOST',2).json();found=report(b,'FOUND',2).json()
    expected={}
    with app.state.sessions() as db:
        first=list(db.scalars(select(ItemImage).where(ItemImage.item_id==lost['id'])))
        second=list(db.scalars(select(ItemImage).where(ItemImage.item_id==found['id'])))
        for q,c in [(q,c) for q in first for c in second]+[(c,q) for q in first for c in second]:
            result=rank_gallery(storage.read(app.state.settings,q.storage_key),[(0,c.id,storage.read(app.state.settings,c.storage_key),c.crop)],q.crop,semantic_model=model)[0]
            expected[(q.id,c.id)]=(result['semantic_similarity'],result['appearance_percent'],result['relevance'],result['relevance_reason'])
    assert process_job(app.state.sessions,app.state.settings,lost['id'])
    with app.state.sessions() as db:
        actual={(m.query_image_id,m.candidate_image_id):(m.similarity,m.appearance,m.relevance,m.reason) for m in db.scalars(select(MatchSuggestion))}
    assert actual==expected
    a.post('/api/v1/items/'+lost['id']+'/match');calls=model.calls
    with patch('backend.storage.read',side_effect=AssertionError('warm cache should not decode')):
        assert process_job(app.state.sessions,app.state.settings,lost['id'])
    assert model.calls==calls


def test_matching_interruption_rolls_back_and_retries(app,monkeypatch):
    from backend.matching import process_job
    from backend.models import MatchJob,MatchSuggestion
    a=account(app);item=report(a,'LOST').json()
    class SimulatedKill(BaseException):pass
    monkeypatch.setattr('backend.matching.get_model',lambda:(_ for _ in ()).throw(SimulatedKill()))
    with pytest.raises(SimulatedKill):process_job(app.state.sessions,app.state.settings,item['id'])
    with app.state.sessions() as db:
        assert db.get(MatchJob,item['id']).status=='PENDING' and db.scalar(select(MatchSuggestion)) is None


def test_readiness_metrics_and_fail_closed_registration(app):
    c=account(app);operator=account(app,'admin@example.edu','admin')
    assert c.get('/health/live').status_code==200 and c.get('/health/ready').status_code==200
    assert c.get('/api/v1/admin/operations').status_code==403
    data=operator.get('/api/v1/admin/operations').json();assert 'http_process_metrics' in data
    app.state.settings.environment='production'
    assert c.get('/health/ready').status_code==503
    from backend.worker import heartbeat
    heartbeat(app.state.sessions,'idle');assert c.get('/health/ready').status_code==200
    assert c.post('/api/v1/auth/register',json={'email':'new@example.edu','password':'A safe synthetic password!','display_name':'Synthetic'}).status_code==403


def test_production_configuration_rejects_unsafe_origin(monkeypatch,tmp_path):
    from backend.settings import Settings
    monkeypatch.setattr('backend.settings.load_env',lambda:None)
    monkeypatch.setenv('CAMPUSFIND_ENV','production');monkeypatch.setenv('CAMPUSFIND_STORAGE',str(tmp_path))
    monkeypatch.setenv('CAMPUSFIND_ORIGIN','http://127.0.0.1:8000');monkeypatch.setenv('CAMPUSFIND_SECURE_COOKIE','false')
    with pytest.raises(ValueError):Settings.from_env()
    monkeypatch.setenv('CAMPUSFIND_ORIGIN','https://campus.example.edu/path');monkeypatch.setenv('CAMPUSFIND_SECURE_COOKIE','true')
    with pytest.raises(ValueError):Settings.from_env()
    monkeypatch.setenv('CAMPUSFIND_ORIGIN','https://campus.example.edu')
    settings=Settings.from_env();assert settings.secure_cookie and not settings.background_matching


def test_trusted_host_and_origin_production(app):
    from backend.platform import create_app
    app.state.settings.environment='production';app.state.settings.secure_cookie=True;app.state.settings.origin='https://campus.example.edu'
    pilot=create_app(app.state.settings)
    try:
        with TestClient(pilot,base_url='https://campus.example.edu') as c:
            assert c.get('/health/live',headers={'host':'attacker.invalid'}).status_code==400
            r=c.post('/api/compare',headers={'origin':'https://attacker.invalid'})
            assert r.status_code==403 and r.headers['x-frame-options']=='DENY' and 'strict-transport-security' in r.headers
    finally:pilot.state.engine.dispose()


def test_postgres_duplicate_worker_and_backup_guard(app,monkeypatch):
    if app.state.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL advisory-lock test')
    from sqlalchemy import text
    from backend.matching import process_job
    from backend.models import MatchJob
    c=account(app);item=report(c).json()
    with app.state.engine.begin() as control:
        control.execute(text('SELECT pg_advisory_xact_lock(72439106)'))
        assert process_job(app.state.sessions,app.state.settings,item['id']) is False
    with app.state.sessions() as db:assert db.get(MatchJob,item['id']).status=='PENDING'
    with app.state.engine.begin() as control:
        control.execute(text('SELECT pg_advisory_xact_lock(72439107)'))
        # Fail fast instead of interleaving a file mutation with backup.
        assert c.delete('/api/v1/items/'+item['id']).status_code==503
    assert c.get('/api/v1/items/'+item['id']).status_code==200


def test_match_pagination_preserves_order(app):
    from backend.models import ItemImage,MatchSuggestion,uid
    from backend.matching import potential_matches
    from sqlalchemy import insert
    c=account(app);owner=c.get('/api/v1/auth/me').json()['user']['id'];query=report(c,'LOST').json()
    ids=[]
    with app.state.sessions.begin() as db:
        for n in range(31):
            iid=uid();pid=uid();ids.append((iid,pid))
            db.add(Item(id=iid,owner_id=owner,kind='FOUND',title=f'Fixture {n}',category='bottle',description='Synthetic pagination fixture',location='Test',event_date=now().date(),expires_at=now()+timedelta(days=1)));db.flush()
            db.add(ItemImage(id=pid,item_id=iid,storage_key=uid().replace('-','')+'.jpg',content_hash='0'*64,position=0));db.flush()
            db.add(MatchSuggestion(query_image_id=query['images'][0]['id'],candidate_image_id=pid,similarity=n/100,appearance=40,relevance='relevant' if n%2 else 'uncertain',reason='Synthetic',model_version='synthetic'))
    first=c.get('/api/v1/items/'+query['id']+'/matches').json();second=c.get('/api/v1/items/'+query['id']+'/matches?offset=25').json()
    actual=[x['image_id'] for p in (first,second) for x in p['groups'][0]['candidates']]
    expected=[ids[n][1] for n in sorted(range(31),key=lambda n:(0 if n%2 else 1,-n))]
    assert actual==expected and first['next_offset']==25 and second['next_offset'] is None
    assert c.get('/api/v1/items/'+query['id']+'/matches?offset=-1').status_code==400


def test_postgres_actual_worker_process_crash(app,monkeypatch):
    if app.state.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL process crash test')
    import os,sys,subprocess,numpy as np
    from backend.models import MatchJob
    from backend.matching import process_job
    c=account(app);item=report(c).json();url=app.state.settings.database_url
    assert 'cf_test_' in url
    code="""
import os
from types import SimpleNamespace
from pathlib import Path
from backend.database import configure
from backend.settings import Settings
import backend.matching as matching
app=SimpleNamespace(state=SimpleNamespace())
configure(app,Settings(database_url=os.environ['CF_CRASH_TEST_URL'],storage=Path(os.environ['CF_CRASH_TEST_STORAGE']),testing=True))
matching.get_model=lambda:os._exit(17)
matching.process_job(app.state.sessions,app.state.settings,os.environ['CF_CRASH_TEST_ITEM'])
"""
    env=dict(os.environ,CF_CRASH_TEST_URL=url,CF_CRASH_TEST_STORAGE=str(app.state.settings.storage),CF_CRASH_TEST_ITEM=item['id'])
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,timeout=30)
    assert result.returncode==17
    with app.state.sessions() as db:assert db.get(MatchJob,item['id']).status=='PENDING'
    class Fake:
        model_version='recovered'
        def describe(self,image):return {'vector':np.array([1.,0.],dtype=np.float32),'label':'bottle','margin':.1}
    monkeypatch.setattr('backend.matching.get_model',lambda:Fake())
    assert process_job(app.state.sessions,app.state.settings,item['id'])


def test_complete_student_journey_through_retention(app,monkeypatch):
    import numpy as np
    from backend.matching import process_job
    from backend.worker import purge
    class Fake:
        model_version='journey-fixture'
        def describe(self,image):return {'vector':np.array([1.,0.],dtype=np.float32),'label':'bottle','margin':.1}
    monkeypatch.setattr('backend.matching.get_model',lambda:Fake())
    owner=account(app);finder=account(app,'finder@example.edu')
    lost=report(owner,'LOST',2).json();found=report(finder,'FOUND',2).json()
    assert process_job(app.state.sessions,app.state.settings,lost['id'])
    matches=owner.get('/api/v1/items/'+lost['id']+'/matches').json()
    assert any(c['item_id']==found['id'] for g in matches['groups'] for c in g['candidates'])
    assert owner.get('/api/v1/notifications').json()['notifications']
    claim=owner.post('/api/v1/items/'+found['id']+'/claims',json={'evidence':'Synthetic secret marking beneath the bottle.'})
    assert claim.status_code==201;cid=claim.json()['id']
    assert 'secret marking' not in owner.get('/api/v1/items/'+found['id']).text
    assert finder.post('/api/v1/claims/'+cid+'/action',json={'action':'approve','note':'Synthetic ownership details checked.'}).status_code==200
    assert owner.post('/api/v1/claims/'+cid+'/action',json={'action':'returned'}).json()['status']=='RETURNED'
    assert finder.get('/api/v1/items/'+found['id']).json()['state']=='RETURNED'
    assert any(n['kind']=='item_returned' for n in owner.get('/api/v1/notifications').json()['notifications'])
    assert finder.delete('/api/v1/items/'+found['id']).status_code==200
    with app.state.sessions.begin() as db:db.get(Item,lost['id']).expires_at=now()-timedelta(seconds=1)
    assert owner.get(lost['images'][0]['url']).status_code==404
    purge(app.state.sessions,app.state.settings)
    assert not list(app.state.settings.storage.glob('*.jpg'))
