"""python -m evaluation.run --models clip [dinov2] --output reports/retrieval.json"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
from evaluation.dataset import load_manifest, validate_isolation
from evaluation.encoders import ClipEncoder, DinoEncoder
from evaluation.pipeline import evaluate, local_evidence
from evaluation.metrics import summarize
from scripts.benchmark_detection import peak_memory_mb


def coverage(data):
    positives=[q for q in data['queries'] if q['positive_ids']]
    instances={data['index'][q['image_id']].get('instance_id') for q in positives}
    instances.discard(None)
    return {'images':len(data['images']),'queries':len(data['queries']),
            'positive_queries':len(positives),'no_match_queries':len(data['queries'])-len(positives),
            'known_positive_physical_instances':len(instances),
            'conditions':sorted({c for q in data['queries'] for c in q.get('conditions',[])}),
            'known_gaps':data.get('known_gaps',[]),'label_provenance':data.get('label_provenance'),
            'manifest_sha256':data['manifest_sha256']}


def experiment(model,dev,test,local=False):
    started=perf_counter();encoder=ClipEncoder() if model == 'clip' else DinoEncoder()
    loading_ms=(perf_counter()-started)*1000
    development=evaluate(dev,encoder)
    fusions=[(v['metrics']['mrr'],v['global_coefficient']) for k,v in development['variants'].items() if k.startswith('fusion_') and v['metrics']['mrr'] is not None]
    best=max(fusions,key=lambda x:(x[0],x[1]))[1] if fusions else None
    independent=evaluate(test,encoder,fusion_alphas=[best] if best is not None else [])
    for name,variant in independent['variants'].items():
        fit=development['variants'].get(name,{}).get('development_threshold_fit') or {}
        threshold=fit.get('threshold')
        variant['frozen_development_threshold_metrics']=summarize(variant['queries'],threshold) if threshold is not None else None
    evidence=local_evidence(dev) if local else None
    return {'model':model,'loading_ms':loading_ms,'peak_process_memory_mib':peak_memory_mb(),
            'development':development,'independent':independent,
            'fusion_selection':{'development_only_global_coefficient':best,
                                'objective':'Development routed MRR; exact ties prefer the global coefficient to avoid unnecessary crop dependence.',
                                'deployable':False},'local_evidence':evidence}


def markdown(report):
    independent_available=bool(report['independent_coverage']['queries'])
    conclusion='Independent observations are available; cohort size, coverage and frozen-policy results still limit conclusions.' if independent_available else '**Generalization result: inconclusive.** Development observations are not independent accuracy evidence.'
    lines=['# Retrieval evaluation results','',conclusion,
           '',f"Development coverage: {report['development_coverage']['images']} images, {report['development_coverage']['positive_queries']} positive queries, {report['development_coverage']['no_match_queries']} no-match queries, {report['development_coverage']['known_positive_physical_instances']} known positive physical instance(s).",
           f"Independent coverage: {report['independent_coverage']['queries']} queries.",'',
           'Recall@k is the fraction of labeled positive images retrieved in the first k results, averaged over positive queries. MRR includes zero for missed positives. Current app suggestions have no identity-acceptance policy; proposal rejection is reported separately from thresholded acceptance.',
           '', '| Model / recipe | Routed R@1 | Routed R@5 | Routed MRR | Raw R@1 | Raw MRR | Wrong routed top-1 / positive | No-match queries with proposals | Prepare + encode ms/image | Repeat ms/image |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    notes=[];acceptance_rows=[]
    def number(v):
        return 'N/A' if v is None else f'{v:.3f}'
    for result in report['models']:
        if 'error' in result:
            notes.append(f"Model {result['model']}: not evaluated ({result['error'][:250]}).")
            continue
        for name,variant in result['development']['variants'].items():
            m=variant['metrics']
            raw=variant['raw_embedding_metrics']
            lines.append(f"| {result['model']} / {name} | {number(m['recall_at_1'])} | {number(m['recall_at_5'])} | {number(m['mrr'])} | {number(raw['recall_at_1'])} | {number(raw['mrr'])} | {m['wrong_top1_on_positive_queries']} / {m['positive_queries']} | {m['no_match_queries_with_proposals']} / {m['no_match_queries']} | {variant['prepare_encode_ms_per_image']:.2f} | {variant['repeated_prepare_encode_ms_per_image']:.2f} |")
            fit=variant['development_threshold_fit'] or {}
            if 'development_metrics' in fit:
                a=fit['development_metrics']
                acceptance_rows.append(f"| {result['model']} / {name} | {a['threshold']:.5f} | {a['false_positive_count']} | {number(a['false_positive_rate_on_no_match_queries'])} | {number(a['no_match_rejection'])} | {number(a['correct_acceptance_recall'])} |")
        notes.append(f"{result['model']}: model loading {result['loading_ms']:.1f} ms; peak worker process working set {result['peak_process_memory_mib']:.1f} MiB.")
        for recipe,error in result['development'].get('unavailable_variants',{}).items():
            notes.append(f"Unavailable {result['model']} / {recipe}: {error}")
    lines.extend(['']+notes+['','DINOv2 has no text/category classifier here: its routed and raw lists are identical. Compare raw columns between encoders; CLIP routed columns additionally include the existing category policy.',
        '', '## Development-only abstention fit', '',
        'Optimistic fitted observations, not validation. Thresholds maximize balanced correct acceptance and no-match rejection on development; conservative ties prefer rejection. Empty independent data means no validated false-positive or rejection rate.', '',
        '| Model / recipe | Fitted threshold | False accepted queries | No-match false-positive rate | No-match rejection | Correct acceptance recall |',
        '|---|---:|---:|---:|---:|---:|']+acceptance_rows)
    lines.extend(['','## Independent evaluation',''])
    if not independent_available:
        lines.append('No independent queries: Recall@1, Recall@5, MRR, false-positive rate and no-match rejection are unavailable. Development-fitted thresholds have no independent validation.')
    else:
        lines.extend(['Frozen development thresholds and the development-selected fusion coefficient only. No parameter selection uses these results.','',
            '| Model / recipe | Recall@1 | Recall@5 | MRR | False accepted queries | No-match rejection |',
            '|---|---:|---:|---:|---:|---:|'])
        for result in report['models']:
            if 'error' in result:
                continue
            for name,variant in result['independent']['variants'].items():
                m=variant['metrics'];frozen=variant.get('frozen_development_threshold_metrics')
                acceptance=frozen.get('acceptance') if frozen else None
                false=acceptance['false_positive_count'] if acceptance else 'N/A'
                rejection=acceptance['no_match_rejection'] if acceptance else None
                lines.append(f"| {result['model']} / {name} | {number(m['recall_at_1'])} | {number(m['recall_at_5'])} | {number(m['mrr'])} | {false} | {number(rejection)} |")
    lines.extend(['','## Interpretation and reproducibility','',
        'These recipes are offline. Live cropping, CLIP preprocessing, category routing, and ranking weights are unchanged. Detector-top is deliberately unreviewed and is not the live assisted-selection behavior. Reviewed-detector uses explicit development review records and documented manual fallback.',
        '', 'Thresholds and fusion coefficients are fitted on development only. Their development acceptance metrics, frozen independent results, raw unfiltered embedding rankings, candidate relevance labels and local-feature diagnostics are in the JSON report. No threshold or coefficient is installed in the website.',
        '', 'Missing evidence: same-model different physical items, independent instances, broader categories and independently reviewed labels. Three views of one object are correlated observations. Product lookalikes are different models, not same-model hard negatives.',
        '', f"Manifest fingerprints: development `{report['development_coverage']['manifest_sha256']}`, independent `{report['independent_coverage']['manifest_sha256']}`.",
        '', f"Platform: {report['platform']}; Python {report['python']}; CPU provider, two native inference threads. Timings include region preparation and encoding, exclude upload/decode, and are subject to process/cache warmup. Repeated measurements use identical pixels. Model processes are isolated; cached native inference is bounded separately in the application."])
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--development',default='data/retrieval-development.json')
    parser.add_argument('--independent',default='data/retrieval-independent.json')
    parser.add_argument('--models',nargs='+',choices=['clip','dinov2'],default=['clip'])
    parser.add_argument('--output',default='reports/retrieval-evaluation.json')
    parser.add_argument('--worker',choices=['clip','dinov2'])
    parser.add_argument('--local-evidence',action='store_true')
    args=parser.parse_args()
    dev=load_manifest(args.development);test=load_manifest(args.independent);validate_isolation(dev,test)
    if args.worker:
        print(json.dumps(experiment(args.worker,dev,test,args.local_evidence)))
    else:
        report={'platform':platform.platform(),'python':platform.python_version(),
                'status':'independent_observations_available' if test['queries'] else 'inconclusive_for_generalization','production_ranking_changed':False,
                'development_coverage':coverage(dev),'independent_coverage':coverage(test),'models':[]}
        sources=list(Path('evaluation').glob('*.py'))+[Path('backend')/name for name in ['semantic.py','vision.py','gallery.py','nanodet.py','detection.py','main.py','embedding_cache.py']]
        report['source_sha256']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
        import cv2,numpy,onnxruntime,PIL
        report['libraries']={'opencv':cv2.__version__,'numpy':numpy.__version__,'onnxruntime':onnxruntime.__version__,'pillow':PIL.__version__}
        for model in args.models:
            command=[sys.executable,'-m','evaluation.run','--worker',model,'--development',args.development,'--independent',args.independent]
            if args.local_evidence and model == 'clip':
                command.append('--local-evidence')
            try:
                result=subprocess.run(command,capture_output=True,text=True,timeout=180)
                report['models'].append(json.loads(result.stdout) if result.returncode == 0 else {'model':model,'error':result.stderr[-1800:]})
            except subprocess.TimeoutExpired:
                report['models'].append({'model':model,'error':'Evaluation exceeded 180 seconds.'})
            output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(report,indent=2))
            output.with_suffix('.md').write_text(markdown(report),encoding='utf-8')
            print(model+': '+('failed' if 'error' in report['models'][-1] else 'complete'),flush=True)
        print('Report: '+args.output)
