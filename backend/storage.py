"""Metadata-free private image storage, never mounted as a static directory."""
import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4
import cv2
from fastapi import HTTPException
from backend.vision import decode_image,prepare,MAX_BYTES


def location(settings,key):
    if not re.fullmatch(r'[a-f0-9]{32}\.jpg',key):raise ValueError('Invalid private storage key.')
    root=settings.storage.resolve();path=(root/key).resolve()
    if path.parent!=root:raise ValueError('Invalid storage location.')
    return path


def save_upload(settings,upload,crop):
    raw=upload.file.read(MAX_BYTES+1)
    image=decode_image(raw)
    if crop is not None and (not isinstance(crop,list) or any(isinstance(v,bool) for v in crop)):
        raise ValueError('Crop must be four normalized numeric coordinates or explicit full image.')
    prepare(image,crop,normalize=False)
    h,w=image.shape[:2];scale=min(1,2000/max(h,w))
    if scale<1:image=cv2.resize(image,(round(w*scale),round(h*scale)),interpolation=cv2.INTER_AREA)
    prepare(image,crop,normalize=False)
    ok,encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,92])
    if not ok:raise ValueError('Could not safely encode this image.')
    content=encoded.tobytes();key=uuid4().hex+'.jpg'
    settings.storage.mkdir(parents=True,exist_ok=True)
    # A crash never publishes a partially written JPEG. Stale .part files are
    # collected by the retention worker, including failures before the caller
    # receives a key to roll back.
    destination=location(settings,key);temporary=destination.with_suffix('.part')
    try:
        with temporary.open('xb') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,destination)
    finally:temporary.unlink(missing_ok=True)
    return key,hashlib.sha256(content).hexdigest(),len(raw)


def remove(settings,key):location(settings,key).unlink(missing_ok=True)


def queue_deletion(db,key):
    from backend.models import FileDeletion,now
    if db.bind.dialect.name=='postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(FileDeletion).values(storage_key=key,created_at=now()).on_conflict_do_nothing())


def drain_deletions(factory,settings,limit=100):
    from backend.models import FileDeletion
    from backend.database import maintenance_guard
    from sqlalchemy import select
    with factory.begin() as db:
        maintenance_guard(db)
        for row in db.scalars(select(FileDeletion).order_by(FileDeletion.created_at).limit(limit).with_for_update(skip_locked=True)):
            try:remove(settings,row.storage_key)
            except OSError:continue  # Durable row remains for next worker tick.
            db.delete(row)


def read(settings,key):
    try:return decode_image(location(settings,key).read_bytes())
    except OSError:raise HTTPException(503,'This image is temporarily unavailable.') from None
