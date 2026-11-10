"""Offline diagnostics and development-selected experiments; never installs policies.

Run: python -m evaluation.phase3 --output reports/phase3.json
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
from time import perf_counter
import numpy as np
from backend.vision import decode_image,prepare
from evaluation.dataset import load_manifest,validate_isolation,audit
from evaluation.encoders import ClipEncoder,DinoEncoder
from evaluation.pipeline import rank_query,local_evidence
from evaluation.metrics import summarize,fit_threshold
from scripts.benchmark_detection import peak_memory_mb


def record(query, ranking, scores):
    return {'query_id':query['id'],'positive_ids':query['positive_ids'],'ranking':ranking,
            'top_score':scores[ranking[0]] if ranking else None,'conditions':query.get('conditions',[])}


def ranked(query,scores):
    # Stable gallery order breaks exact ties, never labels or physical IDs.
    return record(query,sorted(query['gallery_ids'],key=lambda i:-scores[i]),scores)


def metadata_signal(a,b):
    fields=['category','brand','color','location']
    pairs=[(a[k].strip().casefold(),b[k].strip().casefold()) for k in fields if a.get(k) and b.get(k)]
    return sum(1 if x==y else -1 for x,y in pairs)/len(pairs) if pairs else 0.


def score_queries(data,descriptions,alpha=1.,aggregation='single',metadata_weight=0.):
    rows=[]
    for query in data['queries']:
        qviews=query.get('view_ids',[query['image_id']]) if aggregation!='single' else [query['image_id']]
        scores={}
        for cid in query['gallery_ids']:
            cviews=query.get('candidate_views',{}).get(cid,[cid]) if aggregation!='single' else [cid]
            components=[]
            for name,weight in [('clip',alpha),('dinov2',1-alpha)]:
                if not weight:
                    continue
                vectors=descriptions[name]
                pairs=[float(vectors[q]['vector'] @ vectors[c]['vector']) for q in qviews for c in cviews]
                components.append(weight*(max(pairs) if aggregation=='max' else float(np.mean(pairs))))
            visual=sum(components)
            a=data['index'][query['image_id']].get('metadata',{})
            b=data['index'][cid].get('metadata',{})
            scores[cid]=visual+metadata_weight*metadata_signal(a,b)
        rows.append(ranked(query,scores))
    return rows


def measured(rows,threshold=None):
    return {'metrics':summarize(rows,threshold),'by_condition':{
        condition:summarize([r for r in rows if condition in r.get('conditions',[])],threshold)
        for condition in sorted({c for r in rows for c in r.get('conditions',[])})},'queries':rows}


def select_config(trials):
    # Pure endpoint wins a tie over extra models/signals/views. CLIP before DINO
    # is a declared complexity tie break, not evidence that CLIP is better.
    def key(trial):
        config,rows=trial; m=summarize(rows)['mrr']
        return (m if m is not None else -1,config['alpha'] in (0,1),
                -config['metadata_weight'],config['aggregation']=='single',config['alpha'])
    return max(trials,key=key)[0]


def gate_policies(data,descriptions,regions):
    class Routing:
        semantic_routing=True
    policies={'original':[],'category_as_annotation':[],'retain_uncertain':[]};diagnostics=[]
    for query in data['queries']:
        result=rank_query(query,descriptions,regions,Routing())
        policies['original'].append({k:v for k,v in result.items() if k not in {'raw','candidates'}})
        policies['category_as_annotation'].append(result['raw'])
        candidates=result['candidates']; scores={r['id']:r['semantic_similarity'] for r in candidates}
        keep=sorted([r for r in candidates if r['relevance']!='excluded'],key=lambda r:(-r['semantic_similarity'],-(r['appearance_percent'] or 0),r['index']))
        policies['retain_uncertain'].append(record(query,[r['id'] for r in keep],scores))
        for row in candidates:
            diagnostics.append({'query_id':query['id'],'candidate_id':row['id'],
                'relation':query['relations'][row['id']], 'visual_similarity':row['semantic_similarity'],
                'gate':row['relevance'],'reason':row['relevance_reason'],**row['gate_diagnostic']})
    return {'policies':{k:measured(v) for k,v in policies.items()},'decisions':diagnostics,
            'suppressed_positives':sum(d['relation']=='same_instance' and d['gate']!='relevant' for d in diagnostics)}


def encode(data,encoder,cropped):
    descriptions={};regions={};times=[]
    encoder.clear_cache()
    for iid,entry in data['index'].items():
        if cropped and entry.get('manual_box') is None:
            raise ValueError('Every image needs a manual box for the cropped cohort.')
        image=decode_image(Path(entry['path']).read_bytes())
        start=perf_counter()
        region=prepare(image,entry.get('manual_box') if cropped else None,normalize=False)[0]
        descriptions[iid]=encoder.describe(region);regions[iid]=region
        times.append((perf_counter()-start)*1000)
    return descriptions,regions,{'images':len(times),'mean_prepare_encode_ms':float(np.mean(times)) if times else None,
                                'p95_prepare_encode_ms':float(np.percentile(times,95)) if times else None}


def run(dev,test):
    report={'status':'experimental_unvalidated','production_ranking_changed':False,
            'coverage':{'development':audit(dev),'independent':audit(test)},'recipes':{},'models':{},
            'manifests':{d['split']:d['manifest_sha256'] for d in [dev,test]},'platform':platform.platform()}
    descriptions={recipe:{split:{} for split in ['development','independent']} for recipe in ['full_frame','manual_crop']}
    for name,factory in [('clip',ClipEncoder),('dinov2',DinoEncoder)]:
        start=perf_counter()
        try:
            encoder=factory()
        except Exception as exc:
            report['models'][name]={'unavailable':str(exc)};continue
        report['models'][name]={'version':encoder.version,'loading_ms':(perf_counter()-start)*1000,'timing':{}}
        for recipe in descriptions:
            report['recipes'].setdefault(recipe,{})
            for data in [dev,test]:
                try:
                    desc,regions,timing=encode(data,encoder,recipe=='manual_crop')
                except ValueError as exc:
                    report['recipes'][recipe].setdefault('unavailable',{})[data['split']]=str(exc);continue
                descriptions[recipe][data['split']][name]=desc
                report['models'][name]['timing'][recipe+'/'+data['split']]=timing
                if name=='clip':
                    report['recipes'][recipe].setdefault('gates',{})[data['split']]=gate_policies(data,desc,regions)
        # Encoders are invoked serially; peak below is the whole orchestrator,
        # including CLIP's existing singleton and any simultaneous model residency.
        del encoder
    for recipe,splits in descriptions.items():
        result=report['recipes'][recipe];available=splits['development']
        for policy,development in result.get('gates',{}).get('development',{}).get('policies',{}).items():
            fit=fit_threshold(development['queries'])
            development['threshold_fit']=fit
            independent=result.get('gates',{}).get('independent',{}).get('policies',{}).get(policy)
            if independent is not None:
                independent['frozen_threshold_metrics']=summarize(independent['queries'],fit.get('threshold'))
        if not dev['queries'] or not available:
            result['status']='insufficient_data';continue
        alphas=([1.] if 'clip' in available else [])+([0.] if 'dinov2' in available else [])
        if len(alphas)==2:
            alphas += [.25,.5,.75]
        multi=report['coverage']['development']['multi_view_queries']>0
        metadata=any(metadata_signal(dev['index'][q['image_id']].get('metadata',{}),dev['index'][c].get('metadata',{}))!=0 for q in dev['queries'] for c in q['gallery_ids'])
        trials=[];summaries=[];independent_baselines={}
        for alpha in alphas:
            for aggregation in (['single','mean','max'] if multi else ['single']):
                for weight in ([0.,.05,.1,.25] if metadata else [0.]):
                    config={'alpha':alpha,'aggregation':aggregation,'metadata_weight':weight}
                    start=perf_counter();rows=score_queries(dev,available,**config)
                    trials.append((config,rows));summaries.append({'config':config,**measured(rows),'scoring_ms':(perf_counter()-start)*1000})
                    if alpha in (0,1) and aggregation=='single' and weight==0:
                        model='clip' if alpha==1 else 'dinov2'
                        threshold=fit_threshold(rows).get('threshold')
                        if test['queries'] and model in splits['independent']:
                            independent_baselines[model]=measured(score_queries(test,splits['independent'],**config),threshold)
                        else:
                            independent_baselines[model]={'status':'inconclusive'}
        selected=select_config(trials);selected_rows=next(rows for cfg,rows in trials if cfg==selected)
        fit=fit_threshold(selected_rows)
        result.update({'development_trials':summaries,'selected_on_development':selected,'threshold_fit':fit,
                       'independent_fixed_model_baselines':independent_baselines,
                       'multi_view_status':'evaluated' if multi else 'unavailable: no explicitly grouped multi-view queries',
                       'metadata_status':'evaluated' if metadata else 'unavailable: no informative supplied metadata'})
        required={name for name,w in [('clip',selected['alpha']),('dinov2',1-selected['alpha'])] if w}
        if test['queries'] and required <= set(splits['independent']):
            result['independent']=measured(score_queries(test,splits['independent'],**selected),fit.get('threshold'))
        else:
            result['independent']={'status':'inconclusive','reason':'Independent queries or required complete annotations/models unavailable.'}
    report['local_evidence']=local_evidence(dev) if dev['queries'] else {'status':'insufficient_data'}
    report['peak_combined_process_memory_mib']=peak_memory_mb()
    report['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('evaluation').glob('*.py'))}
    return report


def markdown(report):
    lines=['# Phase 3 experimental results','','Production ranking unchanged. No policy or similarity score verifies physical identity.',
           '',f"Coverage: `{json.dumps(report['coverage'])}`",'',
           'All development numbers below are tuning observations. Independent results are stored separately; absent data means inconclusive.',
           '', '| Recipe / CLIP gate policy | Recall@1 | Recall@5 | MRR |','|---|---:|---:|---:|']
    for recipe,result in report['recipes'].items():
        for policy,row in result.get('gates',{}).get('development',{}).get('policies',{}).items():
            m=row['metrics'];lines.append(f"| {recipe} / {policy} | {m['recall_at_1']} | {m['recall_at_5']} | {m['mrr']} |")
    lines+=['','## Model and fusion observations','','CLIP coefficient 1 uses CLIP; 0 uses DINOv2. Interior coefficients require both models. Selection maximizes development MRR; ties prefer single models, zero metadata contribution, single views, then CLIP. Coarse grids are experimental search spaces, not deployed weights.','',
            '| Recipe | CLIP coefficient | Views | Metadata coefficient | Recall@1 | MRR |','|---|---:|---|---:|---:|---:|']
    notes=[]
    for recipe,result in report['recipes'].items():
        for trial in result.get('development_trials',[]):
            c=trial['config'];m=trial['metrics'];lines.append(f"| {recipe} | {c['alpha']} | {c['aggregation']} | {c['metadata_weight']} | {m['recall_at_1']} | {m['mrr']} |")
        notes+=['',f"{recipe}: selected `{result.get('selected_on_development')}`. Independent: `{result.get('independent')}`.",
                str(result.get('multi_view_status','')),str(result.get('metadata_status','')),'']
    lines+=notes
    lines+=['## Gate decisions on positive pairs','','| Recipe | Query → candidate | Similarity | Predicted categories | Margins | Gate |','|---|---|---:|---|---|---|']
    for recipe,result in report['recipes'].items():
        for d in result.get('gates',{}).get('development',{}).get('decisions',[]):
            if d['relation']=='same_instance':
                lines.append(f"| {recipe} | {d['query_id']} → {d['candidate_id']} | {d['visual_similarity']} | {d['query_category']} / {d['candidate_category']} | {d['query_category_margin']:.4f} / {d['candidate_category_margin']:.4f} | {d['gate']} |")
    lines+=['','## CPU measurements','','Preparation and encoding exclude decode and model loading; one pass per image, two native threads, sequential inference. Hybrid costs require both encoders; scoring-only time is in JSON. Peak memory is combined process residency, not per-model memory.',
            '',f"Peak process memory: {report['peak_combined_process_memory_mib']:.1f} MiB."]
    for name,result in report['models'].items():
        lines.append(f"\n{name}: `{json.dumps(result)}`")
    local=report['local_evidence'].get('pairs',[])
    lines+=['',f"Local diagnostics: {len(local)} distinct pairs, {sum(p['geometric_inliers']>0 for p in local)} with geometric inliers. No local-feature reranker enabled.",
            '', 'Raw scores, every gate decision, condition slices, fitted threshold false positives/negatives, source/model/manifest hashes and frozen independent metrics are in the JSON. Threshold fitting is development only, including reject-all outcomes; no-match rejection is not independently validated.']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--development',default='data/retrieval-development.json')
    parser.add_argument('--independent',default='data/retrieval-independent.json');parser.add_argument('--output',default='reports/phase3.json')
    args=parser.parse_args();dev=load_manifest(args.development);test=load_manifest(args.independent);validate_isolation(dev,test)
    report=run(dev,test);output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8');output.with_suffix('.md').write_text(markdown(report),encoding='utf-8')
    print('Report: '+str(output))
