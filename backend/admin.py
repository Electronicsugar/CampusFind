from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select,delete
from backend.auth import admin
from backend.database import get_db
from backend.models import Item,ModerationRecord,User,Session,now
from backend.reports import item_view,item_views

router=APIRouter(prefix='/api/v1/admin',tags=['moderation'])


@router.get('/items')
def admin_items(offset:int=0,user=Depends(admin),db=Depends(get_db)):
    if not 0<=offset<=100000:raise HTTPException(400,'Invalid page.')
    rows=list(db.scalars(select(Item).where(Item.deleted_at.is_(None),Item.expires_at>now()).order_by(Item.created_at.desc(),Item.id).offset(offset).limit(25)))
    return {'items':item_views(db,rows,user),'next_offset':offset+25 if len(rows)==25 else None}


class ModerationAction(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['hide','restore']
    reason:str=Field(min_length=10,max_length=300)


@router.post('/items/{iid}/moderate')
def moderate(iid:str,data:ModerationAction,user=Depends(admin),db=Depends(get_db)):
    if len(data.reason.strip())<10:raise HTTPException(400,'Record a meaningful moderation reason.')
    item=db.scalar(select(Item).where(Item.id==iid,Item.deleted_at.is_(None),Item.expires_at>now()).with_for_update())
    if not item:raise HTTPException(404,'Report not found.')
    item.hidden=data.action=='hide'
    db.add(ModerationRecord(actor_id=user.id,action='moderation_'+data.action,item_id=iid,detail=data.reason))
    return {'ok':True}


@router.get('/audit')
def audit(offset:int=0,user=Depends(admin),db=Depends(get_db)):
    if not 0<=offset<=100000:raise HTTPException(400,'Invalid page.')
    rows=list(db.scalars(select(ModerationRecord).order_by(ModerationRecord.created_at.desc(),ModerationRecord.id).offset(offset).limit(50)))
    return {'records':[{'action':r.action,'item_id':r.item_id,'claim_id':r.claim_id,'actor_id':r.actor_id,'detail':r.detail,'created_at':r.created_at.isoformat()} for r in rows],
            'next_offset':offset+50 if len(rows)==50 else None}
