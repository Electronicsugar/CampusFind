"""Synthetic readiness checks; no participant data or external targets."""
import json
from datetime import timedelta
import pytest
from sqlalchemy import event,select
from sqlalchemy.exc import OperationalError
from tests.test_platform import app,account,report
from backend.models import Session,now
from scripts.pilot_preflight import inspect,inspect_database


def configuration(tmp_path):
    image=tmp_path/'images';backup=tmp_path/'backup';image.mkdir();backup.mkdir()
    return dict(profile='researcher-dry-run',database_env='CF_EXPLICIT_TEST_DB',expected_database='cf_dry_test',expected_user='cf_dry_app',
                expected_host='127.0.0.1',expected_port=5433,origin='https://dry.invalid',expected_origin='https://dry.invalid',
                storage=str(image),backup=str(backup),proxy_ips=['127.0.0.1'],secure_cookie=True,environment='production',worker_mode='separate')


def env():return {'CF_EXPLICIT_TEST_DB':'postgresql+psycopg://cf_dry_app:random-long-synthetic-secret@127.0.0.1:5433/cf_dry_test'}


def test_static_preflight_repeated_redacted_and_no_connection(tmp_path):
    config=configuration(tmp_path);a=inspect(config,env());assert a==inspect(config,env())
    assert not any(c['status']=='FAIL' for c in a)
    assert any(c['status']=='NOT_VERIFIED' for c in a)
    assert 'random-long-synthetic-secret' not in json.dumps(a)
    config['proxy_ips']=[];assert {'check':'explicit_proxy_ips','status':'WARNING'} in inspect(config,env())


@pytest.mark.parametrize('change',[{'origin':'http://dry.invalid'},{'secure_cookie':False},{'proxy_ips':['*']},{'expected_database':'wrong'},{'expected_host':'wrong'},{'storage':'relative'},{'environment':'development'},{'worker_mode':'embedded'}])
def test_preflight_refuses_unsafe_targets(tmp_path,change):
    config=configuration(tmp_path);config.update(change)
    assert any(c['status']=='FAIL' for c in inspect(config,env()))
    assert inspect_database(config,env())[0]['status']=='FAIL' # Refuses before connecting.


def test_preflight_missing_secret_paths_and_empty(tmp_path):
    assert inspect({},env())[0]['status']=='FAIL'
    c=configuration(tmp_path);assert any(x['status']=='FAIL' for x in inspect(c,{}))
    c['backup']=c['storage'];assert any(x['status']=='FAIL' for x in inspect(c,env()))
    c['storage']=str(tmp_path/'OneDrive'/'images');assert any(x['status']=='FAIL' for x in inspect(c,env()))


def test_three_user_direct_boundaries_and_duplicate_transitions(app):
    a=account(app,'a@example.edu');b=account(app,'b@example.edu');c=account(app,'c@example.edu')
    lost=report(a,'LOST',2).json();found=report(b,'FOUND',2).json();iid=found['id']
    # Active reports/images are intentionally cohort-visible, unlike evidence.
    assert c.get('/api/v1/images/'+found['images'][0]['id']).status_code==200
    assert a.patch('/api/v1/items/'+iid,json={k:found[k] for k in ('title','category','description','location','event_date')}).status_code==403
    claim=a.post('/api/v1/items/'+iid+'/claims',json={'evidence':'TEST ONLY private synthetic ownership clue'}).json();cid=claim['id']
    assert 'private synthetic' not in c.get('/api/v1/items/'+iid).text
    assert c.get('/api/v1/claims').json()['claims']==[]
    for action in ('approve','reject','returned'):
        r=c.post('/api/v1/claims/'+cid+'/action',json={'action':action,'note':'TEST ONLY denied action'})
        assert r.status_code==404 and 'private synthetic' not in r.text
    assert c.get('/api/v1/admin/audit').status_code==403
    assert c.get('/api/v1/admin/operations').status_code==403
    assert b.post('/api/v1/claims/'+cid+'/action',json={'action':'approve','note':'TEST ONLY verified staged marking'}).status_code==200
    assert b.post('/api/v1/claims/'+cid+'/action',json={'action':'returned'}).status_code==403
    assert a.post('/api/v1/claims/'+cid+'/action',json={'action':'returned'}).status_code==200
    assert a.post('/api/v1/claims/'+cid+'/action',json={'action':'returned'}).status_code==409
    note=a.get('/api/v1/notifications').json()['notifications'][0]
    assert c.post('/api/v1/notifications/'+note['id']+'/read').status_code==404
    assert b.delete('/api/v1/items/'+iid).status_code==200
    assert c.get('/api/v1/images/'+found['images'][0]['id']).status_code==404


