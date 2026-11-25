import pytest
from tests.test_platform import app,account


def test_app_version_and_revalidation_headers(app):
    from fastapi.testclient import TestClient
    from backend.platform import APP_VERSION
    with TestClient(app) as client:
        response=client.get('/api/v1/options')
        assert response.json()['app_version']==APP_VERSION
        assert response.headers['x-campusfind-version']==APP_VERSION
        for path in ('/app','/assets/app.js'):
            response=client.get(path)
            assert response.status_code==200 and response.headers['cache-control']=='no-store'


def test_explicit_proxy_host_keeps_origin_csrf_and_host_boundaries(app):
    from backend.platform import create_app
    from fastapi.testclient import TestClient
    settings=app.state.settings
    settings.environment='production';settings.secure_cookie=True
    settings.origin='https://campusfind.example';settings.trusted_hosts=('private-tunnel.example',)
    production=create_app(settings)
    try:
        with TestClient(production,base_url='https://private-tunnel.example') as client:
            assert client.get('/health/live').status_code==200
            assert client.get('/health/live',headers={'host':'attacker.example'}).status_code==400
            assert client.post('/api/suggest-crops',headers={'origin':'https://attacker.example'}).status_code==403
            assert client.get('/api/v1/items').status_code==401
    finally:production.state.engine.dispose()


@pytest.mark.parametrize('host',['*','*.example.com','https://example.com','example.com:443','example.com/path'])
def test_proxy_host_config_refuses_broad_or_invalid_values(host,tmp_path,monkeypatch):
    from backend.settings import Settings
    monkeypatch.setattr('backend.settings.load_env',lambda:None)
    monkeypatch.setenv('CAMPUSFIND_ENV','production');monkeypatch.setenv('CAMPUSFIND_ORIGIN','https://campusfind.example')
    monkeypatch.setenv('CAMPUSFIND_SECURE_COOKIE','true');monkeypatch.setenv('CAMPUSFIND_STORAGE',str(tmp_path))
    monkeypatch.setenv('CAMPUSFIND_TRUSTED_HOSTS',host)
    with pytest.raises(ValueError,match='Trusted hosts'):Settings.from_env()
