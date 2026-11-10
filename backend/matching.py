"""Durable per-photograph CLIP retrieval; no experimental fusion or identity claim."""
import logging
import hashlib,json,time
from collections import OrderedDict
import numpy as np
from fastapi import APIRouter,Depends,HTTPException,Request,BackgroundTasks
from sqlalchemy import select,delete,text,update,case,func
from backend.auth import current,throttle
from backend.database import get_db,maintenance_guard
from backend.models import Item,ItemImage,MatchJob,MatchSuggestion,Notification,now,uid
from backend.reports import ACTIVE,find_item,images,queue,schedule,visible
from backend.claims import notify
from backend import storage
from backend.vision import prepare,appearance_descriptor,appearance_from_descriptors
from backend.semantic import get_model,PREPROCESSING_VERSION
from backend.embedding_cache import image_key
from backend.gallery import rank_gallery,score_descriptions

LOG=logging.getLogger(__name__)
router=APIRouter(prefix='/api/v1',tags=['potential matches'])


class StoredEncoder:
    def __init__(self,model):self.model=model;self.rows={}
    def register(self,row,region):self.rows[image_key(region,self.model.model_version,PREPROCESSING_VERSION)]=row
    def describe(self,region):
        key=image_key(region,self.model.model_version,PREPROCESSING_VERSION);row=self.rows[key]
        if row.embedding_key==key.hex() and row.descriptor:
            result=dict(row.descriptor);result['vector']=np.asarray(result['vector'],dtype=np.float32);return result
        result=self.model.describe(region)
        row.descriptor={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in result.items()}
        row.embedding_key=key.hex()
        return result


def write_pair(db,q,c,row,version):
    existing=db.scalar(select(MatchSuggestion).where(MatchSuggestion.query_image_id==q.id,MatchSuggestion.candidate_image_id==c.id))
    if existing is None:
        existing=MatchSuggestion(query_image_id=q.id,candidate_image_id=c.id);db.add(existing)
    existing.similarity=row['semantic_similarity'];existing.appearance=row['appearance_percent']
    existing.relevance=row['relevance'];existing.reason=row['relevance_reason'];existing.model_version=version


class PreparedCache:
    """Immutable stored pixels + crop + both descriptor versions; bounded RAM."""
    def __init__(self,model,settings):self.model=model;self.settings=settings;self.memory=OrderedDict()
    def get(self,row):
        signature=hashlib.sha256(json.dumps([row.content_hash,row.crop,self.model.model_version,PREPROCESSING_VERSION,'appearance-v1'],separators=(',',':')).encode()).hexdigest()
        if row.cache_signature!=signature or row.descriptor is None or row.appearance is None:
            if signature in self.memory:
                descriptor,appearance,key=self.memory[signature];self.memory.move_to_end(signature)
            else:
                region=prepare(storage.read(self.settings,row.storage_key),row.crop,normalize=False)[0]
                encoder=StoredEncoder(self.model);encoder.register(row,region);result=encoder.describe(region)
                descriptor={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in result.items()}
                appearance=[part.tolist() if part is not None else None for part in appearance_descriptor(region)]
                key=image_key(region,self.model.model_version,PREPROCESSING_VERSION).hex()
                self.memory[signature]=(descriptor,appearance,key)
                if len(self.memory)>256:self.memory.popitem(last=False)
            row.descriptor=descriptor;row.appearance=appearance;row.embedding_key=key;row.cache_signature=signature
        result=dict(row.descriptor);result['vector']=np.asarray(result['vector'],dtype=np.float32)
        return result,tuple(np.asarray(part,dtype=float) if part is not None else None for part in row.appearance)


def bulk_pairs(db,rows):
    if not rows:return
    if db.bind.dialect.name=='postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    for offset in range(0,len(rows),200):
        statement=insert(MatchSuggestion).values(rows[offset:offset+200])
        db.execute(statement.on_conflict_do_update(index_elements=['query_image_id','candidate_image_id'],set_={k:getattr(statement.excluded,k) for k in ['similarity','appearance','relevance','reason','model_version']}))


