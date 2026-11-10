import numpy as np
import pytest
from backend.semantic import relevance, ModelUnavailable
from backend.main import search_gallery
from fastapi import UploadFile, HTTPException
from io import BytesIO
import cv2


def desc(label, margin=.1, vector=(1.,0.)):
    return {'label':label,'margin':margin,'vector':np.array(vector)}


def test_confident_chart_is_excluded_even_with_high_visual_alignment():
    result=relevance(desc('earbuds'),desc('chart_or_diagram'))
    assert result['relevance']=='excluded'


def test_ambiguous_category_is_not_silently_discarded():
    assert relevance(desc('earbuds'),desc('phone',margin=.001))['relevance']=='uncertain'


def test_same_category_is_candidate_not_ownership_confirmation():
    result=relevance(desc('earbuds'),desc('earbuds'))
    assert result['relevance']=='relevant'
    assert 'not confirmed' in result['relevance_reason']


def test_missing_model_does_not_fall_back_to_appearance(monkeypatch):
    def unavailable():
        raise ModelUnavailable('Model missing')
    monkeypatch.setattr('backend.main.get_model', unavailable)
    _,raw=cv2.imencode('.png',np.zeros((40,40,3),np.uint8))
    def upload():
        return UploadFile(filename='a.png',file=BytesIO(raw.tobytes()))
    with pytest.raises(HTTPException) as exc:
        search_gallery(upload(),[upload()],'null','[null]')
    assert exc.value.status_code==503

@pytest.mark.skipif(not __import__('pathlib').Path('models/clip/vision_model_quantized.onnx').exists(), reason='Download local model first')
def test_real_user_regression_content_not_filename():
    from pathlib import Path
    from backend.main import compare_uploads
    root=Path(__file__).resolve().parents[1]/'data/samples'
    if not all((root/f).exists() for f in ['case-query.jpg','case-close.jpg','graph-negative.png']):
        pytest.skip('Private regression photos are not in this checkout')
    def file(name, filename):
        return UploadFile(filename=filename,file=BytesIO((root/name).read_bytes()))
    result=search_gallery(file('case-query.jpg','query.jpg'),[
        file('graph-negative.png','earbuds.png'),
        file('case-close.jpg','graph.jpg')], 'null','[null,null]')
    assert [r['index'] for r in result['results']]==[1]
    assert [r['index'] for r in result['excluded']]==[0]
    assert result['excluded'][0]['predicted_category']=='chart_or_diagram'
    pair=compare_uploads(file('case-query.jpg','a.jpg'),file('graph-negative.png','b.png'),'null','null',True)
    assert pair['relevance']=='excluded'
    assert pair['appearance_percent']>85  # Preserve proof that appearance alone failed.

@pytest.mark.skipif(not __import__('pathlib').Path('models/clip/vision_model_quantized.onnx').exists(), reason='Download local model first')
def test_object_crop_ranks_real_case_above_supplied_lookalikes():
    from pathlib import Path
    from backend.gallery import rank_gallery
    from backend.vision import decode_image
    root=Path(__file__).resolve().parents[1]/'data/samples'
    names=['white-case.jpg','silver-oneplus.webp','black-oneplus.webp','case-close.jpg','graph-negative.png']
    if not all((root/n).exists() for n in names+['case-distant.jpg']):
        pytest.skip('Private regression gallery not available')
    read=lambda n:decode_image((root/n).read_bytes())
    # No name-based matching. The correct candidate is the fourth upload.
    rows=rank_gallery(read('case-distant.jpg'),[(i,f'candidate-{i}',read(n),None) for i,n in enumerate(names)], [.26,.40,.60,.59])
    relevant=[r for r in rows if r['relevance']=='relevant']
    assert relevant[0]['index']==3
    assert relevant[0]['rank']==1
    assert next(r for r in rows if r['index']==4)['relevance']=='excluded'
