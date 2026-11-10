"""Offline preprocessing recipes and ranking. Does not change API defaults."""
from time import perf_counter
import numpy as np
from backend.vision import prepare, appearance_similarity, decode_image, compare
from backend.semantic import relevance
from backend.gallery import sort_results
from backend.detection import get_detector
from evaluation.metrics import summarize, fit_threshold


def pad_square(image, mean):
    h,w=image.shape[:2];side=max(h,w)
    # Fill with the encoder's mean so padding is approximately zero after normalization.
    background=np.round(np.asarray(mean)[::-1]*255).astype(np.uint8)
    result=np.empty((side,side,3),np.uint8);result[:]=background
    top,left=(side-h)//2,(side-w)//2
    result[top:top+h,left:left+w]=image
    return result


def reviewed_box(entry,proposals):
    review=entry.get('detector_review')
    if not review:
        raise ValueError('Reviewed detector experiment needs an explicit per-image review; never choose by ground-truth overlap.')
    if review['decision'] == 'accept':
        index=review['proposal_index']
        if isinstance(index,bool) or not isinstance(index,int) or not 0 <= index < len(proposals):
            raise ValueError('Recorded detector proposal is unavailable; review again.')
        if 'box' not in review or not np.allclose(proposals[index]['box'],review['box'],atol=1e-4,rtol=0):
            raise ValueError('Detector proposal changed since review; review again instead of silently accepting it.')
        return proposals[index]['box']
    if review['decision'] == 'manual_fallback':
        if entry.get('manual_box') is None:
            raise ValueError('Manual fallback requires an explicit manual box.')
        return entry['manual_box']
    if review['decision'] == 'full_frame':
        return None
    raise ValueError('Unknown detector review decision.')


def rank_query(query,descriptions,regions,encoder,global_descriptions=None,alpha=None):
    qid=query['image_id'];rows=[]
    for index,cid in enumerate(query['gallery_ids']):
        q,c=descriptions[qid],descriptions[cid]
        score=float(q['vector'] @ c['vector'])
        if alpha is not None:
            score=alpha*float(global_descriptions[qid]['vector'] @ global_descriptions[cid]['vector'])+(1-alpha)*score
        appearance=appearance_similarity(regions[qid],regions[cid])
        semantic=relevance(q,c) if encoder.semantic_routing else {'relevance':'relevant','relevance_reason':'Uncalibrated visual retrieval; identity unknown.'}
        if encoder.semantic_routing and appearance['appearance_percent'] is None:
            semantic['relevance']='uncertain'
            semantic['relevance_reason']='Too little visible structure to assess this candidate reliably.'
        diagnostic={}
        if encoder.semantic_routing:
            diagnostic={'query_category':q['label'],'query_category_margin':q['margin'],
                        'candidate_category':c['label'],'candidate_category_margin':c['margin'],
                        'candidate_non_item_margin':c.get('non_item_margin'),
                        'query_alternatives':q.get('alternatives'), 'candidate_alternatives':c.get('alternatives'),
                        'structure_override':appearance['appearance_percent'] is None}
        rows.append({'index':index,'id':cid,**appearance,**semantic,'semantic_similarity':round(score,4),'gate_diagnostic':diagnostic})
    sort_results(rows)
    routed=[r for r in rows if r['relevance']=='relevant']
    # Raw embedding ranking exposes errors hidden by category routing.
    raw=sorted(rows,key=lambda r:(-r['semantic_similarity'],-(r['appearance_percent'] or 0),r['index']))
    def record(ranking):
        return {'query_id':query['id'],'positive_ids':query['positive_ids'],
                'ranking':[r['id'] for r in ranking],'top_score':ranking[0]['semantic_similarity'] if ranking else None,
                'conditions':query.get('conditions',[])}
    return {**record(routed),'raw':record(raw),'candidates':rows}


