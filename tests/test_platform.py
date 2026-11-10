"""Synthetic fixtures exercise application mechanics, never retrieval accuracy."""
import json
import os
import uuid
from io import BytesIO
from datetime import timedelta
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import select,func,create_engine,text
from sqlalchemy.engine import make_url
from alembic.config import Config
from alembic import command
from backend.platform import create_app
from backend.settings import Settings
from backend.models import User,Session,Item,ItemImage,ClaimRequest,MatchJob,MatchSuggestion,ModerationRecord,now

PASSWORD='A long synthetic password 123!'


def test_presentation_assets_are_available_without_private_data(app):
    client = TestClient(app)
    for name in ('app.css', 'app.js', 'app-ui.js'):
        response = client.get('/assets/' + name)
        assert response.status_code == 200
    assert client.get('/assets/../settings.py').status_code == 404


@pytest.fixture
def app(tmp_path):
    database='sqlite:///'+str(tmp_path/'app.db');control=None;schema=None
    if os.getenv('CAMPUSFIND_TEST_POSTGRES')=='true':
        database=Settings.from_env().database_url
        assert database.startswith('postgresql+psycopg://')
        control=create_engine(database);schema='cf_test_'+uuid.uuid4().hex
        with control.begin() as db:db.execute(text('CREATE SCHEMA '+schema))
        database=make_url(database).update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    settings=Settings(database_url=database,storage=tmp_path/'private',origin='http://testserver',testing=True,background_matching=False)
    config=Config('alembic.ini');config.set_main_option('sqlalchemy.url',settings.database_url.replace('%','%%'));command.upgrade(config,'head')
    app=create_app(settings)
    yield app
    app.state.engine.dispose()
    if control:
        assert schema.startswith('cf_test_') and schema[8:].isalnum()
        with control.begin() as db:db.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        control.dispose()


def account(app,email='student@example.edu',role='student'):
    client=TestClient(app);client.headers['origin']='http://testserver'
    response=client.post('/api/v1/auth/register',json={'email':email,'password':PASSWORD,'display_name':'Test Student'})
    assert response.status_code==201,response.text
    client.headers['x-csrf-token']=response.json()['csrf']
    if role=='admin':
        with app.state.sessions.begin() as db:db.get(User,response.json()['user']['id']).role='admin'
    return client


def photo(color='red'):
    image=Image.new('RGB',(100,100),color)
    for x in range(20,80):
        for y in range(20,80):image.putpixel((x,y),(20,50,90))
    raw=BytesIO();image.save(raw,format='JPEG',exif=b'Exif\x00\x00PRIVATE LOCATION');return raw.getvalue()


def report(client,kind='FOUND',count=1):
    metadata={'kind':kind,'title':'Test bottle','category':'bottle','description':'A synthetic object for a workflow test.','location':'Library entrance','event_date':'2026-01-01','consent':True}
    return client.post('/api/v1/items',data={'metadata':json.dumps(metadata),'selections':json.dumps([{'confirmed':True,'box':None}]*count)},
        files=[('photos',(f'photo{i}.jpg',photo('red' if i==0 else 'blue'),'image/jpeg')) for i in range(count)])


def test_migration_auth_hash_cookie_csrf_logout(app):
    c=account(app);me=c.get('/api/v1/auth/me').json()
    with app.state.sessions() as db:
        user=db.scalar(select(User));session=db.scalar(select(Session))
        assert user.password_hash.startswith('$argon2id$') and PASSWORD not in user.password_hash
        assert session.token_hash!=c.cookies.get('campusfind_session')
    c.headers['x-csrf-token']='bad'
    assert c.post('/api/v1/auth/logout').status_code==403
    c.headers['x-csrf-token']=me['csrf'];assert c.post('/api/v1/auth/logout').status_code==200
    assert c.get('/api/v1/auth/me').status_code==401
    bad=c.post('/api/v1/auth/login',json={'email':'student@example.edu','password':'wrong password 123'})
    assert bad.status_code==401
    assert c.post('/api/v1/auth/login',json={'email':'student@example.edu','password':PASSWORD}).status_code==200


def test_registration_validation_origin_roles_and_domain(app):
    c=TestClient(app)
    data={'email':'new@example.edu','password':PASSWORD,'display_name':'Student'}
    assert c.post('/api/v1/auth/register',json=data).status_code==403
    c.headers['origin']='http://testserver';data['role']='admin'
    assert c.post('/api/v1/auth/register',json=data).status_code==422
    del data['role'];app.state.settings.domains=('campus.edu',)
    assert c.post('/api/v1/auth/register',json=data).status_code==400
    data['email']='new@campus.edu';data['password']='secret'
    r=c.post('/api/v1/auth/register',json=data);assert r.status_code==422 and 'secret' not in r.text