def pair_values(query,candidate,row,version):
    return dict(id=uid(),query_image_id=query.id,candidate_image_id=candidate.id,similarity=row['semantic_similarity'],appearance=row['appearance_percent'],relevance=row['relevance'],reason=row['relevance_reason'],model_version=version)


def process_job(factory,settings,iid):
    """Atomic results, one CPU job across workers, bounded batches and runtime.

    Parent-before-job locking matches report mutations. Candidate parents are
    locked before reading image versions, preventing crop/delete races. A killed
    process rolls back to PENDING; only a completed transaction publishes results.
    """
    started=time.perf_counter();attempt_version=None;pairs_scored=0
    try:
        with factory.begin() as db:
            maintenance_guard(db)
            if db.bind.dialect.name=='postgresql' and not db.scalar(text('SELECT pg_try_advisory_xact_lock(72439106)')):return False
            item=db.scalar(select(Item).where(Item.id==iid).with_for_update())
            job=db.scalar(select(MatchJob).where(MatchJob.item_id==iid).with_for_update())
            if not job or job.status!='PENDING':return False
            attempt_version=job.updated_at
            if not item or item.hidden or item.deleted_at or item.expires_at<=now() or item.state not in ACTIVE:
                job.status='DONE';job.error='';return True
            model=get_model();cache=PreparedCache(model,settings);query_images=images(db,item)
            queries=[(q,*cache.get(q)) for q in query_images]
            db.execute(delete(MatchSuggestion).where(MatchSuggestion.query_image_id.in_([r.id for r in query_images])))
            eligible=(Item.kind!=item.kind,Item.owner_id!=item.owner_id,Item.state.in_(ACTIVE),Item.hidden.is_(False),Item.deleted_at.is_(None),Item.expires_at>now())
            candidate_ids=list(db.scalars(select(Item.id).where(*eligible).order_by(Item.created_at,Item.id)))
            found=False
            for start in range(0,len(candidate_ids),100):
                if time.perf_counter()-started>300:raise TimeoutError('Bounded job time exceeded')
                candidates=list(db.scalars(select(Item).where(Item.id.in_(candidate_ids[start:start+100]),*eligible).order_by(Item.created_at,Item.id).with_for_update().execution_options(populate_existing=True)))
                grouped={c.id:[] for c in candidates}
                for photo in db.scalars(select(ItemImage).where(ItemImage.item_id.in_(grouped)).order_by(ItemImage.position)):grouped[photo.item_id].append(photo)
                pairs=[];notifications=[]
                for candidate in candidates:
                    relevant_pair=False;reverse_found=False
                    for photo in grouped[candidate.id]:
                        cdesc,cappearance=cache.get(photo)
                        for query,qdesc,qappearance in queries:
                            scores=appearance_from_descriptors(qappearance,cappearance)
                            row=score_descriptions(qdesc,cdesc,scores);reverse=score_descriptions(cdesc,qdesc,scores)
                            pairs.extend([pair_values(query,photo,row,model.model_version),pair_values(photo,query,reverse,model.model_version)])
                            pairs_scored+=2
                            found|=row['relevance']=='relevant';reverse_found|=reverse['relevance']=='relevant'
                            relevant_pair|=row['relevance']=='relevant' or reverse['relevance']=='relevant'
                    if relevant_pair:
                        pair=':'.join(sorted([item.id,candidate.id]))
                        for owner,report in [(item.owner_id,item),(candidate.owner_id,candidate)]:
                            notifications.append(dict(id=uid(),user_id=owner,kind='potential_match',message='A visually similar opposite-type report is available. Ownership is unverified.',item_id=report.id,dedupe=f'match:{owner}:{pair}',created_at=now()))
                    if reverse_found and candidate.state=='OPEN':candidate.state='MATCH_SUGGESTED'
                db.flush();bulk_pairs(db,pairs)
                if notifications:
                    if db.bind.dialect.name=='postgresql':
                        from sqlalchemy.dialects.postgresql import insert
                    else:
                        from sqlalchemy.dialects.sqlite import insert
                    db.execute(insert(Notification).values(notifications).on_conflict_do_nothing(index_elements=['dedupe']))
            if found and item.state=='OPEN':item.state='MATCH_SUGGESTED'
            job.status='DONE';job.error=''
        LOG.info(json.dumps({'event':'matching_job','status':'done','seconds':round(time.perf_counter()-started,3),'directed_pairs':pairs_scored}))
        return True
    except Exception:
        LOG.warning(json.dumps({'event':'matching_job','status':'failed','seconds':round(time.perf_counter()-started,3)}))
        try:
            with factory.begin() as db:
                maintenance_guard(db)
                db.scalar(select(Item).where(Item.id==iid).with_for_update())
                job=db.scalar(select(MatchJob).where(MatchJob.item_id==iid).with_for_update())
                if job and attempt_version is not None and job.status=='PENDING' and job.updated_at==attempt_version:
                    job.status='FAILED';job.error='Matching is unavailable. The report is saved; retry after checking the local model and storage.'
        except Exception:LOG.warning('Could not record matching job failure')
        return False


