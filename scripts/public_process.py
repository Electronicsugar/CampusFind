"""Run an existing app/worker against an explicit private public-instance config."""
import argparse,json,os
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True,type=Path);parser.add_argument('mode',choices=['web','worker']);args=parser.parse_args()
    config=json.loads(args.config.read_text(encoding='utf-8'))
    required={'DATABASE_URL','CAMPUSFIND_ORIGIN','CAMPUSFIND_STORAGE','CAMPUSFIND_TRUSTED_HOSTS'}
    if not required<=config.keys():raise SystemExit('Incomplete explicit public instance configuration.')
    os.environ.update(config)
    os.environ.update(CAMPUSFIND_ENV='production',CAMPUSFIND_SECURE_COOKIE='true',CAMPUSFIND_BACKGROUND_MATCHING='false')
    if args.mode=='web':
        import uvicorn
        uvicorn.run('backend.main:app',host='127.0.0.1',port=8020,proxy_headers=False,access_log=False,server_header=False,limit_concurrency=64)
    else:
        import runpy
        runpy.run_module('backend.worker',run_name='__main__')

if __name__=='__main__':main()
