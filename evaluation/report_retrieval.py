"""Opt-in offline report retrieval. Never imported by the production worker."""
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import numpy as np
from backend.embedding_cache import image_key
from backend.semantic import PREPROCESSING_VERSION


class DescriptorStore:
    """Separate local experimental descriptors; no pickle or production DB writes.

    Reuses production content/model/preprocessing keying. The input is the final
    transformed image, so crop, mask and padding pixel changes invalidate entries.
    Delete this derived cache with the source dataset when retention requires it.
    """
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS descriptors (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.hits=0;self.misses=0

    def describe(self,encoder,image,recipe):
        preprocessing=PREPROCESSING_VERSION if encoder.name=='clip' else 'dino-bicubic256-center224-cls-v1'
        key=image_key(image,encoder.version,'phase6-v1/'+preprocessing+'/'+recipe).hex()
        row=self.db.execute('SELECT value FROM descriptors WHERE key=?',(key,)).fetchone()
        if row:
            try:
                result=json.loads(row[0]);vector=np.asarray(result['vector'],dtype=np.float32)
                if vector.ndim!=1 or not np.isfinite(vector).all() or abs(np.linalg.norm(vector)-1)>.001:
                    raise ValueError('Invalid cached descriptor')
                if encoder.semantic_routing and not {'label','margin','non_item_margin','alternatives'}<=result.keys():
                    raise ValueError('Incomplete cached category description')
                result['vector']=vector;self.hits+=1;return result
            except (ValueError,TypeError,KeyError):
                pass  # Corrupt derived entry is recomputed, never trusted.
        result=encoder.describe(image);self.misses+=1
        serialized={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in result.items()}
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO descriptors VALUES (?,?)',(key,json.dumps(serialized,allow_nan=False)))
        return result

    def close(self):
        self.db.close()


@dataclass(frozen=True)
class Config:
    alpha: float=1.
    aggregation: str='single'

    def __post_init__(self):
        if not np.isfinite(self.alpha) or not 0<=self.alpha<=1:
            raise ValueError('CLIP coefficient must lie in [0,1].')
        if self.aggregation not in ('single','max','mean','bidirectional_best'):
            raise ValueError('Unknown report aggregation.')


def rank_reports(query_views,candidate_views,descriptions,config,*,enabled=False):
    """Only IDs, vectors and grouping enter ranking, never identity/positive labels.

    Hybrid combination occurs per image pair BEFORE view aggregation. Report IDs
    are unique dictionary keys, with stable input order for exact score ties.
    """
    if not enabled:
        raise RuntimeError('Experimental report retrieval is disabled. Explicit opt-in is required.')
    if not query_views or len(set(query_views))!=len(query_views):
        raise ValueError('Query views must be nonempty and unique.')
    results=[]
    for report_id,views in candidate_views.items():
        if not views or len(set(views))!=len(views) or set(query_views)&set(views):
            raise ValueError('Candidate views must be unique and separate from query views.')
        qids=query_views[:1] if config.aggregation=='single' else query_views
        cids=views[:1] if config.aggregation=='single' else views
        matrix=np.zeros((len(qids),len(cids)),dtype=np.float64);components={}
        for name,weight in [('clip',config.alpha),('dinov2',1-config.alpha)]:
            if not weight:continue
            vectors=descriptions[name]
            q=np.array([vectors[i]['vector'] for i in qids]);c=np.array([vectors[i]['vector'] for i in cids])
            if not np.isfinite(q).all() or not np.isfinite(c).all():
                raise ValueError('Nonfinite descriptor.')
            pairs=q@c.T;components[name]=pairs;matrix+=weight*pairs
        if config.aggregation=='max':score=float(matrix.max())
        elif config.aggregation=='bidirectional_best':
            # Equal coverage of both view sets; no tuned scalar score weights.
            score=float((matrix.max(axis=1).mean()+matrix.max(axis=0).mean())/2)
        else:score=float(matrix.mean())
        best=np.unravel_index(int(matrix.argmax()),matrix.shape)
        best_pair={'query_image_id':qids[best[0]],'candidate_image_id':cids[best[1]],
                   'score':float(matrix[best]),'model_scores':{n:float(m[best]) for n,m in components.items()}}
        results.append({'report_id':report_id,'score':score,'best_pair':best_pair,
                        'pair_score_min':float(matrix.min()),'pair_score_max':float(matrix.max()),
                        'query_view_best_scores':[float(v) for v in matrix.max(axis=1)],
                        'candidate_view_best_scores':[float(v) for v in matrix.max(axis=0)],
                        'notice':'Experimental visual evidence; identity and ownership unverified.'})
    return sorted(results,key=lambda r:-r['score'])


def score_dataset(data,descriptions,config):
    rows=[]
    for query in data['queries']:
        groups={};representatives={}
        for cid in query['gallery_ids']:
            rid=data['index'][cid].get('report_id') or cid
            groups.setdefault(rid,[]);representatives[cid]=rid
            for view in query.get('candidate_views',{}).get(cid,[cid]):
                if view not in groups[rid]:groups[rid].append(view)
        results=rank_reports(query.get('view_ids',[query['image_id']]),groups,descriptions,config,enabled=True)
        # Labels used only after the ranking is complete.
        positives=list(dict.fromkeys(representatives[i] for i in query['positive_ids']))
        conditions=list(query.get('conditions',[]));entry=data['index'][query['image_id']]
        category=entry.get('metadata',{}).get('category')
        if category:conditions.append('category:'+category)
        for key,value in entry.get('capture',{}).items():conditions.append('capture:'+key+'='+str(value))
        hard=[]
        for cid in query['gallery_ids']:
            other=data['index'][cid]
            if (entry.get('product_model_id') and entry.get('product_model_id')==other.get('product_model_id')
                    and entry.get('instance_id') and other.get('instance_id') and entry['instance_id']!=other['instance_id']):
                hard.append(representatives[cid])
        if hard:conditions.append('same_model_hard_negative')
        rows.append({'query_id':query['id'],'positive_ids':positives,'ranking':[r['report_id'] for r in results],
                     'top_score':results[0]['score'] if results else None,'conditions':list(dict.fromkeys(conditions)),
                     'same_model_negative_reports':hard,'candidates':results})
    return rows