@router.post('/items/{iid}/match')
def retry_match(iid:str,request:Request,tasks:BackgroundTasks,auth=Depends(current),db=Depends(get_db)):
    throttle(request,'matching',auth[0].id,6,600)
    item=find_item(db,iid,auth[0],owned=True,lock=True)
    if item.state not in ACTIVE or item.hidden:raise HTTPException(409,'This report is not active.')
    queue(db,item);db.commit();schedule(request,tasks,iid);return {'status':'PENDING'}


@router.get('/items/{iid}/matches')
def potential_matches(iid:str,offset:int=0,auth=Depends(current),db=Depends(get_db)):
    if not 0<=offset<=100000:raise HTTPException(400,'Invalid page.')
    item=find_item(db,iid,auth[0],owned=True);job=db.get(MatchJob,iid)
    groups=[];has_more=False
    for query in images(db,item):
        entries=[]
        if item.state in ACTIVE and not item.hidden:
            stmt=select(MatchSuggestion,ItemImage,Item).join(ItemImage,MatchSuggestion.candidate_image_id==ItemImage.id).join(Item,Item.id==ItemImage.item_id).where(
                MatchSuggestion.query_image_id==query.id,Item.state.in_(ACTIVE),Item.hidden.is_(False),Item.deleted_at.is_(None),Item.expires_at>now())
            stmt=stmt.order_by(case({'relevant':0,'uncertain':1,'excluded':2},value=MatchSuggestion.relevance),MatchSuggestion.similarity.desc(),func.coalesce(MatchSuggestion.appearance,0).desc(),Item.created_at,Item.id,ItemImage.position).offset(offset).limit(26)
            rows=db.execute(stmt).all();has_more|=len(rows)>25
            for match,image,candidate in rows[:25]:
                entries.append({'item_id':candidate.id,'image_id':image.id,'title':candidate.title,'kind':candidate.kind,'crop':image.crop,
                    'image_url':f'/api/v1/images/{image.id}','relevance':match.relevance,'reason':match.reason})
        groups.append({'query_image_id':query.id,'query_url':f'/api/v1/images/{query.id}','query_crop':query.crop,'candidates':entries})
    return {'status':job.status if job else 'PENDING','message':job.error if job else '', 'groups':groups,'next_offset':offset+25 if has_more else None,'previous_offset':max(0,offset-25) if offset else None,
            'notice':'Each photograph is ranked separately with the existing CLIP policy. No identity is verified; an empty list does not prove absence.'}
