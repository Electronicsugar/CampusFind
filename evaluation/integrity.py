"""Strict opt-in labels and conservative, reviewable leakage screening."""
import hashlib
from pathlib import Path
import cv2
import numpy as np
from backend.vision import decode_image
from evaluation.dataset import validate_isolation, audit


def valid_box(box):
    return (isinstance(box,list) and len(box)==4
            and all(type(v) in (int,float) and np.isfinite(v) for v in box)
            and 0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1)


def validate_v3(manifest,index):
    reports={};instances={}
    for entry in index.values():
        for field in ('instance_id','report_id','product_model_id','capture_session_id','source_asset_id','label_provenance'):
            if not isinstance(entry.get(field),str) or not entry[field].strip():
                raise ValueError('Schema 3 requires nonempty '+field+'; do not guess labels.')
        category=entry.get('metadata',{}).get('category')
        if not category or not category.strip():
            raise ValueError('Schema 3 requires category metadata.')
        if not isinstance(entry.get('capture'),dict) or not entry['capture']:
            raise ValueError('Schema 3 requires capture conditions.')
        if any(not isinstance(k,str) or not isinstance(v,(str,bool,int,float)) for k,v in entry['capture'].items()):
            raise ValueError('Capture values must be scalar annotations.')
        if entry.get('role') not in ('query','gallery'):
            raise ValueError('Schema 3 photos require a query/gallery role.')
        identity=(entry['instance_id'],entry['role'])
        if reports.setdefault(entry['report_id'],identity)!=identity:
            raise ValueError('Report photos must agree on instance and role.')
        model=(entry['product_model_id'],category)
        if instances.setdefault(entry['instance_id'],model)!=model:
            raise ValueError('Physical instance has conflicting model/category labels.')
        if 'manual_box' in entry and not valid_box(entry['manual_box']):
            raise ValueError('Invalid manual_box.')
        if 'localization_boxes' in entry:
            if not isinstance(entry['localization_boxes'],list) or any(not valid_box(b) for b in entry['localization_boxes']):
                raise ValueError('Invalid localization boxes.')
            if not entry.get('localization_provenance'):
                raise ValueError('Localization boxes require independent annotation provenance.')
    for query in manifest['queries']:
        groups=[(query['image_id'],query.get('view_ids',[query['image_id']]),'query')]
        groups += [(cid,query.get('candidate_views',{}).get(cid,[cid]),'gallery') for cid in query['gallery_ids']]
        seen=set()
        for representative,views,role in groups:
            rid=index[representative]['report_id']
            if rid in seen:
                raise ValueError('Use exactly one representative per report.')
            seen.add(rid)
            if any(index[i]['report_id']!=rid or index[i]['role']!=role for i in views):
                raise ValueError('View groups must match report IDs and query/gallery roles.')


def perceptual_hash(image):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    low=cv2.dct(cv2.resize(gray,(32,32)).astype(np.float32))[:8,:8].ravel()[1:]
    return sum(int(v>np.median(low))<<i for i,v in enumerate(low))


def screen_splits(dev,test):
    """pHash is a review signal, not an identity or duplicate oracle.

    Review decisions bind file hashes, so replacing a photo invalidates a waiver.
    Exact pixels/instances and declared source/session leakage cannot be waived.
    """
    validate_isolation(dev,test)
    for field in ('source_asset_id','capture_session_id','report_id'):
        left={i[field] for i in dev['index'].values() if i.get(field)}
        right={i[field] for i in test['index'].values() if i.get(field)}
        if left & right:
            raise ValueError('Cross-split '+field+' leakage.')
    hashes={}
    if dev['index'] and test['index']:
        for data in (dev,test):
            for entry in data['index'].values():
                hashes[entry['sha256']]=perceptual_hash(decode_image(Path(entry['path']).read_bytes()))
    reviews={}
    for review in test.get('near_duplicate_reviews',[]):
        pair=review.get('sha256_pair',[])
        if (len(pair)!=2 or any(not isinstance(v,str) or len(v)!=64 for v in pair)
                or review.get('decision')!='distinct_capture'
                or not review.get('reviewer') or not review.get('reason')):
            raise ValueError('Near-duplicate reviews need two hashes, reviewer, reason and distinct_capture decision.')
        reviews[tuple(sorted(pair))]=review
    suspects=[]
    for a in dev['index'].values():
        for b in test['index'].values():
            distance=(hashes[a['sha256']]^hashes[b['sha256']]).bit_count()
            if distance<=4:
                pair=tuple(sorted((a['sha256'],b['sha256'])))
                suspects.append({'development_id':a['id'],'independent_id':b['id'],
                                 'sha256_pair':list(pair),'hamming_distance':distance,'reviewed':pair in reviews})
    unknown=sum(not e.get('instance_id') for e in test['index'].values())
    return {'status':'blocked_pending_review' if unknown or any(not s['reviewed'] for s in suspects) else 'screen_passed',
            'unknown_independent_instance_images':unknown,'suspected_near_duplicates':suspects,
            'note':'63-bit pHash distance <=4 flags review only; crops and viewpoint duplicates can evade it. Manual provenance review remains required.'}


def coverage(data):
    result=audit(data)
    result['queries']=len(data['queries'])
    result['positive_queries']=sum(bool(q['positive_ids']) for q in data['queries'])
    result['reports']=len({e['report_id'] for e in data['index'].values() if e.get('report_id')})
    result['labeled_localization_images']=sum('localization_boxes' in e for e in data['index'].values())
    result['reviewed_masks']=sum(bool(e.get('segmentation',{}).get('reviewed')) for e in data['index'].values())
    hard=0
    for q in data['queries']:
        a=data['index'][q['image_id']]
        for cid in q['gallery_ids']:
            b=data['index'][cid]
            hard+=int(bool(a.get('product_model_id')) and a.get('product_model_id')==b.get('product_model_id')
                      and bool(a.get('instance_id')) and bool(b.get('instance_id')) and a['instance_id']!=b['instance_id'])
    result['same_model_negative_pairs']=hard
    return result
