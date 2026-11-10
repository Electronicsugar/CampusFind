"""Optional portable Windows PostgreSQL, using an explicitly installed EDB runtime.

No download or system-service installation. State is confined to .local.
"""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
from backend.settings import ROOT,load_env


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','stop','status']);args=parser.parse_args();load_env()
    folder=ROOT/'.local';runtime=folder/'postgres'/'pgsql'/'bin';data=folder/'pgdata';secret=folder/'pg-admin-password'
    def run(arguments):
        # The server inherits handles on Windows: use a file, not pipes that
        # communicate() would wait to close for the lifetime of PostgreSQL.
        output=folder/'pg-command.log'
        with output.open('w',encoding='utf-8') as stream:
            result=subprocess.run([str(a) for a in arguments],stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
        message=output.read_text(encoding='utf-8',errors='replace')
        if result.returncode:raise SystemExit(message)
        print(message.strip(),flush=True)
    if not (runtime/'pg_ctl.exe').exists():raise SystemExit('Install the official EDB Windows runtime in .local/postgres/pgsql first, or use Docker Compose.')
    if args.action=='start':
        if not data.exists():
            secret.write_text(secrets.token_urlsafe(32),encoding='utf-8')
            run([runtime/'initdb.exe','-D',data,'-U','campusfind_admin','--pwfile',secret,'--auth=scram-sha-256','--encoding=UTF8','--locale=C'])
        status=subprocess.run([str(runtime/'pg_ctl.exe'),'-D',str(data),'status'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if status.returncode:run([runtime/'pg_ctl.exe','-D',data,'-l',folder/'postgres.log','-o','-h 127.0.0.1 -p 5433','start'])
        import psycopg
        from psycopg import sql
        with psycopg.connect(host='127.0.0.1',port=5433,dbname='postgres',user='campusfind_admin',password=secret.read_text(),autocommit=True) as conn:
            if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',('campusfind',)).fetchone():
                conn.execute(sql.SQL('CREATE ROLE campusfind LOGIN PASSWORD {}').format(sql.Literal(os.environ['POSTGRES_PASSWORD'])))
            if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',('campusfind',)).fetchone():
                conn.execute('CREATE DATABASE campusfind OWNER campusfind')
        print('PostgreSQL ready on 127.0.0.1:5433; application role is not a superuser.')
    elif args.action=='stop':run([runtime/'pg_ctl.exe','-D',data,'stop','-m','fast'])
    else:run([runtime/'pg_ctl.exe','-D',data,'status'])
