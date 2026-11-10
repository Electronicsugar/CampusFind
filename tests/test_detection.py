from io import BytesIO
import cv2
import numpy as np
import pytest
from fastapi import UploadFile, HTTPException
from backend import detection
from backend.main import suggest_crops


def upload():
    _, encoded = cv2.imencode('.png', np.zeros((100, 200, 3), np.uint8))
    return UploadFile(filename='private.png', file=BytesIO(encoded.tobytes()))


def test_filter_clips_deduplicates_and_rejects_invalid_or_tiny_boxes():
    rows = [
        {'box': [-.1, .1, .6, .9], 'score': .9, 'label': 'case'},
        {'box': [0, .1, .6, .9], 'score': .8, 'label': 'duplicate'},
        {'box': [.7, .2, 1.1, .8], 'score': .7, 'label': 'phone'},
        {'box': [.1, .1, .11, .9], 'score': .95, 'label': 'tiny'},
        {'box': [0, 0, float('nan'), 1], 'score': .99, 'label': 'invalid'},
    ]
    proposals = detection.filter_boxes(rows, 200, 100)
    assert [p['label'] for p in proposals] == ['case', 'phone']
    assert proposals[0]['box'][0] == 0
    assert proposals[1]['box'][2] == 1


def test_suggestions_require_review_and_keep_image_unchanged(monkeypatch):
    class Fake:
        name = 'test-detector'
        def detect(self, image, prompt):
            assert image.shape == (100, 200, 3)
            assert prompt == 'case.'
            return [{'box': [.1, .1, .8, .9], 'label': 'case', 'score': .5}]
    monkeypatch.setattr(detection, 'get_detector', lambda *_: Fake())
    result = suggest_crops(upload(), 'case')
    assert result['requires_confirmation'] is True
    assert len(result['proposals']) == 1
    assert 'selected_box' not in result


def test_empty_detection_is_manual_fallback(monkeypatch):
    class Fake:
        name = 'test'
        def detect(self, *_):
            return []
    monkeypatch.setattr(detection, 'get_detector', lambda *_: Fake())
    result = suggest_crops(upload(), '')
    assert result['proposals'] == []
    assert 'manually' in result['note']


@pytest.mark.parametrize('error,status', [(detection.DetectorUnavailable('missing'),503), (detection.DetectorBusy('busy'),429)])
def test_visible_detector_errors(monkeypatch, error, status):
    def fail(*_):
        raise error
    monkeypatch.setattr(detection, 'suggest_objects', fail)
    with pytest.raises(HTTPException) as exc:
        suggest_crops(upload(), '')
    assert exc.value.status_code == status


def test_invalid_image_rejected_before_detector():
    with pytest.raises(HTTPException) as exc:
        suggest_crops(UploadFile(filename='a.png', file=BytesIO(b'bad')), '')
    assert exc.value.status_code == 400


@pytest.mark.parametrize('prompt', ['', 'x'*241, 'case\nphone'])
def test_prompt_bounds(prompt):
    with pytest.raises(ValueError):
        detection.validate_prompt(prompt)


def test_busy_guard_released_after_inference_error(monkeypatch):
    def fail(*_):
        raise detection.DetectorUnavailable('missing')
    monkeypatch.setattr(detection, 'get_detector', fail)
    for _ in range(2):
        with pytest.raises(detection.DetectorUnavailable):
            detection.suggest_objects(np.zeros((100,100,3), np.uint8), 'case')


def test_non_square_original_coordinate_mapping_and_rgb_preprocessing():
    from types import SimpleNamespace
    detector = detection.GroundingDetector.__new__(detection.GroundingDetector)
    detector.mean = np.zeros(3,np.float32)
    detector.std = np.ones(3,np.float32)
    detector.short_edge = 800
    detector.long_edge = 1333
    detector.fixed_size = {'width':800,'height':800}
    class Tokenizer:
        def encode(self, _):
            return SimpleNamespace(ids=[101,300,1012,102], attention_mask=[1]*4,type_ids=[0]*4)
        def decode(self, _):
            return 'case'
    class Session:
        def get_inputs(self):
            return [SimpleNamespace(name=n) for n in ['pixel_values','input_ids','attention_mask']]
        def get_outputs(self):
            return [SimpleNamespace(name=n) for n in ['logits','pred_boxes']]
        def run(self, _, inputs):
            assert inputs['pixel_values'].shape == (1,3,800,800)
            assert inputs['pixel_values'][0,0,0,0] == 1  # BGR red becomes RGB red.
            return [np.array([[[-20,2,-20,-20]]]),np.array([[[.5,.5,.5,.4]]])]
    detector.tokenizer=Tokenizer();detector.session=Session()
    image=np.zeros((100,200,3),np.uint8);image[:,:,2]=255
    proposal=detector.detect(image,'case')[0]
    assert proposal['box'] == pytest.approx([.25,.3,.75,.7])
    from backend.vision import prepare
    crop,_=prepare(image,proposal['box'],normalize=False)
    assert crop.shape[:2] == (40,100)


def test_multipart_detection_endpoint(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    monkeypatch.setattr(detection,'suggest_objects',lambda image,prompt,model:{'proposals':[], 'requires_confirmation':True,'note':'manual'})
    file=upload()
    with TestClient(app) as client:
        response=client.post('/api/suggest-crops',files={'image':('a.png',file.file.read(),'image/png')},data={'prompt':'case'})
    assert response.status_code == 200
    assert response.json()['requires_confirmation'] is True


def test_simultaneous_detector_request_is_rejected():
    assert detection._RUN_LOCK.acquire(blocking=False)
    try:
        with pytest.raises(detection.DetectorBusy):
            detection.suggest_objects(np.zeros((100,100,3),np.uint8),'case')
    finally:
        detection._RUN_LOCK.release()


def test_unsupported_format_is_rejected_even_with_png_filename():
    from PIL import Image
    raw=BytesIO();Image.new('RGB',(100,100)).save(raw,format='BMP')
    with pytest.raises(HTTPException) as exc:
        suggest_crops(UploadFile(filename='fake.png',file=BytesIO(raw.getvalue())),'case','nanodet')
    assert exc.value.status_code == 400


def test_exif_orientation_uses_the_same_original_coordinate_space():
    from PIL import Image
    from backend.vision import decode_image, prepare
    original=Image.new('RGB',(80,160),'red')
    exif=Image.Exif();exif[274]=6
    raw=BytesIO();original.save(raw,format='JPEG',exif=exif)
    oriented=decode_image(raw.getvalue())
    assert oriented.shape[:2] == (80,160)
    crop,_=prepare(oriented,[.25,0,.75,1],normalize=False)
    assert crop.shape[:2] == (80,80)


def test_invalid_detector_name_is_not_a_file_path():
    with pytest.raises(HTTPException) as exc:
        suggest_crops(upload(),'case','../../unknown')
    assert exc.value.status_code == 400
