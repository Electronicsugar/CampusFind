"""Read-only explicit-target preflight. Never loads .env or provisions resources."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def inspect(config, environ=None):
    environ=os.environ if environ is None else environ
    checks=[]
    def add(name,status):checks.append({'check':name,'status':status})
    required={'profile','database_env','expected_database','expected_user','expected_origin','origin',
              'storage','backup','proxy_ips','secure_cookie','environment','worker_mode','expected_host','expected_port'}
    if not isinstance(config,dict) or not required<=config.keys():
        return [{'check':'required_configuration','status':'FAIL'}]
    add('placeholder_free','FAIL' if any(token in str(config).lower() for token in ('replace','changeme')) else 'PASS')
    add('profile','PASS' if config['profile'] in ('researcher-dry-run','authorized-student-pilot') else 'FAIL')
    add('production_controls','PASS' if config['environment']=='production' and config['secure_cookie'] is True and config['worker_mode']=='separate' else 'FAIL')
    try:
        origin=urlsplit(config['origin'])
        safe=(config['origin']==config['expected_origin'] and origin.scheme=='https' and origin.hostname
              and not any((origin.username,origin.password,origin.path,origin.query,origin.fragment)))
    except (ValueError,TypeError):safe=False
    add('exact_https_origin','PASS' if safe else 'FAIL')
    try:
        proxies=config['proxy_ips'];assert isinstance(proxies,list)
        for ip in proxies:ipaddress.ip_address(ip)
        add('explicit_proxy_ips','PASS' if proxies else 'WARNING')
    except (ValueError,TypeError,AssertionError):add('explicit_proxy_ips','FAIL')
    try:
        url=make_url(environ.get(config['database_env'],''))
        safe=(url.drivername=='postgresql+psycopg' and url.database==config['expected_database']
              and url.username==config['expected_user'] and bool(url.password) and bool(url.host)
              and url.host==config['expected_host'] and (url.port or 5432)==config['expected_port']
              and (not url.query if url.host in ('127.0.0.1','localhost','::1') else url.query.get('sslmode')=='verify-full' and set(url.query)<={'sslmode','sslrootcert'}) and len(url.password)>=20 and not any(x in url.password.lower() for x in ('example','changeme','test only')))
        # Nonlocal database transport requires a separately verified TLS policy.
        add('database_transport','PASS' if url.host in ('127.0.0.1','localhost','::1') else 'NOT_VERIFIED')
    except (ValueError,TypeError,KeyError,ArgumentError):safe=False
    add('explicit_database_secret_and_target','PASS' if safe else 'FAIL')
    try:
        storage=Path(config['storage']);backup=Path(config['backup'])
        root=Path(__file__).resolve().parents[1]
        def bad(p):return (not p.is_absolute() or root==p.resolve() or root in p.resolve().parents
                           or any(s.lower() in ('onedrive','dropbox','google drive','public','wwwroot','static') or s.lower().startswith('onedrive -') for s in p.parts))
        nested=storage.resolve()==backup.resolve() or storage.resolve() in backup.resolve().parents or backup.resolve() in storage.resolve().parents
        add('separate_private_paths','FAIL' if bad(storage) or bad(backup) or nested else 'PASS')
        add('storage_exists','PASS' if storage.is_dir() and backup.is_dir() else 'FAIL')
        add('storage_not_symlink','FAIL' if any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for target in (storage,backup) for p in (target,*target.parents)) else 'PASS')
    except (ValueError,TypeError,OSError):add('private_storage','FAIL')
    for name in ('filesystem_acl','cloud_sync_exclusion','trusted_tls_proxy','restricted_network','worker_supervision','alert_delivery','institutional_approval'):
        add(name,'NOT_VERIFIED')
    return checks


def inspect_database(config,environ=None):
    """Only connect after static checks; transaction explicitly read only."""
    from sqlalchemy import create_engine,text
    env=os.environ if environ is None else environ
    if any(c['status']=='FAIL' for c in inspect(config,env)):
        return [{'check':'database_connection_preconditions','status':'FAIL'}]
    engine=None
    try:
        engine=create_engine(env[config['database_env']],connect_args={'connect_timeout':5})
        with engine.connect() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            db.execute(text("SET LOCAL statement_timeout='5s'"))
            identity=db.execute(text('SELECT current_database(),current_user,current_schema()')).one()
            flags=db.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
            revision=db.scalar(text('SELECT version_num FROM alembic_version'))
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            head=ScriptDirectory.from_config(Config('alembic.ini')).get_current_head()
            owns=db.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_class WHERE relnamespace='public'::regnamespace AND relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))"))
            can_create=db.scalar(text("SELECT has_schema_privilege(current_user,'public','CREATE')"))
            return [{'check':'connected_identity','status':'PASS' if tuple(identity)==(config['expected_database'],config['expected_user'],'public') else 'FAIL'},
                    {'check':'restricted_role','status':'FAIL' if any(flags) or owns or can_create else 'PASS'},
                    {'check':'schema_revision','status':'PASS' if revision==head else 'FAIL'}]
    except Exception:
        return [{'check':'database_connectivity_or_query','status':'FAIL'}] # Never echo DSNs/errors.
    finally:
        if engine:engine.dispose()


def canary():
    """Single synthetic CLIP and NanoDet calls; no downloads/recognition labels."""
    import time
    import numpy as np
    from backend.semantic import MODEL_DIR,get_model
    from backend.detection import ROOT
    required=[MODEL_DIR/n for n in ('vision_model_quantized.onnx','text_model_quantized.onnx','tokenizer.json','preprocessor_config.json')]
    required.append(ROOT/'nanodet'/'object_detection_nanodet_2022nov.onnx')
    if any(not p.is_file() for p in required):return {'status':'FAIL','stage':'missing_artifact'}
    started=time.perf_counter()
    try:
        model=get_model()
        from backend.nanodet import NanoDetector
        detector=NanoDetector()
    except Exception:return {'status':'FAIL','stage':'model_loading'}
    loaded=time.perf_counter()
    try:
        image=np.random.default_rng(82).integers(0,256,(320,320,3),dtype=np.uint8)
        result=model.describe(image);detector.detect(image)
        assert np.isfinite(result['vector']).all()
    except Exception:return {'status':'FAIL','stage':'runtime_inference'}
    return {'status':'PASS','stage':'synthetic_cpu_inference','load_seconds':round(loaded-started,3),
            'inference_seconds':round(time.perf_counter()-loaded,3),'model_fingerprint':model.model_version,
            'scope':'one generated input; no accuracy or capacity evidence'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path);p.add_argument('--connect',action='store_true');p.add_argument('--canary',action='store_true');a=p.parse_args()
    if a.canary and not a.config:result={'canary':canary()}
    else:
        try:config=json.loads(a.config.read_text(encoding='utf-8'));checks=inspect(config)
        except (AttributeError,OSError,ValueError):p.exit(2,'Cannot read explicit preflight configuration. No defaults used.\n')
        if a.connect:checks+=inspect_database(config)
        result={'checks':checks,'note':'PASS checks do not verify unmeasured deployment controls.'}
        if a.canary:result['canary']=canary()
    print(json.dumps(result,indent=2,sort_keys=True))
    return int(any(c['status']=='FAIL' for c in result.get('checks',[])) or result.get('canary',{}).get('status')=='FAIL')


if __name__=='__main__':raise SystemExit(main())
