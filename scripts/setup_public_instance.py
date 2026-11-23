"""Create a NEW isolated local public-demo cluster. Never resets/reuses a target."""
import argparse,json,os,secrets,subprocess,uuid
from pathlib import Path
from urllib.parse import urlsplit

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--origin',required=True);p.add_argument('--tunnel',required=True);a=p.parse_args()
    for value in (a.origin,a.tunnel):
        u=urlsplit(value)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.path or u.query or u.fragment:p.error('Use exact HTTPS origins without credentials or path.')
    root=Path(os.environ['LOCALAPPDATA'])/'CampusFind'/'public'/uuid.uuid4().hex
    root.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];runtime=repo/'.local/postgres/pgsql/bin'
    if not (runtime/'initdb.exe').is_file():raise SystemExit('Installed portable PostgreSQL runtime required.')
    # Restrict new instance before writing credentials. No existing paths are changed.
    sid=subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True).strip().split(',')[-1].strip('"')
    for args in (['/inheritance:r'],['/grant:r','*'+sid+':(OI)(CI)F','*S-1-5-18:(OI)(CI)F']):
        subprocess.run(['icacls',str(root),*args],check=True,stdout=subprocess.DEVNULL)
    operator=secrets.token_urlsafe(36);migration=secrets.token_urlsafe(36);application=secrets.token_urlsafe(36)
    pw=root/'init-password';pw.write_text(operator,encoding='utf-8')
    def pg(args):
        with (root/'postgres-command.log').open('a') as log:
            result=subprocess.run([str(runtime/args[0]),*args[1:]],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
        if result.returncode:raise RuntimeError('PostgreSQL setup failed; inspect restricted local log.')
    pg(['initdb.exe','-D',str(root/'pgdata'),'-U','campusfind_operator','--pwfile',str(pw),'--auth=scram-sha-256','--encoding=UTF8','--locale=C'])
    pw.unlink()
    pg(['pg_ctl.exe','-D',str(root/'pgdata'),'-l',str(root/'postgres.log'),'-o','-h 127.0.0.1 -p 5434','start'])
    import psycopg
    from psycopg import sql
    with psycopg.connect(host='127.0.0.1',port=5434,dbname='postgres',user='campusfind_operator',password=operator,autocommit=True) as db:
        for name,password in [('campusfind_migrate',migration),('campusfind_app',application)]:
            db.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(name),sql.Literal(password)))
        db.execute('CREATE DATABASE campusfind_public OWNER campusfind_migrate')
        db.execute('REVOKE ALL ON DATABASE campusfind_public FROM PUBLIC')
        db.execute('GRANT CONNECT ON DATABASE campusfind_public TO campusfind_app')
    def url(user,password):return f'postgresql+psycopg://{user}:{password}@127.0.0.1:5434/campusfind_public'
    migration_url=url('campusfind_migrate',migration)
    from alembic.config import Config
    from alembic import command
    config=Config(str(repo/'alembic.ini'));config.set_main_option('sqlalchemy.url',migration_url);command.upgrade(config,'head')
    with psycopg.connect(host='127.0.0.1',port=5434,dbname='campusfind_public',user='campusfind_migrate',password=migration,autocommit=True) as db:
        db.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        db.execute('GRANT USAGE ON SCHEMA public TO campusfind_app')
        db.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO campusfind_app')
        db.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO campusfind_app')
    (root/'images').mkdir();(root/'backups').mkdir()
    runtime_config={'DATABASE_URL':url('campusfind_app',application),'CAMPUSFIND_ORIGIN':a.origin,'CAMPUSFIND_STORAGE':str(root/'images'),
                    'CAMPUSFIND_TRUSTED_HOSTS':urlsplit(a.tunnel).hostname+',localhost','CAMPUSFIND_RETENTION_DAYS':'7'}
    (root/'runtime.json').write_text(json.dumps(runtime_config,indent=2),encoding='utf-8')
    (root/'operator.json').write_text(json.dumps({'operator_password':operator,'migration_url':migration_url}),encoding='utf-8')
    pointer=repo/'.local/public-host-pointer.json';pointer.write_text(json.dumps({'directory':str(root),'origin':a.origin,'tunnel':a.tunnel}),encoding='utf-8')
    print('Created isolated public-demo database and restricted non-synced storage. Private runtime configuration:',root/'runtime.json')

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('Public instance setup did not complete. No existing instance was reset; inspect private setup logs before retrying.')