def evaluate(data,encoder,recipes=None,fusion_alphas=None):
    from pathlib import Path
    if not data['queries']:
        return {'status':'inconclusive','reason':'No independent labeled queries available.','variants':{}}
    recipes=recipes or ['full_frame','manual_crop','reviewed_detector','detector_top','square_pad','fusion']
    images={i:decode_image(Path(entry['path']).read_bytes()) for i,entry in data['index'].items()}
    proposal_rows={};detection_ms=0;detection_error=None
    if any(name in recipes for name in ['reviewed_detector','detector_top']):
        started=perf_counter()
        try:
            detector=get_detector('nanodet')
            for image_id,image in images.items():
                proposal_rows[image_id]=detector.detect(image)
        except Exception as exc:
            detection_error=str(exc)
        detection_ms=(perf_counter()-started)*1000
    report={'status':'development_diagnostic' if data['split']=='development' else 'evaluation',
            'model_version':encoder.version,'detector_total_ms':detection_ms,
            'detector_images':len(proposal_rows),'variants':{},'unavailable_variants':{}}
    for name in recipes:
        if detection_error and name in {'reviewed_detector','detector_top'}:
            report['unavailable_variants'][name]='Detector unavailable: '+detection_error
            continue
        encoder.clear_cache()
        descriptions={};regions={};global_desc={}
        def transform(image_id):
            entry=data['index'][image_id];image=images[image_id]
            if name == 'full_frame':
                box=None
            elif name == 'reviewed_detector':
                box=reviewed_box(entry,proposal_rows[image_id])
            elif name == 'detector_top':
                proposals=proposal_rows[image_id];box=proposals[0]['box'] if proposals else None
            else:
                if entry.get('manual_box') is None:
                    raise ValueError('Manual crop experiment needs a box for every image.')
                box=entry['manual_box']
            region,_=prepare(image,box,normalize=False)
            if name == 'square_pad':
                region=pad_square(region,encoder.mean)
            return region
        # Require the same complete cohort for every recipe. Missing annotations
        # disable that recipe rather than quietly dropping difficult examples.
        try:
            for image_id in images:
                transform(image_id)
        except ValueError as exc:
            report['unavailable_variants'][name]=str(exc)
            continue
        started=perf_counter()
        for image_id,image in images.items():
            region=transform(image_id);regions[image_id]=region
            descriptions[image_id]=encoder.describe(region)
            if name == 'fusion':
                full,_=prepare(image,normalize=False);global_desc[image_id]=encoder.describe(full)
        encode_ms=(perf_counter()-started)*1000
        started=perf_counter()
        for image_id,image in images.items():
            encoder.describe(transform(image_id))
            if name == 'fusion':
                full,_=prepare(image,normalize=False);encoder.describe(full)
        repeat_ms=(perf_counter()-started)*1000
        coefficients=[None] if name != 'fusion' else (fusion_alphas if fusion_alphas is not None else [0,.25,.5,.75,1])
        for alpha in coefficients:
            key=name if alpha is None else f'fusion_global_{alpha:g}'
            rows=[rank_query(q,descriptions,regions,encoder,global_desc,alpha) for q in data['queries']]
            raw=[r['raw'] for r in rows]
            report['variants'][key]={'metrics':summarize(rows),'raw_embedding_metrics':summarize(raw),
                'development_threshold_fit':fit_threshold(rows) if data['split']=='development' else None,
                'prepare_encode_ms_per_image':encode_ms/len(images),
                'repeated_prepare_encode_ms_per_image':repeat_ms/len(images),
                'global_coefficient':alpha,'queries':rows}
            if hasattr(encoder,'model') and hasattr(encoder.model,'cache'):
                report['variants'][key]['encoder_cache_stats']=encoder.model.cache.stats()
            elif hasattr(encoder,'cache'):
                report['variants'][key]['encoder_cache_stats']=encoder.cache.stats()
    return report


def local_evidence(data):
    """Diagnostic only: never rerank just because a local matcher was available."""
    from pathlib import Path
    rows=[];seen=set()
    for query in data['queries']:
        for candidate in query['gallery_ids']:
            pair=tuple(sorted([query['image_id'],candidate]))
            if pair in seen:
                continue
            seen.add(pair)
            a,b=[data['index'][i] for i in pair]
            images=[decode_image(Path(r['path']).read_bytes()) for r in [a,b]]
            started=perf_counter()
            result,_=compare(*images,a.get('manual_box'),b.get('manual_box'),normalize=True)
            rows.append({'pair':pair,'relation':query['relations'][candidate],
                         'geometric_inliers':result['geometric_inliers'],'tentative_matches':result['tentative_matches'],
                         'elapsed_ms':(perf_counter()-started)*1000})
    return {'status':'diagnostic_only_no_reranking','pairs':rows}
