"""Measure cold/warm real search handler and require exact response invariance."""
from io import BytesIO
import json
from pathlib import Path
import statistics
from time import perf_counter
from fastapi import UploadFile
from backend.main import search_gallery
from backend.semantic import get_model


def main():
    model=get_model();model.cache.clear()
    folder=Path('data/samples')
    names=['white-case.jpg','silver-oneplus.webp','black-oneplus.webp','case-close.jpg','graph-negative.png']
    def request():
        def upload(name):
            return UploadFile(filename=name,file=BytesIO((folder/name).read_bytes()))
        started=perf_counter()
        response=search_gallery(upload('case-distant.jpg'),[upload(n) for n in names],'null',json.dumps([None]*len(names)))
        elapsed=(perf_counter()-started)*1000
        response.pop('elapsed_ms')
        return response,elapsed
    reference,cold_ms=request();cold_stats=model.cache.stats()
    times=[]
    for _ in range(3):
        response,elapsed=request()
        if reference != response:
            raise AssertionError('Cache changed a response, score, ordering, error or preview.')
        times.append(elapsed)
    warm_stats=model.cache.stats()
    if warm_stats['inference_calls'] != cold_stats['inference_calls']:
        raise AssertionError('Unchanged inputs triggered additional inference.')
    report={'cold_search_ms':cold_ms,'warm_search_mean_ms':statistics.mean(times),'warm_search_trials_ms':times,
            'cold_cache_stats':cold_stats,'warm_cache_stats':warm_stats,
            'responses_identical_except_elapsed_ms':True,'additional_warm_inference_calls':0,
            'model_loading_excluded':True,'note':'Development timing observation, no accuracy improvement claim. Includes file reads, decoding, preparation, scoring and previews.'}
    output=Path('reports/cache-verification.json');output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