def test_rate_limit_failed_auth(app):
    c=TestClient(app);c.headers['origin']='http://testserver'
    for _ in range(10):assert c.post('/api/v1/auth/login',json={'email':'absent@example.edu','password':PASSWORD}).status_code==401
    assert c.post('/api/v1/auth/login',json={'email':'absent@example.edu','password':PASSWORD}).status_code==429


def test_private_images_multiphoto_metadata_and_report_permissions(app):
    c=account(app);other=account(app,'other@example.edu');anon=TestClient(app)
    response=report(c,count=2);assert response.status_code==201,response.text
    item=response.json();assert len(item['images'])==2
    assert anon.get('/api/v1/items').status_code==401
    assert anon.get(item['images'][0]['url']).status_code==401
    raw=other.get(item['images'][0]['url']);assert raw.status_code==200
    assert not Image.open(BytesIO(raw.content)).getexif()
    assert 'storage_key' not in response.text and 'owner_id' not in response.text
    assert other.delete('/api/v1/items/'+item['id']).status_code==403
    assert other.post('/api/v1/items/'+item['id']+'/state',json={'state':'CLOSED'}).status_code==403
    assert c.post('/api/v1/items/'+item['id']+'/state',json={'state':'CLOSED'}).status_code==200
    assert other.get(item['images'][0]['url']).status_code==404
    assert c.get(item['images'][0]['url']).status_code==200
    assert c.delete('/api/v1/items/'+item['id']).status_code==200
    assert not list(app.state.settings.storage.glob('*.jpg'))


def test_invalid_upload_rolls_back_database_and_files(app):
    c=account(app)
    metadata={'kind':'LOST','title':'Lost bag','category':'bag','description':'A synthetic description','location':'Campus','event_date':'2026-01-01','consent':True}
    response=c.post('/api/v1/items',data={'metadata':json.dumps(metadata),'selections':json.dumps([{'confirmed':True,'box':None}]*2)},
        files=[('photos',('good.jpg',photo(),'image/jpeg')),('photos',('bad.jpg',b'not an image','image/jpeg'))])
    assert response.status_code==400
    with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(Item))==0
    assert not list(app.state.settings.storage.glob('*.jpg'))


def test_claim_privacy_review_conflicts_return_notifications(app):
    finder=account(app);claimant=account(app,'claimant@example.edu');intruder=account(app,'intruder@example.edu')
    item=report(finder).json();iid=item['id'];evidence={'evidence':'Private identifying engraving hidden under the base.'}
    response=claimant.post(f'/api/v1/items/{iid}/claims',json=evidence);assert response.status_code==201,response.text
    cid=response.json()['id']
    assert evidence['evidence'] not in intruder.get(f'/api/v1/items/{iid}').text
    assert intruder.get('/api/v1/claims').json()['claims']==[]
    assert intruder.post(f'/api/v1/claims/{cid}/action',json={'action':'approve','note':'Verified engraving'}).status_code==404
    assert claimant.post(f'/api/v1/claims/{cid}/action',json={'action':'approve','note':'Verified engraving'}).status_code==403
    assert claimant.post(f'/api/v1/items/{iid}/claims',json=evidence).status_code==409
    cid2=intruder.post(f'/api/v1/items/{iid}/claims',json=evidence).json()['id']
    assert finder.post(f'/api/v1/claims/{cid}/action',json={'action':'approve','note':'Verified non-public engraving in person.'}).status_code==200
    assert finder.post(f'/api/v1/claims/{cid2}/action',json={'action':'approve','note':'Verified other claim'}).status_code==409
    assert finder.post(f'/api/v1/claims/{cid}/action',json={'action':'returned'}).status_code==403
    assert claimant.post(f'/api/v1/claims/{cid}/action',json={'action':'returned'}).status_code==200
    assert finder.get(f'/api/v1/items/{iid}').json()['state']=='RETURNED'
    notes=claimant.get('/api/v1/notifications').json()['notifications'];assert any(n['kind']=='item_returned' for n in notes)
    assert intruder.post(f"/api/v1/notifications/{notes[0]['id']}/read").status_code==404
    assert claimant.post(f"/api/v1/notifications/{notes[0]['id']}/read").status_code==200
    with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(ModerationRecord))>=6


