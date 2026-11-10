from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,or_
from backend.auth import current,throttle
from backend.database import get_db
from backend.models import ClaimRequest,Item,Notification,ModerationRecord,now,uid
from backend.reports import find_item

router=APIRouter(prefix='/api/v1',tags=['claims and notifications'])


def notify(db,user_id,kind,message,item_id=None,claim_id=None,dedupe=None):
    if db.bind.dialect.name=='postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(Notification).values(id=uid(),user_id=user_id,kind=kind,message=message,item_id=item_id,claim_id=claim_id,
               dedupe=dedupe or uid(),created_at=now()).on_conflict_do_nothing(index_elements=['dedupe']))


def claim_view(claim,item,user):
    expired=bool(item.deleted_at or item.expires_at<=now())
    return {'id':claim.id,'item_id':claim.item_id,'item_title':'Unavailable report' if expired else item.title,'status':claim.status,'evidence':'Removed after expiry or deletion.' if expired else claim.evidence,
            'review_note':'' if expired else claim.review_note,'is_claimant':claim.claimant_id==user.id,'unavailable':expired,
            'can_review':not expired and (item.owner_id==user.id or user.role=='admin'),'created_at':claim.created_at.isoformat()}


class Evidence(BaseModel):
    model_config=ConfigDict(extra='forbid')
    evidence:str=Field(min_length=20,max_length=3000)


@router.post('/items/{iid}/claims',status_code=201)
def make_claim(iid:str,data:Evidence,request:Request,auth=Depends(current),db=Depends(get_db)):
    user=auth[0];throttle(request,'claims',user.id,20,3600)
    item=find_item(db,iid,user,lock=True)
    if item.owner_id==user.id:raise HTTPException(400,'You cannot claim your own found report.')
    if item.kind!='FOUND' or item.hidden or item.state not in {'OPEN','MATCH_SUGGESTED','CLAIM_PENDING'}:
        raise HTTPException(409,'This report is not accepting claims.')
    if len(data.evidence.strip())<20:raise HTTPException(400,'Describe non-public ownership details.')
    if db.scalar(select(ClaimRequest.id).where(ClaimRequest.item_id==iid,ClaimRequest.status.in_(['APPROVED','RETURNED']))):
        raise HTTPException(409,'A handover is already arranged.')
    if db.scalar(select(ClaimRequest.id).where(ClaimRequest.item_id==iid,ClaimRequest.claimant_id==user.id,ClaimRequest.status.in_(['PENDING','APPROVED']))):
        raise HTTPException(409,'You already have an active claim for this item.')
    claim=ClaimRequest(item_id=iid,claimant_id=user.id,evidence=data.evidence.strip());db.add(claim);db.flush()
    item.state='CLAIM_PENDING';db.add(ModerationRecord(actor_id=user.id,action='claim_requested',item_id=iid,claim_id=claim.id))
    notify(db,item.owner_id,'claim_requested','A student submitted private ownership details for your found report.',iid,claim.id)
    return claim_view(claim,item,user)


@router.get('/claims')
def list_claims(offset:int=0,auth=Depends(current),db=Depends(get_db)):
    if not 0<=offset<=100000:raise HTTPException(400,'Invalid page.')
    user=auth[0];stmt=select(ClaimRequest,Item).join(Item,Item.id==ClaimRequest.item_id)
    if user.role!='admin':stmt=stmt.where(or_(ClaimRequest.claimant_id==user.id,Item.owner_id==user.id))
    rows=db.execute(stmt.order_by(ClaimRequest.created_at.desc(),ClaimRequest.id).offset(offset).limit(25)).all()
    return {'claims':[claim_view(c,i,user) for c,i in rows],'next_offset':offset+25 if len(rows)==25 else None}


