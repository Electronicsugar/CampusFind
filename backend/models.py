"""Persistent application records. Ground-truth evaluation remains separate."""
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import String,Text,DateTime,Date,Boolean,Integer,Float,ForeignKey,JSON,CheckConstraint,UniqueConstraint,Index
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column


def now():return datetime.now(timezone.utc).replace(tzinfo=None)
def uid():return str(uuid4())
class Base(DeclarativeBase):pass


class User(Base):
    __tablename__='users'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    email:Mapped[str]=mapped_column(String(254),unique=True)
    display_name:Mapped[str]=mapped_column(String(80))
    password_hash:Mapped[str]=mapped_column(String(512))
    role:Mapped[str]=mapped_column(String(16),default='student')
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)
    __table_args__=(CheckConstraint("role IN ('student','admin')",name='valid_user_role'),)


class Session(Base):
    __tablename__='sessions'
    token_hash:Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    csrf:Mapped[str]=mapped_column(String(64))
    expires_at:Mapped[datetime]=mapped_column(DateTime,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)


class Item(Base):
    __tablename__='items'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    kind:Mapped[str]=mapped_column(String(8))
    title:Mapped[str]=mapped_column(String(120))
    category:Mapped[str]=mapped_column(String(60))
    description:Mapped[str]=mapped_column(Text)
    location:Mapped[str]=mapped_column(String(160))
    event_date:Mapped[datetime]=mapped_column(Date)
    state:Mapped[str]=mapped_column(String(24),default='OPEN',index=True)
    hidden:Mapped[bool]=mapped_column(Boolean,default=False)
    deleted_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    consent_at:Mapped[datetime]=mapped_column(DateTime,default=now)
    expires_at:Mapped[datetime]=mapped_column(DateTime,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now,index=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=now,onupdate=now)
    __table_args__=(CheckConstraint("kind IN ('LOST','FOUND')",name='valid_item_kind'),
        Index('ix_items_owner_order','owner_id','created_at','id'),
        CheckConstraint("state IN ('OPEN','MATCH_SUGGESTED','CLAIM_PENDING','RETURNED','CLOSED')",name='valid_item_state'),)


class ItemImage(Base):
    __tablename__='item_images'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    item_id:Mapped[str]=mapped_column(ForeignKey('items.id',ondelete='CASCADE'),index=True)
    storage_key:Mapped[str]=mapped_column(String(80),unique=True)
    content_hash:Mapped[str]=mapped_column(String(64))
    crop:Mapped[list|None]=mapped_column(JSON,nullable=True)
    position:Mapped[int]=mapped_column(Integer)
    embedding_key:Mapped[str|None]=mapped_column(String(64),nullable=True)
    descriptor:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    cache_signature:Mapped[str|None]=mapped_column(String(64),nullable=True)
    appearance:Mapped[list|None]=mapped_column(JSON,nullable=True)
    __table_args__=(UniqueConstraint('item_id','position',name='image_position'),)


class ClaimRequest(Base):
    __tablename__='claim_requests'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    item_id:Mapped[str]=mapped_column(ForeignKey('items.id'),index=True)
    claimant_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    evidence:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(16),default='PENDING')
    review_note:Mapped[str]=mapped_column(Text,default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=now,onupdate=now)
    __table_args__=(CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','WITHDRAWN','RETURNED')",name='valid_claim_state'),
        Index('one_active_claim_per_student','item_id','claimant_id',unique=True,postgresql_where=__import__('sqlalchemy').text("status IN ('PENDING','APPROVED')"),sqlite_where=__import__('sqlalchemy').text("status IN ('PENDING','APPROVED')")),
        Index('one_approved_claim_per_item','item_id',unique=True,postgresql_where=__import__('sqlalchemy').text("status IN ('APPROVED','RETURNED')"),sqlite_where=__import__('sqlalchemy').text("status IN ('APPROVED','RETURNED')")))


class Notification(Base):
    __tablename__='notifications'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    kind:Mapped[str]=mapped_column(String(40))
    message:Mapped[str]=mapped_column(String(300))
    item_id:Mapped[str|None]=mapped_column(ForeignKey('items.id'),nullable=True)
    claim_id:Mapped[str|None]=mapped_column(ForeignKey('claim_requests.id'),nullable=True)
    dedupe:Mapped[str]=mapped_column(String(180),unique=True)
    read_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now,index=True)
    __table_args__=(Index('ix_notifications_recipient_order','user_id','created_at','id'),)


class ModerationRecord(Base):
    __tablename__='moderation_records'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    actor_id:Mapped[str|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    action:Mapped[str]=mapped_column(String(60))
    item_id:Mapped[str|None]=mapped_column(ForeignKey('items.id'),nullable=True)
    claim_id:Mapped[str|None]=mapped_column(ForeignKey('claim_requests.id'),nullable=True)
    detail:Mapped[str]=mapped_column(String(300),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now,index=True)


class MatchJob(Base):
    __tablename__='match_jobs'
    item_id:Mapped[str]=mapped_column(ForeignKey('items.id'),primary_key=True)
    status:Mapped[str]=mapped_column(String(16),default='PENDING')
    error:Mapped[str]=mapped_column(String(200),default='')
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=now,onupdate=now)
    __table_args__=(Index('ix_match_jobs_pending','status','updated_at'),)


class MatchSuggestion(Base):
    __tablename__='match_suggestions'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    query_image_id:Mapped[str]=mapped_column(ForeignKey('item_images.id',ondelete='CASCADE'),index=True)
    candidate_image_id:Mapped[str]=mapped_column(ForeignKey('item_images.id',ondelete='CASCADE'),index=True)
    similarity:Mapped[float]=mapped_column(Float)
    appearance:Mapped[float|None]=mapped_column(Float,nullable=True)
    relevance:Mapped[str]=mapped_column(String(16))
    reason:Mapped[str]=mapped_column(String(300))
    model_version:Mapped[str]=mapped_column(String(64))
    __table_args__=(UniqueConstraint('query_image_id','candidate_image_id',name='unique_match_pair'),)


class RateLimit(Base):
    __tablename__='rate_limits'
    key:Mapped[str]=mapped_column(String(64),primary_key=True)
    count:Mapped[int]=mapped_column(Integer,default=0)
    expires_at:Mapped[datetime]=mapped_column(DateTime,index=True)


class FileDeletion(Base):
    __tablename__='file_deletions'
    storage_key:Mapped[str]=mapped_column(String(80),primary_key=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now)


class WorkerState(Base):
    __tablename__='worker_state'
    name:Mapped[str]=mapped_column(String(40),primary_key=True)
    heartbeat:Mapped[datetime]=mapped_column(DateTime,default=now)
    status:Mapped[str]=mapped_column(String(16),default='idle')