def test_withdraw_reopen_admin_hide(app):
    finder=account(app);claimant=account(app,'claimant@example.edu');operator=account(app,'admin@example.edu','admin')
    iid=report(finder).json()['id']
    cid=claimant.post(f'/api/v1/items/{iid}/claims',json={'evidence':'An unlisted distinctive mark under the item.'}).json()['id']
    assert finder.post(f'/api/v1/items/{iid}/state',json={'state':'CLOSED'}).status_code==409
    assert claimant.post(f'/api/v1/claims/{cid}/action',json={'action':'withdraw'}).status_code==200
    assert finder.get(f'/api/v1/items/{iid}').json()['state']=='OPEN'
    assert finder.get('/api/v1/admin/items').status_code==403
    assert operator.post(f'/api/v1/admin/items/{iid}/moderate',json={'action':'hide','reason':'Synthetic moderation test'}).status_code==200
    assert claimant.get(f'/api/v1/items/{iid}').status_code==404
    assert operator.get('/api/v1/admin/audit').status_code==200


def test_matching_uses_original_ranking_cache_and_excludes_closed(app,monkeypatch):
    from backend.matching import process_job
    class Fake:
        model_version='test-v1';calls=0
        def describe(self,image):
            self.calls+=1;v=image.mean(axis=(0,1)).astype(np.float32);v/=np.linalg.norm(v)
            return {'vector':v,'label':'bottle','margin':.1,'non_item_margin':-.2}
    model=Fake();monkeypatch.setattr('backend.matching.get_model',lambda:model)
    lost=account(app);found=account(app,'found@example.edu')
    a=report(lost,'LOST',2).json();b=report(found,'FOUND',2).json()
    assert process_job(app.state.sessions,app.state.settings,a['id'])
    rows=lost.get(f"/api/v1/items/{a['id']}/matches").json()
    assert rows['status']=='DONE' and len(rows['groups'])==2 and len(rows['groups'][0]['candidates'])==2
    first_calls=model.calls
    with app.state.sessions() as db:
        assert all(isinstance(i.embedding_key,str) and len(i.embedding_key)==64 for i in db.scalars(select(ItemImage)))
    lost.post(f"/api/v1/items/{a['id']}/match")
    assert process_job(app.state.sessions,app.state.settings,a['id']);assert model.calls==first_calls
    assert found.get('/api/v1/notifications').json()['notifications']
    assert found.post(f"/api/v1/items/{b['id']}/state",json={'state':'CLOSED'}).status_code==200
    assert not lost.get(f"/api/v1/items/{a['id']}/matches").json()['groups'][0]['candidates']


def test_model_failure_preserves_report_and_retry_job(app,monkeypatch):
    from backend.matching import process_job
    def fail():raise RuntimeError('model missing')
    monkeypatch.setattr('backend.matching.get_model',fail)
    c=account(app);iid=report(c).json()['id']
    assert not process_job(app.state.sessions,app.state.settings,iid)
    assert c.get('/api/v1/items/'+iid).status_code==200
    assert c.get(f'/api/v1/items/{iid}/matches').json()['status']=='FAILED'


def test_retention_removes_images_and_evidence(app):
    from backend.worker import purge
    c=account(app);iid=report(c).json()['id']
    with app.state.sessions.begin() as db:db.get(Item,iid).expires_at=now()-timedelta(seconds=1)
    assert c.get('/api/v1/items/'+iid).status_code==404
    purge(app.state.sessions,app.state.settings)
    assert not list(app.state.settings.storage.glob('*.jpg'))


def test_edit_validation_crop_and_session_expiration(app):
    c=account(app);item=report(c).json();iid=item['id'];image=item['images'][0]
    metadata={'title':'Edited bottle','category':'bottle','description':'A sufficiently long description','location':'Main library','event_date':'2999-01-01'}
    assert c.patch('/api/v1/items/'+iid,json=metadata).status_code==400
    metadata['event_date']='2026-01-01'
    assert c.patch('/api/v1/items/'+iid,json=metadata).status_code==200
    assert c.patch('/api/v1/images/'+image['id']+'/crop',json={'confirmed':True,'box':[.8,0,.2,1]}).status_code==400
    assert c.patch('/api/v1/images/'+image['id']+'/crop',json={'confirmed':True,'box':[.1,.1,.9,.9]}).status_code==200
    with app.state.sessions.begin() as db:
        db.scalar(select(Session)).expires_at=now()-timedelta(seconds=1)
    assert c.get('/api/v1/auth/me').status_code==401


