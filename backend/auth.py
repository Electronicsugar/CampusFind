"""Opaque revocable sessions, Argon2id passwords and shared throttling."""
import hashlib
import re
import secrets
import time
from threading import BoundedSemaphore
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHashError
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel,Field,ConfigDict,field_validator
from sqlalchemy import select,delete
from sqlalchemy.exc import IntegrityError
from backend.database import get_db
from backend.models import User,Session,RecoveryCode,RateLimit,ModerationRecord,now

router=APIRouter(prefix='/api/v1/auth',tags=['accounts'])
hasher=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
DUMMY_HASH=hasher.hash(secrets.token_urlsafe(32))
COOKIE='campusfind_session'
PASSWORD_WORK=BoundedSemaphore(2)


def hash_password(password):
    if not PASSWORD_WORK.acquire(timeout=3):raise HTTPException(429,'Authentication is busy. Try again shortly.')
    try:return hasher.hash(password)
    finally:PASSWORD_WORK.release()


def verify_password(encoded,password):
    if not PASSWORD_WORK.acquire(timeout=3):raise HTTPException(429,'Authentication is busy. Try again shortly.')
    try:
        try:return hasher.verify(encoded,password)
        except (VerificationError,InvalidHashError):return False
    finally:PASSWORD_WORK.release()


def digest(value):return hashlib.sha256(value.encode()).hexdigest()


def origin_check(request):
    if request.headers.get('origin')!=request.app.state.settings.origin:
        raise HTTPException(403,'Request origin is not allowed.')


def throttle(request,scope,identity,limit,seconds):
    """Atomic shared counters; failed requests count too. Keys contain no raw email/IP."""
    factory=request.app.state.sessions
    if factory is None:raise HTTPException(503,'Database is not configured.')
    bucket=int(time.time())//seconds
    key=digest(f'{scope}:{identity}:{bucket}')
    with factory.begin() as db:
        if db.bind.dialect.name=='postgresql':
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        statement=insert(RateLimit).values(key=key,count=1,expires_at=now()+timedelta(seconds=seconds))
        count=db.execute(statement.on_conflict_do_update(index_elements=['key'],set_={'count':RateLimit.count+1}).returning(RateLimit.count)).scalar_one()
    if count>limit:raise HTTPException(429,'Too many attempts. Please try again later.',headers={'Retry-After':str(seconds)})


def current(request:Request,db=Depends(get_db)):
    token=request.cookies.get(COOKIE,'')
    session=db.get(Session,digest(token)) if token else None
    user=db.get(User,session.user_id) if session and session.expires_at>now() else None
    if not user or not user.active:raise HTTPException(401,'Please log in.')
    if request.method not in {'GET','HEAD','OPTIONS'}:
        origin_check(request)
        if not secrets.compare_digest(request.headers.get('x-csrf-token',''),session.csrf):
            raise HTTPException(403,'Session verification failed. Refresh and try again.')
    return user,session


def admin(auth=Depends(current)):
    if auth[0].role!='admin':raise HTTPException(403,'Administrator access required.')
    return auth[0]


def user_view(user):return {'id':user.id,'display_name':user.display_name,'email':user.email,'role':user.role}


class Credentials(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=6,max_length=128)
    @field_validator('email')
    @classmethod
    def email_format(cls,value):
        value=value.strip().lower()
        if not re.fullmatch(r'[a-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}',value):
            raise ValueError('Enter a valid email address.')
        return value


class NewPassword(Credentials):
    password:str=Field(min_length=6,max_length=12)

    @field_validator('password')
    @classmethod
    def password_mix(cls,value):
        if not re.search(r'[A-Za-z]',value) or not re.search(r'[0-9]',value):
            raise ValueError('Use 6–12 characters with at least one letter and one number.')
        return value


class Registration(NewPassword):
    display_name:str=Field(min_length=2,max_length=80)
    @field_validator('display_name')
    @classmethod
    def name(cls,value):
        if len(value.strip())<2:raise ValueError('Enter your display name.')
        return value.strip()


def new_session(request,response,db,user):
    old=request.cookies.get(COOKIE)
    if old:db.execute(delete(Session).where(Session.token_hash==digest(old)))
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
    settings=request.app.state.settings
    db.add(Session(token_hash=digest(token),user_id=user.id,csrf=csrf,expires_at=now()+timedelta(hours=settings.session_hours)))
    db.commit()
    response.set_cookie(COOKIE,token,max_age=settings.session_hours*3600,httponly=True,secure=settings.secure_cookie,samesite='lax',path='/')
    return {'user':user_view(user),'csrf':csrf}