class ClaimAction(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['approve','reject','withdraw','returned']
    note:str=Field(default='',max_length=1000)


@router.post('/claims/{cid}/action')
def act(cid:str,data:ClaimAction,auth=Depends(current),db=Depends(get_db)):
    user=auth[0];claim=db.get(ClaimRequest,cid)
    if not claim:raise HTTPException(404,'Claim not found.')
    item=db.scalar(select(Item).where(Item.id==claim.item_id).with_for_update())
    claim=db.scalar(select(ClaimRequest).where(ClaimRequest.id==cid).with_for_update().execution_options(populate_existing=True))
    reviewer=item.owner_id==user.id or user.role=='admin'
    if not reviewer and claim.claimant_id!=user.id:raise HTTPException(404,'Claim not found.')
    if item.deleted_at or item.expires_at<=now() or (item.hidden and user.role!='admin'):
        raise HTTPException(409,'This report is unavailable for claim changes.')
    if data.action in {'approve','reject'}:
        if not reviewer:raise HTTPException(403,'Only the finder or an administrator can review claims.')
        if claim.claimant_id==user.id:raise HTTPException(403,'You cannot approve or reject your own claim.')
        if claim.status!='PENDING' or item.state!='CLAIM_PENDING':raise HTTPException(409,'Only pending claims can be reviewed.')
        if len(data.note.strip())<10:raise HTTPException(400,'Record a review explanation of at least 10 characters.')
        claim.status='APPROVED' if data.action=='approve' else 'REJECTED';claim.review_note=data.note.strip()
        if data.action=='approve':
            other_approved=db.scalar(select(ClaimRequest.id).where(ClaimRequest.item_id==item.id,ClaimRequest.status.in_(['APPROVED','RETURNED']),ClaimRequest.id!=cid))
            if other_approved:raise HTTPException(409,'Another claim has already been approved.')
            for other in db.scalars(select(ClaimRequest).where(ClaimRequest.item_id==item.id,ClaimRequest.id!=cid,ClaimRequest.status=='PENDING')):
                other.status='REJECTED';other.review_note='A different claim was approved after review.'
                db.add(ModerationRecord(actor_id=user.id,action='claim_rejected_conflict',item_id=item.id,claim_id=other.id))
                notify(db,other.claimant_id,'claim_rejected','Your claim was not selected after review.',item.id,other.id)
        notify(db,claim.claimant_id,'claim_'+data.action,'Your claim was '+('approved for handover.' if data.action=='approve' else 'rejected after review.'),item.id,cid)
    elif data.action=='withdraw':
        if claim.claimant_id!=user.id:raise HTTPException(403,'Only the claimant can withdraw a claim.')
        if claim.status not in {'PENDING','APPROVED'}:raise HTTPException(409,'This claim cannot be withdrawn.')
        claim.status='WITHDRAWN';notify(db,item.owner_id,'claim_withdrawn','A student withdrew their claim.',item.id,cid)
    else:
        if claim.status!='APPROVED':raise HTTPException(409,'Only an approved claim can be marked returned.')
        if claim.claimant_id!=user.id and user.role!='admin':raise HTTPException(403,'The claimant must confirm receipt, or an administrator must record handover.')
        if user.role=='admin' and claim.claimant_id!=user.id and len(data.note.strip())<10:
            raise HTTPException(400,'Record the verified handover details.')
        if user.role=='admin' and claim.claimant_id!=user.id:claim.review_note=data.note.strip()
        claim.status='RETURNED';item.state='RETURNED'
        for recipient in {item.owner_id,claim.claimant_id}:notify(db,recipient,'item_returned','The item handover has been confirmed.',item.id,cid)
    db.flush()
    if item.state!='RETURNED':
        pending=db.scalar(select(ClaimRequest.id).where(ClaimRequest.item_id==item.id,ClaimRequest.status.in_(['PENDING','APPROVED'])).limit(1))
        item.state='CLAIM_PENDING' if pending else 'OPEN'
    db.add(ModerationRecord(actor_id=user.id,action='claim_'+data.action,item_id=item.id,claim_id=cid))
    return claim_view(claim,item,user)


@router.get('/notifications')
def notifications(offset:int=0,auth=Depends(current),db=Depends(get_db)):
    if not 0<=offset<=100000:raise HTTPException(400,'Invalid page.')
    rows=list(db.scalars(select(Notification).where(Notification.user_id==auth[0].id).order_by(Notification.created_at.desc(),Notification.id).offset(offset).limit(30)))
    return {'notifications':[{'id':r.id,'kind':r.kind,'message':r.message,'item_id':r.item_id,'claim_id':r.claim_id,'read':bool(r.read_at),'created_at':r.created_at.isoformat()} for r in rows],
            'next_offset':offset+30 if len(rows)==30 else None}


@router.post('/notifications/{nid}/read')
def mark_read(nid:str,auth=Depends(current),db=Depends(get_db)):
    row=db.scalar(select(Notification).where(Notification.id==nid,Notification.user_id==auth[0].id))
    if not row:raise HTTPException(404,'Notification not found.')
    row.read_at=now();return {'ok':True}
