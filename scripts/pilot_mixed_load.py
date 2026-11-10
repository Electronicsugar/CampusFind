"""100 mixed reports, real local CLIP, queue drain and concurrent browsing."""
import json,time,uuid,threading,hashlib
from datetime import timedelta,date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np,cv2,psutil
from sqlalchemy import insert,select,func
from fastapi.testclient import TestClient
from scripts.pilot_benchmark import isolated,distribution
from backend.models import User,Session,Item,ItemImage,MatchJob,MatchSuggestion,now,uid
from backend.auth import digest
from backend.matching import process_job


def main():
    output=Path('reports/phase5-mixed-real.json')
    if output.exists():raise RuntimeError('Refusing to overwrite results')
    with isolated() as app:
        owner=uid();other=uid();token=uid();csrf=uid();items=[];photos=[];blobs=[]
        for n in range(100):
            iid=uid();key=uuid.uuid4().hex+'.jpg'
            image=np.random.default_rng(n+100).integers(0,255,(768,1024,3),dtype=np.uint8)
            # Synthetic texture is deliberately not an object-recognition test.
            blob=cv2.imencode('.jpg',image)[1].tobytes();blobs.append(blob)
            (app.state.settings.storage/key).write_bytes(blob)
            items.append(dict(id=iid,owner_id=owner if n%2 else other,kind='LOST' if n%2 else 'FOUND',title=f'Synthetic fixture {n}',category='other',description='Synthetic workload only',location='Test library',event_date=date(2026,1,1),expires_at=now()+timedelta(days=1)))
            photos.append(dict(id=uid(),item_id=iid,storage_key=key,content_hash=hashlib.sha256(blob).hexdigest(),position=0))
        with app.state.sessions.begin() as db:
            db.add_all([User(id=owner,email='mixed-a@example.invalid',display_name='Synthetic',password_hash='disabled'),User(id=other,email='mixed-b@example.invalid',display_name='Synthetic',password_hash='disabled')]);db.flush()
            db.execute(insert(Item),items);db.execute(insert(ItemImage),photos)
            db.execute(insert(MatchJob),[{'item_id':row['id']} for row in items])
            db.add(Session(token_hash=digest(token),user_id=owner,csrf=csrf,expires_at=now()+timedelta(hours=1)))
        def client():
            c=TestClient(app);c.cookies.set('campusfind_session',token);c.headers.update({'origin':app.state.settings.origin,'x-csrf-token':csrf});return c
        search=[]
        def browse(_):
            with client() as c:
                started=time.perf_counter();r=c.get('/api/v1/items?q=fixture');assert r.status_code==200
                return (time.perf_counter()-started)*1000
        process=psutil.Process();peak=[process.memory_info().rss];stopping=threading.Event()
        def sample():
            while not stopping.wait(.05):peak[0]=max(peak[0],process.memory_info().rss)
        sampler=threading.Thread(target=sample,daemon=True);sampler.start();cpu=sum(process.cpu_times()[:2]);start=time.perf_counter();durations=[]
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                requests=[pool.submit(browse,n) for n in range(64)]
                for row in items:
                    began=time.perf_counter();assert process_job(app.state.sessions,app.state.settings,row['id']);durations.append((time.perf_counter()-began)*1000)
                search=[future.result() for future in requests]
            queue_seconds=time.perf_counter()-start
        finally:stopping.set();sampler.join()
        uploads=[]
        with client() as c:
            for n in range(3):
                began=time.perf_counter()
                response=c.post('/api/v1/items',data={'metadata':json.dumps({'kind':'LOST','title':'Synthetic upload','category':'other','description':'Synthetic two-photo upload','location':'Test','event_date':'2026-01-01','consent':True}),'selections':json.dumps([{'confirmed':True,'box':None}]*2)},files=[('photos',('a.jpg',blobs[0],'image/jpeg')),('photos',('b.jpg',blobs[1],'image/jpeg'))])
                assert response.status_code==201;uploads.append((time.perf_counter()-began)*1000)
        with app.state.sessions() as db:pair_count=db.scalar(select(func.count()).select_from(MatchSuggestion))
        result={'reports':100,'lost':50,'found':50,'unique_photos':100,'photo_size':'1024x768 synthetic texture','encoder':'real existing CLIP','queue_jobs':100,'queue_seconds':round(queue_seconds,3),'jobs_per_minute':round(6000/queue_seconds,2),'job_latency':distribution(durations),'concurrent_search_8_users_64_requests':distribution(search),'two_photo_upload':distribution(uploads),'directed_pair_rows':pair_count,'cpu_seconds_including_uploads':round(sum(process.cpu_times()[:2])-cpu,3),'peak_worker_process_rss_mb':round(peak[0]/1024**2,2),'accuracy':'not evaluated'}
        output.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':main()
