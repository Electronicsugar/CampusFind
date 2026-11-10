"""Real local CLIP timing on synthetic pixels; never recognition accuracy."""
import json,time,threading
from pathlib import Path
import numpy as np,psutil
from backend.semantic import get_model
from backend.vision import prepare
from scripts.pilot_benchmark import distribution


if __name__=='__main__':
    output=Path('reports/phase5-encoder.json')
    if output.exists():raise SystemExit('Refusing to overwrite results.')
    process=psutil.Process();stop=threading.Event();peak=[process.memory_info().rss]
    def sample():
        while not stop.wait(.05):peak[0]=max(peak[0],process.memory_info().rss)
    sampler=threading.Thread(target=sample,daemon=True);sampler.start();cpu=sum(process.cpu_times()[:2]);start=time.perf_counter()
    try:
        model=get_model();load=time.perf_counter()-start
        images=[prepare(np.random.default_rng(n).integers(0,255,(768,1024,3),dtype=np.uint8),None,normalize=False)[0] for n in range(20)]
        runs=[]
        for _ in range(2):
            timings=[]
            for image in images:
                started=time.perf_counter();model.describe(image);timings.append((time.perf_counter()-started)*1000)
            runs.append(distribution(timings))
        result={'scope':'20 unique synthetic 1024x768 frames, real cached local CLIP, no accuracy labels','model_load_seconds':round(load,3),'cold_encoding':runs[0],'memory_cache_hits':runs[1],'cpu_seconds':round(sum(process.cpu_times()[:2])-cpu,3),'peak_process_rss_mb':round(peak[0]/1024**2,2)}
    finally:stop.set();sampler.join()
    output.write_text(json.dumps(result,indent=2));print(json.dumps(result))