def test_database_outage_is_generic_and_recovers_without_server_stop(app):
    c=account(app);item=report(c,'LOST').json()
    def outage(*args):raise OperationalError('synthetic','secret-should-not-leak',Exception('TEST ONLY database down'))
    event.listen(app.state.engine,'before_cursor_execute',outage)
    try:
        response=c.get('/api/v1/items/'+item['id'])
        assert response.status_code==503 and 'secret-should-not-leak' not in response.text
        assert c.get('/health/ready').status_code==503
    finally:event.remove(app.state.engine,'before_cursor_execute',outage)
    assert c.get('/api/v1/items/'+item['id']).status_code==200
    assert c.get('/health/ready').status_code==200


def test_session_expiry_denies_direct_request_and_relogin_succeeds(app):
    from tests.test_platform import PASSWORD
    c=account(app)
    with app.state.sessions.begin() as db:
        for session in db.scalars(select(Session)):session.expires_at=now()-timedelta(seconds=1)
    assert c.get('/api/v1/items').status_code==401
    r=c.post('/api/v1/auth/login',json={'email':'student@example.edu','password':PASSWORD});assert r.status_code==200
    c.headers['x-csrf-token']=r.json()['csrf']
    assert report(c,'LOST').status_code==201


def test_https_cookie_csrf_host_forwarded_and_logs(app,caplog):
    from fastapi.testclient import TestClient
    from backend.platform import create_app
    from tests.test_platform import PASSWORD
    from scripts.serve import proxy_address
    account(app)
    settings=app.state.settings;settings.environment='production';settings.secure_cookie=True;settings.origin='https://dry.invalid'
    production=create_app(settings)
    try:
        with TestClient(production,base_url=settings.origin) as c:
            caplog.set_level('INFO',logger='campusfind.operations')
            r=c.post('/api/v1/auth/login',headers={'origin':settings.origin,'x-forwarded-for':'203.0.113.99','x-forwarded-proto':'http'},json={'email':'student@example.edu','password':PASSWORD})
            assert r.status_code==200
            cookie=r.headers['set-cookie'].lower()
            assert all(flag in cookie for flag in ('secure','httponly','samesite=lax'))
            assert c.post('/api/v1/auth/logout',headers={'origin':settings.origin}).status_code==403
            assert c.post('/api/v1/auth/logout',headers={'origin':'https://wrong.invalid','x-csrf-token':r.json()['csrf']}).status_code==403
            assert c.get('/api/v1/items',headers={'host':'wrong.invalid'}).status_code==400
            assert c.post('/api/v1/auth/register',headers={'origin':settings.origin},json={'email':'new@example.edu','password':PASSWORD,'display_name':'Synthetic'}).status_code==403
            operational=' '.join(rec.message for rec in caplog.records if rec.name=='campusfind.operations')
            assert operational and PASSWORD not in operational and 'student@example.edu' not in operational and r.json()['csrf'] not in operational
        with pytest.raises(ValueError):proxy_address('*')
    finally:production.state.engine.dispose()


def test_database_inspection_is_read_only_and_redacts_errors(tmp_path,monkeypatch):
    import sqlalchemy
    class BrokenEngine:
        disposed=False
        def connect(self):raise RuntimeError('secret DSN must not appear')
        def dispose(self):self.disposed=True
    engine=BrokenEngine();monkeypatch.setattr(sqlalchemy,'create_engine',lambda *a,**kw:engine)
    result=inspect_database(configuration(tmp_path),env())
    assert result==[{'check':'database_connectivity_or_query','status':'FAIL'}] and engine.disposed
    assert 'secret' not in json.dumps(result)


def test_placeholder_config_cannot_pass(tmp_path):
    c=configuration(tmp_path);c['expected_database']='REPLACE'
    assert {'check':'placeholder_free','status':'FAIL'} in inspect(c,env())


def test_canary_missing_loading_and_runtime_stages(tmp_path,monkeypatch):
    from scripts.pilot_preflight import canary
    import backend.semantic as semantic
    import backend.detection as detection
    import backend.nanodet as nanodet
    monkeypatch.setattr(semantic,'MODEL_DIR',tmp_path/'clip');monkeypatch.setattr(detection,'ROOT',tmp_path)
    assert canary()['stage']=='missing_artifact'
    (tmp_path/'clip').mkdir();(tmp_path/'nanodet').mkdir()
    for n in ('vision_model_quantized.onnx','text_model_quantized.onnx','tokenizer.json','preprocessor_config.json'):(tmp_path/'clip'/n).touch()
    (tmp_path/'nanodet'/'object_detection_nanodet_2022nov.onnx').touch()
    monkeypatch.setattr(semantic,'get_model',lambda:(_ for _ in ()).throw(RuntimeError('private loading details')))
    result=canary();assert result=={'status':'FAIL','stage':'model_loading'}
    class BrokenModel:
        def describe(self,image):raise RuntimeError('private runtime details')
    monkeypatch.setattr(semantic,'get_model',lambda:BrokenModel())
    monkeypatch.setattr(nanodet,'NanoDetector',lambda:object())
    assert canary()=={'status':'FAIL','stage':'runtime_inference'}
