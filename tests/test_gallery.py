from io import BytesIO
import cv2
import numpy as np
import pytest
from fastapi import UploadFile, HTTPException
from backend.gallery import rank_gallery
from backend.main import search_gallery



@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    # Deterministic fixture for ranking/API mechanics, not semantic accuracy.
    class FakeModel:
        def describe(self, image):
            vector = image.mean(axis=(0,1)).astype(float)
            vector /= np.linalg.norm(vector)
            return {'vector': vector, 'label': 'earbuds', 'margin': .1}
    monkeypatch.setattr('backend.gallery.get_model', lambda: FakeModel())
    monkeypatch.setattr('backend.main.get_model', lambda: FakeModel())


def picture(color=(40, 140, 220)):
    image = np.full((180, 240, 3), color, np.uint8)
    cv2.rectangle(image, (30, 30), (160, 140), (15, 15, 15), 4)
    cv2.putText(image, 'A37', (45, 105), cv2.FONT_HERSHEY_SIMPLEX, 1, (250,250,250), 2)
    return image


def upload(image, name='image.png'):
    _, raw = cv2.imencode('.png', image)
    return UploadFile(filename=name, file=BytesIO(raw.tobytes()))


def test_correct_candidate_ranks_first_and_retains_others():
    a = picture()
    different = picture((220, 140, 40))
    blank = np.full_like(a, 100)
    rows = rank_gallery(a, [(0,'different',different,None),(1,'same',a,None),(2,'blank',blank,None)])
    assert [r['name'] for r in rows] == ['same','different','blank']
    assert rows[0]['appearance_percent'] == 100
    assert rows[-1]['rank'] is None
    assert len(rows) == 3


def test_ties_preserve_input_order():
    a=picture()
    rows=rank_gallery(a,[(0,'first',a,None),(1,'second',a,None)])
    assert [r['index'] for r in rows] == [0,1]


def test_handler_reports_bad_candidate_without_losing_good_one():
    result=search_gallery(upload(picture()),[UploadFile(filename='bad.jpg',file=BytesIO(b'bad')),upload(picture(),'good.png')],'null','[null,null]')
    assert len(result['errors']) == 1
    assert result['results'][0]['index'] == 1
    assert result['results'][0]['rank'] == 1
    assert result['results'][0]['preview'].startswith('data:image/jpeg;base64,')


def test_malformed_crop_list_rejected():
    with pytest.raises(HTTPException) as error:
        search_gallery(upload(picture()),[upload(picture())],'null','[]')
    assert error.value.status_code == 400


def test_gallery_count_limit():
    with pytest.raises(HTTPException) as error:
        search_gallery(upload(picture()),[],'null','[]')
    assert error.value.status_code == 400


def test_invalid_crop_is_reported_per_candidate():
    result=search_gallery(upload(picture()),[upload(picture())],'null','[[0,0,0,1]]')
    assert not result['results']
    assert len(result['errors']) == 1
