"""Explicitly enabled offline Phase VI runner; no production side effects."""
import argparse
from dataclasses import asdict
import hashlib
import json
import platform
from pathlib import Path
from time import perf_counter, process_time
import cv2
import numpy as np
from backend.detection import get_detector, iou
from backend.vision import decode_image, prepare
from evaluation.dataset import load_manifest
from evaluation.integrity import screen_splits, coverage
from evaluation.encoders import ClipEncoder, DinoEncoder
from evaluation.pipeline import pad_square, reviewed_box
from evaluation.phase3 import gate_policies, measured
from evaluation.metrics import summarize, fit_threshold
from evaluation.report_retrieval import Config, DescriptorStore, score_dataset
from scripts.benchmark_detection import peak_memory_mb

RECIPES=('full_frame','manual_crop','square_pad','reviewed_detector','segmented')


def transform(entry,image,recipe,mean,proposals=None):
    if recipe=='full_frame':box=None
    elif recipe=='reviewed_detector':box=reviewed_box(entry,proposals)
    else:
        box=entry.get('manual_box')
        if box is None:raise ValueError('Complete manual crop annotations required.')
    if recipe=='segmented':
        annotation=entry.get('segmentation',{})
        if annotation.get('reviewed') is not True or not annotation.get('provenance'):
            raise ValueError('Complete reviewed segmentation masks required; no automatic mask selection.')
        raw=Path(annotation['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=annotation.get('sha256'):
            raise ValueError('Segmentation mask changed since review.')
        mask=decode_image(raw)
        if mask.shape!=image.shape or not np.array_equal(mask[:,:,0],mask[:,:,1]) or not np.array_equal(mask[:,:,0],mask[:,:,2]):
            raise ValueError('Mask must match EXIF-oriented image dimensions and be grayscale.')
        if not set(np.unique(mask))<={0,255} or not np.any(mask):
            raise ValueError('Mask must be nonempty binary 0/255.')
        image=image.copy();image[mask[:,:,0]==0]=np.round(np.asarray(mean)[::-1]*255).astype(np.uint8)
    region=prepare(image,box,normalize=False)[0]
    return pad_square(region,mean) if recipe in ('square_pad','segmented') else region


def detector_diagnostics(data,detector):
    proposals={};rows=[];times=[]
    for iid,entry in data['index'].items():
        image=decode_image(Path(entry['path']).read_bytes());start=perf_counter()
        predictions=detector.detect(image);times.append((perf_counter()-start)*1000)
        proposals[iid]=predictions
        row={'image_id':iid,'proposal_count':len(predictions),'review_decision':entry.get('detector_review',{}).get('decision')}
        # Never repurpose retrieval manual crops as localization ground truth.
        if 'localization_boxes' in entry and entry.get('localization_provenance'):
            boxes=entry['localization_boxes']
            row['best_ious']=[max((iou(b,p['box']) for p in predictions),default=0.) for b in boxes]
            row['negative_image_has_proposals']=bool(predictions) if not boxes else None
        rows.append(row)
    overlaps=[v for row in rows for v in row.get('best_ious',[])]
    negatives=[r['negative_image_has_proposals'] for r in rows if r.get('negative_image_has_proposals') is not None]
    return proposals,{'status':'labeled_observations' if overlaps or negatives else 'inconclusive_no_localization_labels',
                      'labeled_objects':len(overlaps),'proposal_recall_iou50':sum(v>=.5 for v in overlaps)/len(overlaps) if overlaps else None,
                      'labeled_negative_images':len(negatives),'negative_image_proposal_rate':float(np.mean(negatives)) if negatives else None,
                      'mean_inference_ms':float(np.mean(times)) if times else None,'images':rows}


def encode(data,encoder,recipe,store,proposals):
    descriptions={};regions={};times=[];cpu=process_time();hits=store.hits;misses=store.misses
    for iid,entry in data['index'].items():
        start=perf_counter()
        image=decode_image(Path(entry['path']).read_bytes())
        region=transform(entry,image,recipe,encoder.mean,proposals.get(iid))
        descriptions[iid]=store.describe(encoder,region,recipe);regions[iid]=region
        times.append((perf_counter()-start)*1000)
    return descriptions,regions,{'images':len(times),'median_decode_prepare_encode_ms':float(np.median(times)) if times else None,
                                'p95_decode_prepare_encode_ms':float(np.percentile(times,95)) if times else None,
                                'cpu_seconds':process_time()-cpu,'persistent_hits':store.hits-hits,'persistent_misses':store.misses-misses}


def choose(trials):
    viable=[t for t in trials if t['development']['metrics']['mrr'] is not None]
    if not viable:return None
    return max(viable,key=lambda t:(t['development']['metrics']['mrr'],
        t['config']['alpha'] in (0.,1.),t['config']['aggregation']=='single',t['config']['alpha']))


def independent_result(data,descriptions,config,threshold,screen):
    required={name for name,w in [('clip',config.alpha),('dinov2',1-config.alpha)] if w}
    if screen['status']!='screen_passed' or not data['queries'] or not required<=descriptions.keys():
        return {'status':'inconclusive','reason':'No usable independent queries, unresolved leakage review, or required preprocessing/model unavailable.'}
    return {'status':'held_out_observations_not_deployment_validation',**measured(score_dataset(data,descriptions,config),threshold)}


def run(dev,test,cache_path,*,enabled=False,recipes=RECIPES):
    if not enabled:raise RuntimeError('Pass --enable-experimental to run offline experiments.')
    screen=screen_splits(dev,test)
    report={'status':'experimental_unvalidated','production_ranking_changed':False,
            'coverage':{d['split']:coverage(d) for d in (dev,test)},'split_screen':screen,
            'manifest_sha256':{d['split']:d['manifest_sha256'] for d in (dev,test)},
            'platform':platform.platform(),'python':platform.python_version(),'recipes':{},'models':{},'detector':{},
            'local_features':'Not repeated: previous SIFT yielded no inliers; no new distinctive-mark photos or hypothesis.',
            'region_parts':'Unavailable: no reviewed corresponding distinctive-part regions.',
            'metadata':'Not tuned: existing photos lack informative metadata; schema retains optional fields.'}
    proposals={d['split']:{} for d in (dev,test)}
    try:
        detector=get_detector('nanodet')
        for d in (dev,test):
            if d['split']=='independent' and screen['status']!='screen_passed':continue
            proposals[d['split']],report['detector'][d['split']]=detector_diagnostics(d,detector)
    except Exception as exc:
        report['detector']['unavailable']=str(exc)
    all_desc={recipe:{d['split']:{} for d in (dev,test)} for recipe in recipes}
    store=DescriptorStore(cache_path)
    try:
        for name,factory in [('clip',ClipEncoder),('dinov2',DinoEncoder)]:
            start=perf_counter()
            try:encoder=factory()
            except Exception as exc:
                report['models'][name]={'unavailable':str(exc)};continue
            report['models'][name]={'version':encoder.version,'load_ms':(perf_counter()-start)*1000,'timings':{}}
            for recipe in recipes:
                result=report['recipes'].setdefault(recipe,{'unavailable':{},'gate_diagnostics':{}})
                for d in (dev,test):
                    if not d['queries'] or (d['split']=='independent' and screen['status']!='screen_passed'):continue
                    try:
                        if recipe=='reviewed_detector' and len(proposals[d['split']])!=len(d['index']):
                            raise ValueError('Detector proposals unavailable.')
                        desc,regions,timing=encode(d,encoder,recipe,store,proposals[d['split']])
                    except (ValueError,OSError,KeyError,RuntimeError) as exc:
                        result['unavailable'][name+'/'+d['split']]=str(exc);continue
                    all_desc[recipe][d['split']][name]=desc
                    report['models'][name]['timings'][recipe+'/'+d['split']]=timing
                    if name=='clip':result['gate_diagnostics'][d['split']]=gate_policies(d,desc,regions)
                    del regions
            del encoder
        for recipe,splits in all_desc.items():
            result=report['recipes'].setdefault(recipe,{'unavailable':{},'gate_diagnostics':{}})
            names=splits['development'];alphas=([1.] if 'clip' in names else [])+([0.] if 'dinov2' in names else [])
            if len(alphas)==2:alphas += [.25,.5,.75]
            multi=coverage(dev)['multi_view_queries']>0
            result['multi_view_status']='development_observations' if multi else 'inconclusive_no_grouped_multi_photo_queries'
            trials=[]
            for alpha in alphas:
                for aggregation in (['single','max','mean','bidirectional_best'] if multi else ['single']):
                    config=Config(alpha,aggregation);start=perf_counter()
                    rows=score_dataset(dev,names,config)
                    trials.append({'config':asdict(config),'development':measured(rows),'scoring_ms':(perf_counter()-start)*1000})
            result['development_trials']=trials
            selected=choose(trials)
            if selected:
                # Fit and freeze using development only. No independent score enters selection.
                config=Config(**selected['config']);fit=fit_threshold(selected['development']['queries'])
                result['frozen_config']={'recipe':recipe,**asdict(config),'threshold':fit.get('threshold'),
                    'selection':'Development MRR; ties prefer single model, single view, then CLIP.',
                    'development_manifest_sha256':dev['manifest_sha256'],'deployable':False}
                result['threshold_fit']=fit
                result['independent']=independent_result(test,splits['independent'],config,fit.get('threshold'),screen)
                result['independent_fixed_baselines']={}
                for trial in trials:
                    c=Config(**trial['config'])
                    if c.alpha in (0.,1.) and c.aggregation=='single':
                        threshold=fit_threshold(trial['development']['queries']).get('threshold')
                        result['independent_fixed_baselines']['clip' if c.alpha else 'dinov2']=independent_result(test,splits['independent'],c,threshold,screen)
            else:result['independent']={'status':'inconclusive','reason':'No development configuration could be selected.'}
            for policy,gate in result['gate_diagnostics'].get('development',{}).get('policies',{}).items():
                fit=fit_threshold(gate['queries']);gate['threshold_fit']=fit
                independent=result['gate_diagnostics'].get('independent',{}).get('policies',{}).get(policy)
                if independent is not None:independent['frozen_threshold_metrics']=summarize(independent['queries'],fit.get('threshold'))
        report['cache']={'hits':store.hits,'misses':store.misses,'scope':'isolated experimental descriptors; no production database writes'}
    finally:store.close()
    report['peak_combined_process_rss_mib']=peak_memory_mb()
    sources=list(Path('evaluation').glob('*.py'))+[Path('backend')/n for n in ('semantic.py','vision.py','nanodet.py','detection.py','embedding_cache.py','gallery.py')]
    report['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    return report


def markdown(report):
    lines=['# Phase VI measured experiments','', '**Experimental; production unchanged.** Independent accuracy requires held-out real photographs.',
           '', 'Coverage: `'+json.dumps(report['coverage'])+'`','',
           '| Recipe | CLIP coefficient | Views | R@1 | R@5 | MRR | mAP |',
           '| --- | ---: | --- | ---: | ---: | ---: | ---: |']
    for recipe,result in report['recipes'].items():
        for t in result['development_trials']:
            c=t['config'];m=t['development']['metrics']
            lines.append(f"| {recipe} | {c['alpha']} | {c['aggregation']} | {m['recall_at_1']} | {m['recall_at_5']} | {m['mrr']} | {m['mean_average_precision']} |")
    lines += ['', 'All table values above are development observations. Report-level raw visual ranking is separate from category routing.', '', '## Availability and frozen evaluation']
    for recipe,result in report['recipes'].items():
        lines += ['',f"{recipe}: independent `{result['independent']['status']}`; multi-view `{result['multi_view_status']}`.",
                  'Unavailable: `'+json.dumps(result['unavailable'])+'`',
                  'Frozen development configuration: `'+json.dumps(result.get('frozen_config'))+'`']
    lines += ['', '## Timings', '', 'Includes decoding, preparation, cache lookup and encoding. First-use model loading is separate; persistent hits are not cold inference. Sequential CPU encoders use two native threads. Peak RSS is combined process residency, not per-model memory.',
              '',f"Peak combined RSS: {report['peak_combined_process_rss_mib']} MiB."]
    for name,model in report['models'].items():lines += ['',name+': `'+json.dumps(model)+'`']
    lines += ['', 'Raw JSON contains all query rankings, supporting pairs, category decisions, threshold fits, false acceptances/rejections, condition slices, cache counts and source/model/manifest hashes. No similarity is an identity probability.',
              '', report['local_features'],report['region_parts'],report['metadata']]
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-experimental',action='store_true')
    parser.add_argument('--development',default='data/retrieval-development.json')
    parser.add_argument('--independent',default='data/retrieval-independent.json')
    parser.add_argument('--cache',default='.local/phase6/descriptors.sqlite')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if not args.enable_experimental:parser.error('Experimental engine disabled: pass --enable-experimental explicitly.')
    output=Path(args.output)
    if output.exists() or output.with_suffix('.md').exists():parser.error('Choose a new output path; previous experiments are immutable.')
    dev=load_manifest(args.development);test=load_manifest(args.independent)
    report=run(dev,test,args.cache,enabled=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    output.with_suffix('.md').write_text(markdown(report),encoding='utf-8')
    print('Experimental report saved: '+str(output))


if __name__=='__main__':main()
