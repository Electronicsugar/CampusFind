"""Private, pre-publication image retrieval over active found reports."""
import json
import logging
import time
from threading import BoundedSemaphore
import cv2
import numpy as np
from fastapi import APIRouter,Depends,File,Form,HTTPException,Request,UploadFile
from sqlalchemy import select,or_,text
from backend.auth import current,throttle
from backend.database import get_db
from backend.models import Item,ItemImage,now
from backend.reports import ACTIVE
from backend.matching import PreparedCache
from backend.semantic import get_model,relevance,ModelUnavailable
from backend.vision import decode_image,prepare,MAX_BYTES

router=APIRouter(prefix='/api/v1/found',tags=['image search'])
SEARCH_WORK=BoundedSemaphore(1)
MAX_GALLERY_PHOTOS=2000
MAX_SEARCH_SECONDS=45
LOG=logging.getLogger(__name__)


@router.post('/search-image')
def search_found(request:Request,photo:UploadFile=File(...),selection:str=Form(...),
                 category:str=Form(''),q:str=Form(''),offset:int=Form(0),
                 auth=Depends(current),db=Depends(get_db)):
    throttle(request,'image_search',auth[0].id,20,600)
    started=time.perf_counter()
    if len(category)>60 or len(q)>120 or not 0<=offset<=100000:raise HTTPException(400,'Invalid search filters or page.')
    try:
        choice=json.loads(selection)
        if not isinstance(choice,dict) or set(choice)!={'confirmed','box'} or choice['confirmed'] is not True:
            raise ValueError('Select the object or explicitly use the full image before searching.')
        box=choice['box']
        if box is not None and (not isinstance(box,list) or any(isinstance(v,bool) for v in box)):
            raise ValueError('Use four normalized numeric crop coordinates.')
        image=decode_image(photo.file.read(MAX_BYTES+1))
        # Same maximum size and crop transform as stored candidate photographs.
        h,w=image.shape[:2];scale=min(1,2000/max(h,w))
        if scale<1:image=cv2.resize(image,(round(w*scale),round(h*scale)),interpolation=cv2.INTER_AREA)
        region=prepare(image,box,normalize=False)[0]
    except (ValueError,TypeError,cv2.error):
        raise HTTPException(400,'Choose a valid JPEG, PNG or WebP (15 MB / 24 MP maximum) and confirm a valid object crop or full image.') from None
    if not SEARCH_WORK.acquire(blocking=False):raise HTTPException(429,'Image search is busy. Try again shortly.',headers={'Retry-After':'5'})
    try:
        if db.bind.dialect.name=='postgresql' and not db.scalar(text('SELECT pg_try_advisory_xact_lock(72439106)')):
            raise HTTPException(429,'The matching worker is busy. Try image search again shortly.',headers={'Retry-After':'5'})
        eligible=[Item.kind=='FOUND',Item.state.in_(ACTIVE),Item.hidden.is_(False),Item.deleted_at.is_(None),Item.expires_at>now()]
        if category:eligible.append(Item.category==category)
        if q:eligible.append(or_(Item.title.icontains(q,autoescape=True),Item.description.icontains(q,autoescape=True),Item.location.icontains(q,autoescape=True)))
        candidates=db.execute(select(ItemImage,Item).join(Item,Item.id==ItemImage.item_id).where(*eligible)
            .order_by(Item.id,ItemImage.position).limit(MAX_GALLERY_PHOTOS+1)).all()
        if len(candidates)>MAX_GALLERY_PHOTOS:
            raise HTTPException(422,'Too many photos for one CPU search. Narrow the category or location/description filter and retry.')
        results={};model_version=None
        if candidates:
            model=get_model();model_version=model.model_version
            reference=model.describe(region);cache=PreparedCache(model,request.app.state.settings)
            for photo_row,item in candidates:
                if time.perf_counter()-started>MAX_SEARCH_SECONDS:
                    raise HTTPException(503,'Image search exceeded its time limit. Narrow the filters and retry; nothing was published.')
                description,_=cache.get(photo_row)
                score=float(np.clip(reference['vector']@description['vector'],-1,1))
                if item.id not in results or score>results[item.id]['visual_similarity']:
                    results[item.id]={'item_id':item.id,'image_id':photo_row.id,'title':item.title,'category':item.category,
                        'location':item.location,'event_date':item.event_date.isoformat(),'image_url':f'/api/v1/images/{photo_row.id}',
                        'crop':photo_row.crop,'visual_similarity':score,'category_note':relevance(reference,description)['relevance_reason']}
        # Category predictions are advisory; never remove or demote visual hits.
        ranked=sorted(results.values(),key=lambda row:(-row['visual_similarity'],row['item_id']))
        for rank,row in enumerate(ranked,1):row['rank']=rank;row.pop('visual_similarity')
        db.flush()
        elapsed=round((time.perf_counter()-started)*1000,1)
        LOG.info(json.dumps({'event':'found_image_search','photos':len(candidates),'reports':len(ranked),'elapsed_ms':elapsed}))
        return {'results':ranked[offset:offset+25],'total_reports':len(ranked),'searched_photos':len(candidates),
            'next_offset':offset+25 if len(ranked)>offset+25 else None,'elapsed_ms':elapsed,'model_version':model_version,
            'notice':'Ranked visual suggestions, not verified identity. All filtered active found reports were searched. A low-ranked or absent result does not prove your item is absent. Your search photo was not published or saved.'}
    except ModelUnavailable:
        raise HTTPException(503,'Image matching is unavailable. Try later or browse by location and description; nothing was published.') from None
    finally:SEARCH_WORK.release()
