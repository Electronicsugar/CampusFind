from io import BytesIO
import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 15 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 24_000_000


def decode_image(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('Image exceeds the 15 MB limit.')
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValueError('Please use a JPEG, PNG, or WebP image.')
            if image.width * image.height > 24_000_000:
                raise ValueError('Image exceeds the 24 megapixel limit.')
            return cv2.cvtColor(np.array(ImageOps.exif_transpose(image).convert('RGB')), cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Please use a valid JPEG, PNG, or WebP image.') from exc


def prepare(image, box=None, normalize=True):
    if box is not None:
        if len(box) != 4 or not all(isinstance(v, (float, int)) and np.isfinite(v) for v in box):
            raise ValueError('Crop requires four finite coordinates.')
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError('Crop must be within the image and have positive size.')
        h, w = image.shape[:2]
        image = image[int(y1*h):int(y2*h), int(x1*w):int(x2*w)]
    h, w = image.shape[:2]
    if min(h, w) < 24:
        raise ValueError('Selected object is too small. Select a larger region or use a closer photo.')
    scale = min(1, 1000/max(h, w))
    image = cv2.resize(image, (round(w*scale), round(h*scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if normalize:
        gray = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8)).apply(gray)
    return image, gray



def appearance_descriptor(image):
    """Coarse appearance only, without correspondence or identity claims.

    HSV hue/saturation avoids comparing raw exposure. Near-gray pixels use one
    achromatic bin, since hue is unstable there. A radial edge-energy profile
    provides a coarse centered shape/texture cue that tolerates image rotation.
    Neither descriptor proves instance identity or solves large viewpoint changes.
    """
    h, w = image.shape[:2]
    scale = min(1.0, 384 / max(h, w))
    small = cv2.resize(image, (round(w*scale), round(h*scale)), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hue, sat = hsv[:, :, 0], hsv[:, :, 1]
    chromatic = sat >= 40
    histogram, _, _ = np.histogram2d(hue[chromatic], sat[chromatic], bins=(12, 4), range=((0, 180), (0, 256)))
    colors = np.append(histogram.ravel(), np.count_nonzero(~chromatic)).astype(float)
    colors /= colors.sum()

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
    low, high = np.percentile(gray, (2, 98))
    if high-low < 5:
        return colors, None
    gray = np.clip((gray-low)/(high-low), 0, 1).astype(np.float32)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    dx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    dy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    energy = cv2.magnitude(dx, dy)
    # Ignore crop-border artifacts.
    energy[:3] = energy[-3:] = 0
    energy[:, :3] = energy[:, -3:] = 0
    hh, ww = gray.shape
    yy, xx = np.mgrid[:hh, :ww]
    radius = np.sqrt(((xx-(ww-1)/2)/(ww/2))**2 + ((yy-(hh-1)/2)/(hh/2))**2)
    shape, _ = np.histogram(radius, bins=12, range=(0, np.sqrt(2)), weights=energy)
    shape = shape.astype(float)
    if shape.sum() <= 1e-8:
        return colors, None
    return colors, shape / shape.sum()


def appearance_similarity(a, b):
    ca, sa = appearance_descriptor(a)
    cb, sb = appearance_descriptor(b)
    return appearance_from_descriptors((ca,sa),(cb,sb))


def appearance_from_descriptors(first,second):
    ca,sa=first;cb,sb=second
    # Bhattacharyya coefficient: overlap of normalized histograms, in [0, 1].
    def overlap(x, y):
        return float(np.clip(np.sqrt(x*y).sum(), 0, 1))
    color = overlap(ca, cb)
    shape = overlap(sa, sb) if sa is not None and sb is not None else None
    # Equal-weight heuristic; deliberately exposed and not calibrated as confidence.
    total = (color + shape)/2 if shape is not None else None
    return {'appearance_percent': round(total*100, 1) if total is not None else None,
            'color_percent': round(color*100, 1),
            'structure_percent': round(shape*100, 1) if shape is not None else None,
            'appearance_method': 'Mean of HSV color overlap and radial edge-profile overlap; experimental, not identity confidence.'}


def compare(a, b, box_a=None, box_b=None, normalize=True):
    a, gray_a = prepare(a, box_a, normalize)
    b, gray_b = prepare(b, box_b, normalize)
    sift = cv2.SIFT_create(nfeatures=2500)
    ka, da = sift.detectAndCompute(gray_a, None)
    kb, db = sift.detectAndCompute(gray_b, None)
    matches = []
    if da is not None and db is not None and min(len(da), len(db)) >= 2:
        matcher = cv2.BFMatcher(cv2.NORM_L2)
        def ratio_pairs(first, second):
            return [pair[0] for pair in matcher.knnMatch(first, second, k=2)
                    if len(pair) == 2 and pair[0].distance < .75 * pair[1].distance]
        forward = ratio_pairs(da, db)
        backward = {(m.trainIdx, m.queryIdx) for m in ratio_pairs(db, da)}
        matches = [m for m in forward if (m.queryIdx, m.trainIdx) in backward]
    inliers = []
    if len(matches) >= 4:
        src = np.float32([ka[m.queryIdx].pt for m in matches])
        dst = np.float32([kb[m.trainIdx].pt for m in matches])
        transform, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
        if transform is not None and mask is not None and np.isfinite(transform).all():
            inliers = [m for m, keep in zip(matches, mask.ravel()) if keep]
    # Diagnostic ranking signal only. Not a probability of identity.
    score = len(inliers) * (len(inliers) / max(len(matches), 1))
    result = {**appearance_similarity(a, b), 'keypoints': [len(ka), len(kb)], 'tentative_matches': len(matches),
              'geometric_inliers': len(inliers), 'ranking_score': round(score, 3),
              'note': 'Local evidence only; repeated branding and background can match. This does not establish ownership.'}
    visual = cv2.drawMatches(a, ka, b, kb, inliers[:60], None,
                            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
    return result, visual
