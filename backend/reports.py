import json
from datetime import date,timedelta
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request,UploadFile,File,Form,BackgroundTasks
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,Field,ConfigDict,field_validator,ValidationError
from sqlalchemy import select,delete,func,or_
from backend.auth import current,throttle
from backend.database import get_db
from backend.models import Item,ItemImage,User,MatchJob,MatchSuggestion,ClaimRequest,ModerationRecord,now
from backend import storage
from backend.settings import campus_today

router=APIRouter(prefix='/api/v1',tags=['reports'])
ACTIVE=('OPEN','MATCH_SUGGESTED','CLAIM_PENDING')


class ReportData(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['LOST','FOUND']
    title:str=Field(min_length=3,max_length=120)
    category:str=Field(min_length=2,max_length=60)
    description:str=Field(min_length=10,max_length=3000)
    location:str=Field(min_length=2,max_length=160)
    event_date:date
    consent:Literal[True]
    @field_validator('title','category','description','location')
    @classmethod
    def trim(cls,value):
        if not value.strip():raise ValueError('This field cannot be blank.')
        return value.strip()
    @field_validator('event_date')
    @classmethod
    def valid_date(cls,value):
        if value>campus_today():raise ValueError('Date cannot be in the future.')
        return value


def visible(item,user):
    return not item.deleted_at and item.expires_at>now() and (user.role=='admin' or item.owner_id==user.id or (not item.hidden and item.state in ACTIVE))


def find_item(db,iid,user,owned=False,lock=False):
    stmt=select(Item).where(Item.id==iid)
    if lock:stmt=stmt.with_for_update()
    item=db.scalar(stmt)
    if not item or not visible(item,user):raise HTTPException(404,'Report not found.')
    if owned and item.owner_id!=user.id and user.role!='admin':raise HTTPException(403,'Only the report owner can change this report.')
    return item


def images(db,item):return list(db.scalars(select(ItemImage).where(ItemImage.item_id==item.id).order_by(ItemImage.position)))


def item_view(db,item,user,photo_rows=None):
    return {'id':item.id,'kind':item.kind,'title':item.title,'category':item.category,'description':item.description,
            'location':item.location,'event_date':item.event_date.isoformat(),'state':item.state,'hidden':item.hidden,
            'is_owner':item.owner_id==user.id,'created_at':item.created_at.isoformat(),'expires_at':item.expires_at.isoformat(),
            'images':[{'id':i.id,'url':f'/api/v1/images/{i.id}','crop':i.crop} for i in (images(db,item) if photo_rows is None else photo_rows)]}


def item_views(db,items,user):
    grouped={item.id:[] for item in items}
    if grouped:
        for photo in db.scalars(select(ItemImage).where(ItemImage.item_id.in_(grouped)).order_by(ItemImage.position)):
            grouped[photo.item_id].append(photo)
    return [item_view(db,item,user,grouped[item.id]) for item in items]


def queue(db,item):
    job=db.get(MatchJob,item.id)
    if not job:db.add(MatchJob(item_id=item.id,status='PENDING'))
    else:job.status='PENDING';job.error='';job.updated_at=now()


def schedule(request,tasks,iid):
    if request.app.state.settings.background_matching:
        from backend.matching import process_job
        tasks.add_task(process_job,request.app.state.sessions,request.app.state.settings,iid)


def clear_matches(db,image_ids):
    db.execute(delete(MatchSuggestion).where(or_(MatchSuggestion.query_image_id.in_(image_ids),MatchSuggestion.candidate_image_id.in_(image_ids))))


@router.post('/items',status_code=201)
def create_report(request:Request,tasks:BackgroundTasks,metadata:str=Form(...),selections:str=Form(...),
                  photos:list[UploadFile]=File(...),auth=Depends(current),db=Depends(get_db)):
    user=auth[0];throttle(request,'reports',user.id,12,3600)
    try:
        data=ReportData.model_validate_json(metadata);choices=json.loads(selections)
    except (ValidationError,ValueError,TypeError):raise HTTPException(400,'Check report fields, date and photo selections.') from None
    if not 1<=len(photos)<=4 or not isinstance(choices,list) or len(choices)!=len(photos):
        raise HTTPException(400,'Choose 1–4 photographs and explicitly select each object or full image.')
    if any(not isinstance(c,dict) or set(c)!={'confirmed','box'} or c['confirmed'] is not True for c in choices):
        raise HTTPException(400,'Every photograph needs an accepted crop or full-image selection.')
    # Serialize quota checks per account.
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    count=db.scalar(select(func.count()).select_from(Item).where(Item.owner_id==user.id,Item.deleted_at.is_(None)))
    if count>=100:raise HTTPException(409,'Report limit reached. Delete old reports before adding more.')
    item=Item(owner_id=user.id,**data.model_dump(exclude={'consent'}),expires_at=now()+timedelta(days=request.app.state.settings.retention_days))
    db.add(item);db.flush();saved=[];total=0
    try:
        for position,(upload,choice) in enumerate(zip(photos,choices)):
            key,content_hash,size=storage.save_upload(request.app.state.settings,upload,choice['box']);saved.append(key);total+=size
            if total>45*1024*1024:raise ValueError('Combined upload limit is 45 MB.')
            db.add(ItemImage(item_id=item.id,storage_key=key,content_hash=content_hash,crop=choice['box'],position=position))
        queue(db,item);db.add(ModerationRecord(actor_id=user.id,action='report_created',item_id=item.id))
        db.commit()
    except Exception as exc:
        db.rollback()
        for key in saved:storage.remove(request.app.state.settings,key)
        if isinstance(exc,(ValueError,TypeError)):raise HTTPException(400,str(exc)) from None
        raise
    result=item_view(db,item,user);schedule(request,tasks,item.id)
    return result


@router.get('/items')
def browse(kind:Literal['LOST','FOUND']|None=None,category:str='',q:str='',mine:bool=False,offset:int=0,auth=Depends(current),db=Depends(get_db)):
    if offset<0 or offset>100000 or len(q)>120 or len(category)>60:raise HTTPException(400,'Invalid search filters.')
    user=auth[0];stmt=select(Item).where(Item.deleted_at.is_(None),Item.expires_at>now())
    if mine:stmt=stmt.where(Item.owner_id==user.id)
    else:stmt=stmt.where(Item.hidden.is_(False),Item.state.in_(ACTIVE))
    if kind:stmt=stmt.where(Item.kind==kind)
    if category:stmt=stmt.where(Item.category==category)
    if q:stmt=stmt.where(or_(Item.title.icontains(q,autoescape=True),Item.description.icontains(q,autoescape=True),Item.location.icontains(q,autoescape=True)))
    rows=list(db.scalars(stmt.order_by(Item.created_at.desc(),Item.id).offset(offset).limit(25)))
    return {'items':item_views(db,rows,user),'next_offset':offset+25 if len(rows)==25 else None}


@router.get('/items/{iid}')
def detail(iid:str,auth=Depends(current),db=Depends(get_db)):
    item=find_item(db,iid,auth[0]);return item_view(db,item,auth[0])


class EditReport(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=3,max_length=120)
    category:str=Field(min_length=2,max_length=60)
    description:str=Field(min_length=10,max_length=3000)
    location:str=Field(min_length=2,max_length=160)
    event_date:date


@router.patch('/items/{iid}')
def edit(iid:str,data:EditReport,auth=Depends(current),db=Depends(get_db)):
    item=find_item(db,iid,auth[0],owned=True,lock=True)
    if item.state not in {'OPEN','MATCH_SUGGESTED'}:raise HTTPException(409,'This report cannot be edited in its current state.')
    try:validated=ReportData(**data.model_dump(),kind=item.kind,consent=True)
    except ValidationError:raise HTTPException(400,'Check report fields and date.') from None
    for key,value in validated.model_dump(exclude={'kind','consent'}).items():setattr(item,key,value)
    db.add(ModerationRecord(actor_id=auth[0].id,action='report_edited',item_id=iid))
    return item_view(db,item,auth[0])


class StateChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    state:Literal['OPEN','CLOSED']


@router.post('/items/{iid}/state')
def change_state(iid:str,data:StateChange,request:Request,tasks:BackgroundTasks,auth=Depends(current),db=Depends(get_db)):
    item=find_item(db,iid,auth[0],owned=True,lock=True)
    allowed={'OPEN':{'CLOSED'},'MATCH_SUGGESTED':{'CLOSED'},'CLOSED':{'OPEN'}}
    if data.state not in allowed.get(item.state,set()):raise HTTPException(409,'Invalid report state transition. Resolve active claims first.')
    item.state=data.state
    if data.state=='OPEN':queue(db,item)
    db.add(ModerationRecord(actor_id=auth[0].id,action='report_'+data.state.lower(),item_id=iid));db.commit()
    if data.state=='OPEN':schedule(request,tasks,iid)
    return item_view(db,item,auth[0])


@router.delete('/items/{iid}')
def delete_report(iid:str,request:Request,auth=Depends(current),db=Depends(get_db)):
    item=find_item(db,iid,auth[0],owned=True,lock=True)
    if item.state=='CLAIM_PENDING':raise HTTPException(409,'Resolve active claims before deleting this report.')
    stored=images(db,item);clear_matches(db,[i.id for i in stored])
    item.deleted_at=now();item.state='CLOSED';item.description='Deleted by owner';item.location='Removed';item.title='Deleted report'
    for claim in db.scalars(select(ClaimRequest).where(ClaimRequest.item_id==iid)):
        claim.evidence='Removed';claim.review_note=''
    for image in stored:storage.queue_deletion(db,image.storage_key);db.delete(image)
    db.add(ModerationRecord(actor_id=auth[0].id,action='report_deleted',item_id=iid));db.commit()
    storage.drain_deletions(request.app.state.sessions,request.app.state.settings)
    return {'ok':True}


@router.get('/images/{image_id}')
def image_file(image_id:str,request:Request,auth=Depends(current),db=Depends(get_db)):
    image=db.get(ItemImage,image_id)
    if not image:raise HTTPException(404,'Image not found.')
    find_item(db,image.item_id,auth[0]);path=storage.location(request.app.state.settings,image.storage_key)
    if not path.exists():raise HTTPException(404,'Image not found.')
    return FileResponse(path,media_type='image/jpeg',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'},filename='item.jpg',content_disposition_type='inline')


class CropChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed:Literal[True]
    box:list[float]|None


@router.patch('/images/{image_id}/crop')
def edit_crop(image_id:str,data:CropChange,request:Request,tasks:BackgroundTasks,auth=Depends(current),db=Depends(get_db)):
    image=db.get(ItemImage,image_id)
    if not image:raise HTTPException(404,'Image not found.')
    item=find_item(db,image.item_id,auth[0],owned=True,lock=True)
    image=db.scalar(select(ItemImage).where(ItemImage.id==image_id).execution_options(populate_existing=True))
    if not image:raise HTTPException(404,'Image not found.')
    if item.state not in {'OPEN','MATCH_SUGGESTED'}:raise HTTPException(409,'Crops cannot change during a claim or after closure.')
    from backend.vision import prepare
    try:prepare(storage.read(request.app.state.settings,image.storage_key),data.box,normalize=False)
    except (ValueError,TypeError):raise HTTPException(400,'Invalid crop.') from None
    image.crop=data.box;image.embedding_key=None;image.descriptor=None;image.cache_signature=None;image.appearance=None
    clear_matches(db,[image.id]);queue(db,item);db.add(ModerationRecord(actor_id=auth[0].id,action='crop_changed',item_id=item.id));db.commit()
    schedule(request,tasks,item.id);return {'ok':True}
