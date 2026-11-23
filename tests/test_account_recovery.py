"""Synthetic account-recovery and production signup regression checks."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from backend.auth import digest
from backend.models import RecoveryCode,Session,User,ModerationRecord
from backend.settings import Settings
from tests.test_platform import app,PASSWORD

NEW_PASSWORD='Reset456789!'
EMAIL='recovery@example.edu'


def signup(app):
    c=TestClient(app);c.headers['origin']='http://testserver'
    response=c.post('/api/v1/auth/register',json={'email':EMAIL,'password':PASSWORD,'display_name':'Recovery Test'})
    assert response.status_code==201,response.text
    c.headers['x-csrf-token']=response.json()['csrf']
    return c,response.json()


def reset(c,code,email=EMAIL):
    return c.post('/api/v1/auth/reset-password',json={'email':email,'password':NEW_PASSWORD,'recovery_code':code})


def test_production_signup_explicit_opt_in(app):
    app.state.settings.environment='production'
    c=TestClient(app);c.headers['origin']='http://testserver'
    data={'email':EMAIL,'password':PASSWORD,'display_name':'Recovery Test'}
    assert c.get('/api/v1/options').json()['registration_open'] is False
    assert c.post('/api/v1/auth/register',json=data).status_code==403
    app.state.settings.public_registration=True
    assert c.get('/api/v1/options').json()['registration_open'] is True
    assert c.post('/api/v1/auth/register',json={**data,'role':'admin'}).status_code==422
    assert c.post('/api/v1/auth/register',json=data).json()['user']['role']=='student'


def test_registration_setting_from_env(monkeypatch):
    monkeypatch.setattr('backend.settings.load_env',lambda:None)
    monkeypatch.setenv('CAMPUSFIND_PUBLIC_REGISTRATION','true')
    assert Settings.from_env().public_registration is True
    monkeypatch.delenv('CAMPUSFIND_PUBLIC_REGISTRATION')
    assert Settings.from_env().public_registration is False


@pytest.mark.parametrize('password',['abc12','abcdefghijkl3','abcdef','123456','!!!!!!'])
def test_new_password_policy_rejects_invalid_values(app,password):
    c=TestClient(app);c.headers['origin']='http://testserver'
    assert c.post('/api/v1/auth/register',json={'email':EMAIL,'password':password,'display_name':'Test User'}).status_code==422
    assert c.post('/api/v1/auth/reset-password',json={'email':EMAIL,'password':password,'recovery_code':'unused'}).status_code==422


@pytest.mark.parametrize('password',['abc123','ABCdef123456'])
def test_new_password_policy_accepts_boundaries(app,password):
    c=TestClient(app);c.headers['origin']='http://testserver'
    assert c.post('/api/v1/auth/register',json={'email':EMAIL,'password':password,'display_name':'Test User'}).status_code==201


def test_legacy_long_password_still_logs_in_and_generates_codes(app):
    from backend.auth import hash_password
    c,data=signup(app);legacy='Previously supported long password 123!'
    with app.state.sessions.begin() as db:db.get(User,data['user']['id']).password_hash=hash_password(legacy)
    result=c.post('/api/v1/auth/login',json={'email':EMAIL,'password':legacy})
    assert result.status_code==200
    c.headers['x-csrf-token']=result.json()['csrf']
    assert c.post('/api/v1/auth/recovery-codes',json={'password':legacy}).status_code==200


def test_signup_returns_codes_once_and_stores_only_hashes(app):
    c,data=signup(app);codes=data['recovery_codes']
    assert len(codes)==len(set(codes))==8
    assert all(len(code.replace('-',''))==32 for code in codes)
    assert 'recovery_codes' not in c.get('/api/v1/auth/me').json()
    assert 'recovery_codes' not in c.post('/api/v1/auth/login',json={'email':EMAIL,'password':PASSWORD}).json()
    with app.state.sessions() as db:
        stored=db.scalars(select(RecoveryCode.code_hash)).all()
        assert set(stored)=={digest('recovery:'+code.replace('-','')) for code in codes}
        assert all(code not in stored for code in codes)
        assert not any(code in str(row.detail) for row in db.scalars(select(ModerationRecord)) for code in codes)


def test_reset_revokes_sessions_and_all_old_codes_without_logging_in(app):
    c,data=signup(app)
    other=TestClient(app);other.headers['origin']='http://testserver'
    assert other.post('/api/v1/auth/login',json={'email':EMAIL,'password':PASSWORD}).status_code==200
    result=reset(other,data['recovery_codes'][0].lower().replace('-',' '))
    assert result.status_code==200,result.text
    assert 'set-cookie' not in result.headers
    assert set(result.json()['recovery_codes']).isdisjoint(data['recovery_codes'])
    assert c.get('/api/v1/auth/me').status_code==401
    assert other.get('/api/v1/auth/me').status_code==401
    with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(Session))==0
    for code in data['recovery_codes'][:2]:assert reset(c,code).status_code==400
    assert c.post('/api/v1/auth/login',json={'email':EMAIL,'password':PASSWORD}).status_code==401
    assert c.post('/api/v1/auth/login',json={'email':EMAIL,'password':NEW_PASSWORD}).status_code==200
    assert reset(c,result.json()['recovery_codes'][0]).status_code==200


def test_recovery_invalid_unknown_inactive_and_origin_are_rejected(app):
    c,data=signup(app);code=data['recovery_codes'][0]
    bad=reset(c,'bad').json()
    assert reset(c,code,'absent@example.edu').json()==bad
    c.headers['origin']='https://attacker.example'
    assert reset(c,code).status_code==403
    c.headers['origin']='http://testserver'
    with app.state.sessions.begin() as db:db.get(User,data['user']['id']).active=False
    assert reset(c,code).json()==bad


def test_recovery_code_is_bound_to_account(app):
    c,data=signup(app)
    second=c.post('/api/v1/auth/register',json={'email':'another@example.edu','password':PASSWORD,'display_name':'Other User'})
    assert second.status_code==201
    assert reset(c,data['recovery_codes'][0],'another@example.edu').status_code==400


def test_replacement_requires_session_csrf_and_password_and_invalidates_old_set(app):
    c,data=signup(app)
    anonymous=TestClient(app);anonymous.headers['origin']='http://testserver'
    body={'password':PASSWORD}
    assert anonymous.post('/api/v1/auth/recovery-codes',json=body).status_code==401
    c.headers['x-csrf-token']='wrong'
    assert c.post('/api/v1/auth/recovery-codes',json=body).status_code==403
    c.headers['x-csrf-token']=data['csrf']
    assert c.post('/api/v1/auth/recovery-codes',json={'password':NEW_PASSWORD}).status_code==400
    result=c.post('/api/v1/auth/recovery-codes',json=body)
    assert result.status_code==200,result.text
    assert c.get('/api/v1/auth/me').status_code==200
    assert reset(c,data['recovery_codes'][0]).status_code==400
    assert reset(c,result.json()['recovery_codes'][0]).status_code==200


def test_recovery_failed_attempts_are_throttled(app):
    c,_=signup(app)
    for _ in range(6):assert reset(c,'bad').status_code==400
    assert reset(c,'bad').status_code==429


def test_concurrent_recovery_can_only_succeed_once(app):
    if app.state.engine.dialect.name!='postgresql':pytest.skip('Row-lock concurrency requires PostgreSQL.')
    _,data=signup(app)
    def attempt(code):
        with TestClient(app) as c:
            c.headers['origin']='http://testserver'
            return reset(c,code).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(attempt,data['recovery_codes'][:2]))
    assert sorted(outcomes)==[200,400]
