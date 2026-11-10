from io import BytesIO
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.vision import compare, decode_image, prepare


def textured():
    image = np.full((360, 480, 3), 230, np.uint8)
    rng = np.random.default_rng(7)
    for _ in range(90):
        p = tuple(int(v) for v in rng.integers([25, 25], [450, 330]))
        cv2.circle(image, p, int(rng.integers(3, 11)), tuple(int(v) for v in rng.integers(0, 180, 3)), -1)
    cv2.putText(image, 'REUNITE 123', (40, 180), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    return image


def test_rotation_scale_brightness():
    a = textured()
    matrix = cv2.getRotationMatrix2D((240, 180), 23, .8)
    b = cv2.warpAffine(a, matrix, (480, 360), borderValue=(230, 230, 230))
    b = (b * .55).astype(np.uint8)
    result, _ = compare(a, b)
    assert result['geometric_inliers'] >= 12


def test_blank_is_inconclusive():
    image = np.full((100, 100, 3), 120, np.uint8)
    result, _ = compare(image, image)
    assert result['geometric_inliers'] == 0

@pytest.mark.parametrize('box', [[0,0,0,1],[-1,0,1,1],[0,0,float('nan'),1],[0,0,2,1]])
def test_invalid_crop(box):
    with pytest.raises(ValueError):
        prepare(textured(), box)


def test_invalid_upload():
    with pytest.raises(ValueError):
        decode_image(b'not an image')
    client = TestClient(app)
    response = client.post('/api/compare', files={'image_a':('a.jpg',b'bad'), 'image_b':('b.jpg',b'bad')})
    assert response.status_code == 400


def test_api_comparison():
    client = TestClient(app)
    _, raw = cv2.imencode('.png', textured())
    response = client.post('/api/compare', files={'image_a':('a.png',raw.tobytes()), 'image_b':('b.png',raw.tobytes())})
    assert response.status_code == 200
    assert response.json()['geometric_inliers'] > 10
    assert response.json()['preview'].startswith('data:image/jpeg;base64,')

def test_appearance_identical_and_brightness():
    from backend.vision import appearance_similarity
    a = textured()
    same = appearance_similarity(a, a)
    assert same['appearance_percent'] == 100.0
    changed = appearance_similarity(a, (a*.55).astype(np.uint8))
    assert changed['appearance_percent'] > 85
    assert appearance_similarity((a*.55).astype(np.uint8), a) == changed


def test_appearance_distinguishes_color_and_handles_blank():
    from backend.vision import appearance_similarity
    a = textured()
    b = a.copy()
    # Strongly red and blue versions of the same structure should differ in color.
    a[:, :, 0] = 0
    b[:, :, 2] = 0
    different = appearance_similarity(a, b)
    assert different['color_percent'] < 50
    assert different['appearance_percent'] < 80
    blank = np.full((100,100,3), 100, np.uint8)
    result = appearance_similarity(blank, blank)
    assert result['appearance_percent'] is None
    assert result['structure_percent'] is None
    assert result['color_percent'] == 100
