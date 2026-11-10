"""Durable local matching/retention worker: python -m backend.worker [--once]."""
import argparse
import time
import signal
from threading import Event
from types import SimpleNamespace
from sqlalchemy import select,delete
from backend.database import configure,maintenance_guard
from backend.models import Item,ItemImage,ClaimRequest,MatchJob,ModerationRecord,Session,RateLimit,WorkerState,now
from backend.reports import clear_matches
from backend import storage
from backend.matching import process_job


def purge(factory,settings):
    keys=[]
    with factory.begin() as db:
        maintenance_guard(db)
        for item in db.scalars(select(Item).where(Item.expires_at<=now(),Item.deleted_at.is_(None)).with_for_update(skip_locked=True)):
            photos=list(db.scalars(select(ItemImage).where(ItemImage.item_id==item.id)))
            clear_matches(db,[p.id for p in photos])
            for photo in photos:storage.queue_deletion(db,photo.storage_key);db.delete(photo)
            for claim in db.scalars(select(ClaimRequest).where(ClaimRequest.item_id==item.id)):
                claim.evidence='Removed after retention period';claim.review_note=''
                if claim.status in {'PENDING','APPROVED'}:claim.status='WITHDRAWN'
            item.deleted_at=now();item.state='CLOSED';item.title='Expired report';item.description='Removed';item.location='Removed'
            db.add(ModerationRecord(action='retention_expired',item_id=item.id))
        db.execute(delete(Session).where(Session.expires_at<=now()))
        db.execute(delete(RateLimit).where(RateLimit.expires_at<=now()))
    storage.drain_deletions(factory,settings)
    # Clean files orphaned by interrupted writes/deletions after a one-day grace.
    with factory.begin() as db:
        maintenance_guard(db);referenced=set(db.scalars(select(ItemImage.storage_key)))
        if settings.storage.exists():
            for path in settings.storage.iterdir():
                if path.suffix not in {'.jpg','.part'} or path.is_symlink():continue
                if path.name not in referenced and path.stat().st_mtime<time.time()-86400:
                    if path.suffix=='.jpg':storage.remove(settings,path.name)
                    elif len(path.stem)==32 and all(c in '0123456789abcdef' for c in path.stem):path.unlink(missing_ok=True)


def heartbeat(factory,status):
    with factory.begin() as db:
        if db.bind.dialect.name=='postgresql':
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        db.execute(insert(WorkerState).values(name='matching',status=status,heartbeat=now()).on_conflict_do_update(index_elements=['name'],set_={'status':status,'heartbeat':now()}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    app=SimpleNamespace(state=SimpleNamespace());configure(app)
    if not app.state.sessions:raise SystemExit('Configure DATABASE_URL and run migrations first.')
    stopping=Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stopping.set())
    while not stopping.is_set():
        try:
            heartbeat(app.state.sessions,'busy')
            purge(app.state.sessions,app.state.settings)
            with app.state.sessions() as db:
                jobs=list(db.scalars(select(MatchJob.item_id).where(MatchJob.status=='PENDING').order_by(MatchJob.updated_at).limit(20)))
            for iid in jobs:
                if stopping.is_set():break
                heartbeat(app.state.sessions,'busy');process_job(app.state.sessions,app.state.settings,iid)
            heartbeat(app.state.sessions,'idle')
        except Exception:print('Worker unavailable; check database and storage. Retrying in 10 seconds.',flush=True)
        if args.once:break
        stopping.wait(10)
    heartbeat(app.state.sessions,'stopped')
