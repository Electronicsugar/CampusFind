"""Low-cardinality operational telemetry; no URLs, IDs, evidence or credentials."""
import json,logging,time
from threading import Lock
from datetime import timedelta
from tempfile import TemporaryFile
from fastapi import APIRouter,Depends,Request
from fastapi.responses import JSONResponse
from sqlalchemy import select,func,text
from backend.auth import admin
from backend.database import get_db
from backend.models import MatchJob,FileDeletion,WorkerState,now

router=APIRouter();LOG=logging.getLogger('campusfind.operations')
_lock=Lock();_counts={};_elapsed={}


def observe(request,status,seconds):
    route=getattr(request.scope.get('route'),'path','unmatched')
    key=(route,str(status//100)+'xx')
    with _lock:
        _counts[key]=_counts.get(key,0)+1;_elapsed[key]=_elapsed.get(key,0)+seconds
    LOG.info(json.dumps({'event':'http_request','route':route,'status':status,'elapsed_ms':round(seconds*1000,2)},separators=(',',':')))


@router.get('/health/live')
def live():return {'status':'alive'}


@router.get('/health/ready')
def ready(request:Request):
    try:
        if not request.app.state.sessions:raise RuntimeError()
        with request.app.state.sessions() as db:
            from alembic.script import ScriptDirectory
            from alembic.config import Config
            from backend.settings import ROOT
            config=Config(str(ROOT/'alembic.ini'));config.set_main_option('script_location',str(ROOT/'migrations'))
            if db.scalar(text('SELECT version_num FROM alembic_version'))!=ScriptDirectory.from_config(config).get_current_head():raise RuntimeError()
            beat=db.get(WorkerState,'matching')
            if request.app.state.settings.environment=='production' and (not beat or beat.status=='stopped' or beat.heartbeat<now()-timedelta(minutes=6)):raise RuntimeError()
        root=request.app.state.settings.storage;root.mkdir(parents=True,exist_ok=True)
        with TemporaryFile(dir=root) as stream:stream.write(b'ready');stream.flush()
        return {'status':'ready'}
    except Exception:return JSONResponse({'status':'unavailable'},status_code=503)


@router.get('/api/v1/admin/operations')
def operations(request:Request,user=Depends(admin),db=Depends(get_db)):
    counts=dict(db.execute(select(MatchJob.status,func.count()).group_by(MatchJob.status)).all())
    oldest=db.scalar(select(func.min(MatchJob.updated_at)).where(MatchJob.status=='PENDING'))
    beat=db.get(WorkerState,'matching')
    with _lock:
        metrics=[{'route':route,'status_class':status,'requests':count,'total_seconds':round(_elapsed[(route,status)],3)} for (route,status),count in _counts.items()]
    return {'jobs':counts,'oldest_pending_seconds':max(0,(now()-oldest).total_seconds()) if oldest else None,
            'pending_file_deletions':db.scalar(select(func.count()).select_from(FileDeletion)),
            'worker':{'status':beat.status,'age_seconds':max(0,(now()-beat.heartbeat).total_seconds())} if beat else None,
            'http_process_metrics':metrics,'notice':'HTTP counters are per process and reset on restart. No personal data is logged.'}
