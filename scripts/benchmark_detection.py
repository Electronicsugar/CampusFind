"""Compare local detectors on the same manifest. Optional labeled-box evaluation.

No downloads, no fabricated accuracy from unannotated images. Each detector runs
in a fresh process so peak working set isn't contaminated by the other model.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter

from backend.detection import GroundingDetector, DEFAULT_PROMPT, iou
from backend.nanodet import NanoDetector
from backend.vision import decode_image


def peak_memory_mb():
    if os.name == 'nt':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)] + [(name,ctypes.c_size_t) for name in ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage']]
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        psapi = ctypes.WinDLL('psapi',use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        counts = Counters(); counts.cb = ctypes.sizeof(counts)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counts),counts.cb):
            return None
        return counts.PeakWorkingSetSize / 1024**2
    import resource
    factor = 1024**2 if sys.platform == 'darwin' else 1024
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / factor


def run(kind, manifest, repeats):
    started = perf_counter()
    detector = GroundingDetector() if kind == 'grounding-dino' else NanoDetector()
    load_ms = (perf_counter()-started)*1000
    rows, timings = [], []
    positives = successes = negatives = false_proposals = 0
    for entry in manifest['images']:
        image = decode_image(Path(entry['path']).read_bytes())
        prompt = entry.get('prompt', DEFAULT_PROMPT)
        start = perf_counter(); detector.detect(image,prompt)
        warmup_ms = (perf_counter()-start)*1000
        times = []
        for _ in range(repeats):
            start = perf_counter(); proposals = detector.detect(image,prompt)
            times.append((perf_counter()-start)*1000)
        timings.extend(times)
        row = {'id':entry['id'],'mean_ms':statistics.mean(times),'warmup_ms':warmup_ms,'proposals':proposals}
        if 'boxes' in entry:
            expected = entry['boxes']
            if expected:
                # Success: every annotated object has at least one proposal at IoU >= .5.
                positives += 1
                overlaps = [max((iou(box,p['box']) for p in proposals), default=0) for box in expected]
                row['best_ious'] = overlaps
                row['all_objects_found'] = min(overlaps) >= .5
                successes += int(row['all_objects_found'])
            else:
                negatives += 1
                false_proposals += int(bool(proposals))
        rows.append(row)
    return {'model':kind,'load_ms':load_ms,'mean_inference_ms':statistics.mean(timings) if timings else None,
            'peak_process_memory_mb':peak_memory_mb(),'labeled_positive_images':positives,
            'detection_success_rate_iou50':successes/positives if positives else None,
            'labeled_negative_images':negatives,'negative_image_proposal_rate':false_proposals/negatives if negatives else None,
            'images':rows}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',default='data/detection-manifest.json')
    parser.add_argument('--output',default='reports/detection-benchmark.json')
    parser.add_argument('--models',nargs='+',default=['nanodet','grounding-dino'])
    parser.add_argument('--repeats',type=int,default=2)
    parser.add_argument('--worker',choices=['nanodet','grounding-dino'])
    args=parser.parse_args()
    if args.repeats < 1:
        parser.error('repeats must be positive')
    if args.worker:
        print(json.dumps(run(args.worker,json.loads(Path(args.manifest).read_text()),args.repeats)))
    else:
        report={'platform':platform.platform(),'processor':platform.processor(),'python':platform.python_version(),
                'provider':'CPUExecutionProvider','threads':2,'manifest':args.manifest,'repeats':args.repeats,
                'note':'Development smoke set. Null metrics mean no labels. Not a held-out accuracy comparison.', 'results':[]}
        for kind in args.models:
            command=[sys.executable,'-m','scripts.benchmark_detection','--worker',kind,'--manifest',args.manifest,'--repeats',str(args.repeats)]
            try:
                result=subprocess.run(command,capture_output=True,text=True,timeout=240)
                report['results'].append(json.loads(result.stdout) if result.returncode == 0 else {'model':kind,'error':result.stderr[-3000:]})
            except subprocess.TimeoutExpired:
                report['results'].append({'model':kind,'error':'Benchmark exceeded 240 seconds.'})
            Path(args.output).parent.mkdir(parents=True,exist_ok=True)
            Path(args.output).write_text(json.dumps(report,indent=2))
            print(kind + ': ' + ('failed' if 'error' in report['results'][-1] else 'complete'),flush=True)
        print('Report: '+args.output)