@router.post('/register',status_code=201)
def register(data:Registration,request:Request,response:Response,db=Depends(get_db)):
    origin_check(request);throttle(request,'register',request.client.host,10,3600)
    settings=request.app.state.settings
    if not settings.registration_open:
        raise HTTPException(403,'Pilot accounts are issued by the campus coordinator.')
    domains=request.app.state.settings.domains
    if domains and data.email.rsplit('@',1)[1] not in domains:raise HTTPException(400,'Use an allowed campus email domain.')
    user=User(email=data.email,display_name=data.display_name,password_hash=hash_password(data.password))
    db.add(user)
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Registration could not be completed. Try logging in with this email.') from None
    db.add(ModerationRecord(actor_id=user.id,action='account_registered'))
    codes=replace_recovery_codes(db,user)
    return {**new_session(request,response,db,user),'recovery_codes':codes}


@router.post('/login')
def login(data:Credentials,request:Request,response:Response,db=Depends(get_db)):
    origin_check(request);throttle(request,'login_ip',request.client.host,30,600)
    throttle(request,'login_account',data.email,10,600)
    # Serialize password verification/session creation with password recovery.
    user=db.scalar(select(User).where(User.email==data.email).with_for_update())
    valid=verify_password(user.password_hash if user else DUMMY_HASH,data.password)
    if not valid or not user or not user.active:raise HTTPException(401,'Email or password is incorrect.')
    if hasher.check_needs_rehash(user.password_hash):user.password_hash=hash_password(data.password)
    return new_session(request,response,db,user)


def replace_recovery_codes(db,user):
    """Call with the user row locked (or newly inserted), and commit atomically."""
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id==user.id))
    codes=[]
    for _ in range(8):
        raw=secrets.token_hex(16).upper()
        codes.append('-'.join(raw[i:i+8] for i in range(0,32,8)))
        db.add(RecoveryCode(user_id=user.id,code_hash=digest('recovery:'+raw)))
    return codes


class PasswordReset(NewPassword):
    recovery_code:str=Field(min_length=1,max_length=128)


class PasswordProof(BaseModel):
    model_config=ConfigDict(extra='forbid')
    password:str=Field(min_length=6,max_length=128)


@router.post('/reset-password')
def reset_password(data:PasswordReset,request:Request,db=Depends(get_db)):
    origin_check(request)
    throttle(request,'recovery_ip',request.client.host,20,3600)
    throttle(request,'recovery_account',data.email,6,3600)
    raw=re.sub(r'[-\s]','',data.recovery_code).upper()
    user=db.scalar(select(User).where(User.email==data.email).with_for_update())
    code=db.get(RecoveryCode,digest('recovery:'+raw)) if re.fullmatch(r'[0-9A-F]{32}',raw) else None
    if not user or not user.active or not code or code.user_id!=user.id:
        raise HTTPException(400,'Email or recovery code is incorrect, or the code is no longer valid.')
    user.password_hash=hash_password(data.password)
    db.execute(delete(Session).where(Session.user_id==user.id))
    codes=replace_recovery_codes(db,user)
    db.add(ModerationRecord(actor_id=user.id,action='password_recovered'))
    db.commit()
    return {'ok':True,'recovery_codes':codes}


@router.post('/recovery-codes')
def recovery_codes(data:PasswordProof,request:Request,auth=Depends(current),db=Depends(get_db)):
    throttle(request,'recovery_codes',auth[0].id,6,3600)
    user=db.scalar(select(User).where(User.id==auth[0].id).with_for_update().execution_options(populate_existing=True))
    # Re-check after acquiring the lock: recovery may have revoked this session.
    valid_session=db.scalar(select(Session.token_hash).where(Session.token_hash==auth[1].token_hash,Session.expires_at>now()))
    if not user.active or not valid_session:raise HTTPException(401,'Please log in.')
    if not verify_password(user.password_hash,data.password):raise HTTPException(400,'Password is incorrect.')
    codes=replace_recovery_codes(db,user)
    db.add(ModerationRecord(actor_id=user.id,action='recovery_codes_replaced'))
    db.commit()
    return {'recovery_codes':codes}


@router.get('/me')
def me(auth=Depends(current)):return {'user':user_view(auth[0]),'csrf':auth[1].csrf}


@router.post('/logout')
def logout(response:Response,auth=Depends(current),db=Depends(get_db)):
    db.delete(auth[1]);db.commit();response.delete_cookie(COOKIE,path='/')
    return {'ok':True}


class Profile(BaseModel):
    model_config=ConfigDict(extra='forbid')
    display_name:str=Field(min_length=2,max_length=80)


@router.patch('/profile')
def profile(data:Profile,auth=Depends(current)):
    if len(data.display_name.strip())<2:raise HTTPException(400,'Enter a display name.')
    auth[0].display_name=data.display_name.strip()
    return {'user':user_view(auth[0])}
