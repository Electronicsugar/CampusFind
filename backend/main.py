import base64
import json
import logging
from time import perf_counter
from typing import Annotated
from pathlib import Path
import cv2
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from backend.vision import compare, decode_image, MAX_BYTES, prepare
from backend.semantic import get_model, relevance, ModelUnavailable

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title='CampusFind', version='0.4.0')
LOG = logging.getLogger(__name__)

@app.get('/')
def home():
    return FileResponse(ROOT / 'frontend' / 'app.html')

@app.get('/lab')
def comparison_lab():
    return FileResponse(ROOT / 'frontend' / 'index.html')

@app.get('/api/health')
def health():
    return {'status': 'ok', 'stage': 'CLIP gallery with assisted object selection — local research prototype'}


@app.post('/api/suggest-crops')
def suggest_crops(image: UploadFile = File(...), prompt: str = Form(''), model: Annotated[str, Form()] = 'nanodet'):
    from backend.detection import suggest_objects, DEFAULT_PROMPT, DetectorUnavailable, DetectorBusy
    try:
        decoded = decode_image(image.file.read(MAX_BYTES + 1))
        return suggest_objects(decoded, prompt or DEFAULT_PROMPT, model)
    except DetectorUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except DetectorBusy as exc:
        raise HTTPException(429, str(exc)) from exc
    except (ValueError, TypeError, cv2.error) as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post('/api/compare')
def compare_uploads(image_a: UploadFile = File(...), image_b: UploadFile = File(...),
                    box_a: str = Form('null'), box_b: str = Form('null'), normalize: bool = Form(True)):
    try:
        a = decode_image(image_a.file.read(MAX_BYTES + 1))
        b = decode_image(image_b.file.read(MAX_BYTES + 1))
        region_a, region_b = json.loads(box_a), json.loads(box_b)
        crop_a, _ = prepare(a, region_a, normalize=False)
        crop_b, _ = prepare(b, region_b, normalize=False)
        model = get_model()
        result, visual = compare(a, b, region_a, region_b, normalize)
        result.update(relevance(model.describe(crop_a), model.describe(crop_b)))
        ok, encoded = cv2.imencode('.jpg', visual)
        if not ok:
            raise ValueError('Could not create comparison preview.')
        return {**result, 'preview': 'data:image/jpeg;base64,' + base64.b64encode(encoded).decode()}
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, TypeError, cv2.error) as exc:
        raise HTTPException(400, str(exc)) from exc

@app.get('/gallery')
def gallery_page():
    return FileResponse(ROOT / 'frontend' / 'gallery.html')


@app.get('/detection.js')
def detection_script():
    return FileResponse(ROOT / 'frontend' / 'detection.js', media_type='text/javascript')

@app.post('/api/search')
def search_gallery(query: UploadFile = File(...), candidates: list[UploadFile] = File(...),
                   query_box: str = Form('null'), boxes: str = Form('[]')):
    started=perf_counter()
    from backend.gallery import rank_gallery, sort_results
    from backend.vision import prepare
    if not 1 <= len(candidates) <= 12:
        raise HTTPException(400, 'Choose between 1 and 12 candidate photos.')
    try:
        query_region = json.loads(query_box)
        regions = json.loads(boxes)
        if not isinstance(regions, list) or len(regions) != len(candidates):
            raise ValueError('Each candidate needs a corresponding crop entry.')
        reference = decode_image(query.file.read(MAX_BYTES + 1))
        reference_crop, _ = prepare(reference, query_region, normalize=False)
        reference_description = get_model().describe(reference_crop)
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, TypeError, cv2.error) as exc:
        raise HTTPException(400, str(exc)) from exc
    results, errors = [], []
    total_bytes = 0
    # Decode and score one candidate at a time to bound image memory.
    for index, (upload, box) in enumerate(zip(candidates, regions)):
        name = (upload.filename or f'Item {index+1}').replace('\\', '/').split('/')[-1][:160]
        try:
            raw = upload.file.read(MAX_BYTES + 1)
            total_bytes += len(raw)
            if total_bytes > 60 * 1024 * 1024:
                raise HTTPException(413, 'Gallery exceeds 60 MB. Select fewer or smaller photos.')
            image = decode_image(raw)
            results.extend(rank_gallery(reference, [(index, name, image, box)], query_region, reference_description))
        except ModelUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except (ValueError, TypeError, cv2.error) as exc:
            errors.append({'index': index, 'name': name, 'error': str(exc)})
    sort_results(results)
    elapsed_ms=round((perf_counter()-started)*1000,2)
    LOG.info('gallery_search elapsed_ms=%.2f candidates=%d errors=%d',elapsed_ms,len(candidates),len(errors))
    return {'results': [r for r in results if r['relevance'] == 'relevant'],
            'uncertain': [r for r in results if r['relevance'] == 'uncertain'],
            'excluded': [r for r in results if r['relevance'] == 'excluded'],
            'query_category': reference_description['label'], 'elapsed_ms':elapsed_ms,
            'errors': errors, 'method': 'Local CLIP semantic relevance and image embedding ranking; not identity confidence.'}

from backend.platform import install
install(app)
