"""Session gallery ranking. No images are persisted by this experiment."""
import base64
import cv2
from backend.vision import prepare, appearance_similarity
from backend.semantic import get_model, relevance


def score_descriptions(reference,candidate,scores):
    semantic=relevance(reference,candidate)
    if scores['appearance_percent'] is None:
        semantic['relevance']='uncertain'
        semantic['relevance_reason']='Too little visible structure to assess this candidate reliably.'
    return {**scores,**semantic}


def rank_gallery(query, candidates, query_box=None, reference_description=None, semantic_model=None):
    reference, _ = prepare(query, query_box, normalize=False)
    model = semantic_model if semantic_model is not None else get_model()
    reference_description = reference_description or model.describe(reference)
    results = []
    for index, name, image, box in candidates:
        crop, _ = prepare(image, box, normalize=False)
        scores = appearance_similarity(reference, crop)
        semantic = score_descriptions(reference_description, model.describe(crop),scores)
        h, w = crop.shape[:2]
        factor = min(1, 420/max(h, w))
        thumbnail = cv2.resize(crop, (round(w*factor), round(h*factor)))
        ok, encoded = cv2.imencode('.jpg', thumbnail)
        if not ok:
            raise ValueError('Could not create gallery preview.')
        results.append({'index': index, 'name': name, **scores, **semantic,
                        'preview': 'data:image/jpeg;base64,'+base64.b64encode(encoded).decode()})
    sort_results(results)
    return results


def sort_results(results):
    order = {'relevant': 0, 'uncertain': 1, 'excluded': 2}
    results.sort(key=lambda r: (order[r['relevance']], -r['semantic_similarity'], -(r['appearance_percent'] or 0)))
    rank = 0
    for result in results:
        if result['relevance'] == 'relevant':
            rank += 1
            result['rank'] = rank
        else:
            result['rank'] = None
