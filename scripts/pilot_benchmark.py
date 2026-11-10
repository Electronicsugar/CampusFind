"""Isolated PostgreSQL infrastructure benchmark. Never writes application tables."""
import argparse,json,time,uuid,tempfile,hashlib,statistics
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta,date
import cv2,numpy as np,psutil
from sqlalchemy import create_engine,text,event,select,func
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from backend.settings import Settings
from backend.platform import create_app
from backend.models import User,Session,Item,ItemImage,MatchJob,MatchSuggestion,now,uid
from backend.auth import digest


@contextmanager
def isolated():
    url=Settings.from_env().database_url
    if not url.startswith('postgresql+psycopg://'):raise RuntimeError('PostgreSQL required')
    control=create_engine(url);schema='cf_bench_'+uuid.uuid4().hex
    with control.begin() as db:db.execute(text('CREATE SCHEMA '+schema))
    scoped=make_url(url).update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    app=None
    try:
        config=Config('alembic.ini');config.set_main_option('sqlalchemy.url',scoped.replace('%','%%'));command.upgrade(config,'head')
        with tempfile.TemporaryDirectory(prefix='cf_bench_') as folder:
            app=create_app(Settings(database_url=scoped,storage=Path(folder),origin='http://testserver',testing=True,background_matching=False))
            yield app
    finally:
        if app:app.state.engine.dispose()
        assert schema.startswith('cf_bench_') and len(schema)==41 and schema[9:].isalnum()
        with control.begin() as db:db.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        control.dispose()


class SyntheticEncoder:
    model_version='synthetic-infrastructure-only-v1'
    calls=0
    def describe(self,region):
        self.calls+=1
        seed=int.from_bytes(hashlib.sha256(region.tobytes()).digest()[:4],'little')
        vector=np.random.default_rng(seed).normal(size=512).astype(np.float32);vector/=np.linalg.norm(vector)
        return {'vector':vector,'label':'bottle','margin':.1}


def distribution(values):
    return {'samples':len(values),'median_ms':round(statistics.median(values),2),'p95_ms':round(float(np.percentile(values,95)),2)}


def run(size):
    import backend.matching as matching
    with isolated() as app:
        factory=app.state.sessions;settings=app.state.settings
        query_id=uid();owner=uid();other=uid();token=uuid.uuid4().hex;csrf=uuid.uuid4().hex
        blobs=[]
        for n in range(16):
            image=np.random.default_rng(n).integers(0,255,(96,128,3),dtype=np.uint8)
            blobs.append(cv2.imencode('.jpg',image)[1].tobytes())
        with factory.begin() as db:
            db.add_all([User(id=owner,email='bench-owner@example.invalid',display_name='Synthetic',password_hash='disabled'),User(id=other,email='bench-other@example.invalid',display_name='Synthetic',password_hash='disabled')]);db.flush()
            db.add(Session(token_hash=digest(token),csrf=csrf,user_id=owner,expires_at=now()+timedelta(hours=1)))
            items=[];photos=[]
            for n in range(size):
                iid=query_id if n==0 else uid();key=uuid.uuid4().hex+'.jpg';blob=blobs[n%16]
                (settings.storage/key).write_bytes(blob)
                items.append(dict(id=iid,owner_id=owner if n==0 else other,kind='LOST' if n==0 else 'FOUND',title=f'Synthetic bottle {n}',category='bottle',description='Synthetic workload, not a real object.',location='Synthetic library',event_date=date(2026,1,1),expires_at=now()+timedelta(days=1)))
                photos.append(dict(id=uid(),item_id=iid,storage_key=key,content_hash=hashlib.sha256(blob).hexdigest(),position=0))
            db.execute(__import__('sqlalchemy').insert(Item),items);db.execute(__import__('sqlalchemy').insert(ItemImage),photos)
            db.add(MatchJob(item_id=query_id))
        queries=[]
        def before(conn,cursor,statement,parameters,context,many):context._bench_start=time.perf_counter()
        def after(conn,cursor,statement,parameters,context,many):queries.append((time.perf_counter()-context._bench_start)*1000)
        event.listen(app.state.engine,'before_cursor_execute',before);event.listen(app.state.engine,'after_cursor_execute',after)
        def client():
            c=TestClient(app);c.cookies.set('campusfind_session',token);c.headers.update({'origin':settings.origin,'x-csrf-token':csrf});return c
        def search(_):
            with client() as c:
                start=time.perf_counter();r=c.get('/api/v1/items?q=bottle');assert r.status_code==200
                return (time.perf_counter()-start)*1000
        sequential=[search(n) for n in range(10)];search_queries=len(queries);sql_search=distribution(queries)
        with ThreadPoolExecutor(max_workers=8) as pool:concurrent=list(pool.map(search,range(32)))
        upload=[]
        with client() as c:
            for n in range(3):
                start=time.perf_counter();r=c.post('/api/v1/items',data={'metadata':json.dumps({'kind':'LOST','title':'Synthetic upload','category':'bottle','description':'Synthetic upload performance check.','location':'Test library','event_date':'2026-01-01','consent':True}),'selections':'[{"confirmed":true,"box":null}]'},files={'photos':('fixture.jpg',blobs[0],'image/jpeg')});assert r.status_code==201,r.text
                upload.append((time.perf_counter()-start)*1000)
        model=SyntheticEncoder();matching.get_model=lambda:model
        process=psutil.Process();rss_before=process.memory_info().rss;cpu_before=sum(process.cpu_times()[:2]);queries.clear()
        from threading import Event,Thread
        stop=Event();peak=[rss_before]
        def sample():
            while not stop.wait(.05):peak[0]=max(peak[0],process.memory_info().rss)
        sampler=Thread(target=sample,daemon=True);sampler.start();start=time.perf_counter()
        try:ok=matching.process_job(factory,settings,query_id)
        finally:elapsed=time.perf_counter()-start;stop.set();sampler.join()
        assert ok,'Matching failed'
        with factory() as db:pair_count=db.scalar(select(func.count()).select_from(MatchSuggestion))
        result={'reports':size,'fixture':'96x128 synthetic JPEG, one photo/report; deterministic 512d encoder double','search':distribution(sequential),'search_sql':sql_search,'search_queries_per_request':search_queries/10,'concurrent_search_8_users':distribution(concurrent),'upload':distribution(upload),'matching':{'seconds':round(elapsed,3),'jobs_per_minute':round(60/elapsed,3),'cpu_seconds':round(sum(process.cpu_times()[:2])-cpu_before,3),'peak_process_rss_mb':round(peak[0]/1024**2,2),'rss_growth_mb':round((peak[0]-rss_before)/1024**2,2),'sql_statements':len(queries),'sql':distribution(queries),'encoder_calls':model.calls,'pair_rows':pair_count}}
        print(json.dumps(result),flush=True);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--sizes',type=int,nargs='+',default=[100,1000,5000]);args=parser.parse_args()
    if any(n not in {100,1000,5000} for n in args.sizes):raise SystemExit('Only bounded pilot sizes allowed')
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise SystemExit('Choose a new results path; refusing to overwrite')
    results=[]
    for n in args.sizes:
        results.append(run(n));output.write_text(json.dumps({'kind':'synthetic infrastructure; not accuracy or real CLIP throughput','results':results},indent=2))