def test_security_headers_missing_consent_and_upload_limit(app):
    c=account(app)
    response=c.get('/api/v1/auth/me');assert response.headers['cache-control']=='no-store'
    assert response.headers['x-frame-options']=='DENY'
    assert c.post('/api/v1/auth/login',content=b'x'*33000,headers={'Content-Type':'application/json'}).status_code==413
    metadata={'kind':'LOST','title':'Test report','category':'bag','description':'Test private photo','location':'Library','event_date':'2026-01-01'}
    assert c.post('/api/v1/items',data={'metadata':json.dumps(metadata),'selections':'[{"confirmed":true,"box":null}]'},files={'photos':('a.jpg',photo(),'image/jpeg')}).status_code==400


def test_duplicate_registration_and_revoked_session(app):
    c=account(app);token=c.cookies.get('campusfind_session')
    other=TestClient(app);other.headers['origin']='http://testserver'
    assert other.post('/api/v1/auth/register',json={'email':'student@example.edu','password':PASSWORD,'display_name':'Another'}).status_code==409
    c.post('/api/v1/auth/logout')
    other.cookies.set('campusfind_session',token)
    assert other.get('/api/v1/auth/me').status_code==401


def test_migration_roundtrip_and_schema_drift(app):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from backend.models import Base
    # The fixture is a new, empty, disposable schema/database owned by this test.
    url=app.state.settings.database_url
    assert 'cf_test_' in url or app.state.settings.testing and url.startswith('sqlite')
    config=Config('alembic.ini');config.set_main_option('sqlalchemy.url',url.replace('%','%%'))
    command.downgrade(config,'base');command.upgrade(config,'head')
    with app.state.engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection),Base.metadata)==[]


def test_matching_model_change_invalidates_persistent_cache(app,monkeypatch):
    from backend.matching import process_job
    class Fake:
        model_version='v1';calls=0
        def describe(self,image):
            self.calls+=1;return {'vector':np.array([1.,0.,0.],dtype=np.float32),'label':'bottle','margin':.1}
    model=Fake();monkeypatch.setattr('backend.matching.get_model',lambda:model)
    a=account(app);b=account(app,'b@example.edu');iid=report(a,'LOST').json()['id'];report(b)
    process_job(app.state.sessions,app.state.settings,iid);calls=model.calls
    model.model_version='v2';a.post(f'/api/v1/items/{iid}/match')
    assert process_job(app.state.sessions,app.state.settings,iid) and model.calls>calls


def test_moderation_removes_stale_matches_and_claim_visibility(app,monkeypatch):
    from backend.matching import process_job
    class Fake:
        model_version='v1'
        def describe(self,image):return {'vector':np.array([1.,0.,0.],dtype=np.float32),'label':'bottle','margin':.1}
    monkeypatch.setattr('backend.matching.get_model',lambda:Fake())
    a=account(app);b=account(app,'b@example.edu');operator=account(app,'admin@example.edu','admin')
    lost=report(a,'LOST').json();found=report(b).json();process_job(app.state.sessions,app.state.settings,lost['id'])
    assert a.get(f"/api/v1/items/{lost['id']}/matches").json()['groups'][0]['candidates']
    operator.post(f"/api/v1/admin/items/{found['id']}/moderate",json={'action':'hide','reason':'Private data visible in report.'})
    assert a.get(found['images'][0]['url']).status_code==404
    assert not a.get(f"/api/v1/items/{lost['id']}/matches").json()['groups'][0]['candidates']


def test_postgres_concurrent_claim_approvals(app):
    if app.state.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL row-lock concurrency test')
    from concurrent.futures import ThreadPoolExecutor
    finder=account(app);a=account(app,'a@example.edu');b=account(app,'b@example.edu')
    iid=report(finder).json()['id'];evidence={'evidence':'Distinct ownership evidence for synthetic test.'}
    ids=[c.post(f'/api/v1/items/{iid}/claims',json=evidence).json()['id'] for c in [a,b]]
    def approve(cid):
        with TestClient(app) as client:
            client.cookies.update(finder.cookies);client.headers.update({'origin':'http://testserver','x-csrf-token':finder.headers['x-csrf-token']})
            return client.post(f'/api/v1/claims/{cid}/action',json={'action':'approve','note':'Verified evidence for test claim.'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(approve,ids))
    assert sorted(statuses)==[200,409]
    with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(ClaimRequest).where(ClaimRequest.status=='APPROVED'))==1
