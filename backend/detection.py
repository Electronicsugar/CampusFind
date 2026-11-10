"""Local assisted detection. Boxes are proposals, never accepted selections."""
from functools import lru_cache
from pathlib import Path
from threading import Lock
import json
import logging
from time import perf_counter

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / 'models'
LOG = logging.getLogger(__name__)
DEFAULT_PROMPT = 'earbud charging case. water bottle. phone. wallet. backpack. keys. glasses. watch. book. charger. umbrella.'
_LOAD_LOCK = Lock()
_RUN_LOCK = Lock()


class DetectorUnavailable(RuntimeError):
    pass


class DetectorBusy(RuntimeError):
    pass


def iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    area = lambda x: max(0, x[2]-x[0]) * max(0, x[3]-x[1])
    return intersection / max(area(a)+area(b)-intersection, 1e-12)


def filter_boxes(rows, width, height, threshold=.25, limit=12):
    """Clip normalized boxes and suppress duplicates without choosing an object."""
    valid = []
    for row in sorted(rows, key=lambda r: -r['score']):
        box = np.asarray(row['box'], dtype=float)
        if box.shape != (4,) or not np.isfinite(box).all() or not np.isfinite(row['score']):
            continue
        box = np.clip(box, 0, 1).tolist()
        if row['score'] < threshold or (box[2]-box[0])*width < 24 or (box[3]-box[1])*height < 24:
            continue
        if any(iou(box, previous['box']) > .6 for previous in valid):
            continue
        valid.append({'box': box, 'label': row['label'][:120], 'score': round(float(row['score']), 4)})
        if len(valid) == limit:
            break
    return valid


def validate_prompt(prompt):
    prompt = prompt.strip().lower()
    if not prompt or len(prompt) > 240 or any(ord(c) < 32 for c in prompt):
        raise ValueError('Describe the object in 1–240 characters, without control characters.')
    return prompt if prompt.endswith('.') else prompt + '.'


class GroundingDetector:
    name = 'grounding-dino'

    def __init__(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        folder = ROOT / self.name
        try:
            config = json.loads((folder / 'preprocessor_config.json').read_text())
            self.mean = np.array(config['image_mean'], dtype=np.float32)
            self.std = np.array(config['image_std'], dtype=np.float32)
            self.short_edge = config.get('size', {}).get('shortest_edge', 800)
            self.long_edge = config.get('size', {}).get('longest_edge', 1333)
            self.fixed_size = config.get('size', {})
            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.log_severity_level = 3
            self.session = ort.InferenceSession(str(folder / 'model_quantized.onnx'), options, providers=['CPUExecutionProvider'])
            self.tokenizer = Tokenizer.from_file(str(folder / 'tokenizer.json'))
            self.tokenizer.enable_truncation(max_length=256)
        except Exception as exc:
            raise DetectorUnavailable('Local detector unavailable. Run scripts/download_detector.py --model grounding-dino, then restart. Manual cropping is available.') from exc

    def detect(self, image, prompt=DEFAULT_PROMPT):
        prompt = validate_prompt(prompt)
        height, width = image.shape[:2]
        scale = min(self.short_edge / min(height, width), self.long_edge / max(height, width))
        # This export specifies width/height; other exports may use edge limits.
        size = (self.fixed_size['width'], self.fixed_size['height']) if 'width' in self.fixed_size else (int(width*scale), int(height*scale))
        rgb = Image.fromarray(image[:, :, ::-1]).resize(size, Image.Resampling.BILINEAR)
        pixels = ((np.asarray(rgb, dtype=np.float32)/255-self.mean)/self.std).transpose(2, 0, 1)[None]
        encoded = self.tokenizer.encode(prompt)
        inputs = {'pixel_values': pixels,
                  'pixel_mask': np.ones((1, rgb.height, rgb.width), dtype=np.int64),
                  'input_ids': np.array([encoded.ids], dtype=np.int64),
                  'attention_mask': np.array([encoded.attention_mask], dtype=np.int64),
                  'token_type_ids': np.array([encoded.type_ids], dtype=np.int64)}
        output = self.session.run(None, {item.name: inputs[item.name] for item in self.session.get_inputs()})
        values = dict(zip((item.name for item in self.session.get_outputs()), output))
        logits, boxes = values['logits'][0], values['pred_boxes'][0]
        probabilities = 1 / (1 + np.exp(-np.clip(logits, -80, 80)))
        rows = []
        for probability, (cx, cy, w, h) in zip(probabilities, boxes):
            score = float(probability.max())
            if score < .25:
                continue
            ids = [token for index, token in enumerate(encoded.ids) if index < len(probability) and probability[index] > .25 and token not in (0, 101, 102, 1012)]
            rows.append({'box': [float(cx-w/2), float(cy-h/2), float(cx+w/2), float(cy+h/2)],
                         'score': score, 'label': self.tokenizer.decode(ids) or 'object'})
        return filter_boxes(rows, width, height)


@lru_cache(maxsize=2)
def _load_detector(kind):
    if kind == 'nanodet':
        from backend.nanodet import NanoDetector
        try:
            return NanoDetector()
        except Exception as exc:
            raise DetectorUnavailable('NanoDet unavailable. Run scripts/download_detector.py --model nanodet. Manual cropping is available.') from exc
    return GroundingDetector()


def get_detector(kind='grounding-dino'):
    if kind not in {'grounding-dino', 'nanodet'}:
        raise ValueError('Choose grounding-dino or nanodet.')
    with _LOAD_LOCK:
        return _load_detector(kind)


def suggest_objects(image, prompt=DEFAULT_PROMPT, model='nanodet'):
    prompt = validate_prompt(prompt)
    if not _RUN_LOCK.acquire(blocking=False):
        raise DetectorBusy('Another photo is being analyzed. Try again shortly, or crop manually.')
    started = perf_counter()
    try:
        detector = get_detector(model)
        try:
            proposals = detector.detect(image, prompt)
        except (ValueError, DetectorUnavailable):
            raise
        except Exception as exc:
            LOG.exception('Object detector inference failed')
            raise DetectorUnavailable('Object detection failed locally. Try again or draw a crop manually.') from exc
        elapsed = round((perf_counter()-started)*1000, 1)
        LOG.info('object_suggestions model=%s count=%d elapsed_ms=%.1f', detector.name, len(proposals), elapsed)
        return {'model': detector.name, 'proposals': proposals, 'elapsed_ms': elapsed,
                'requires_confirmation': True,
                'note': ('NanoDet suggests regions from fixed categories; labels may be wrong and the object description is not used. Review every box. ' if model == 'nanodet' else '') + ('Choose and review a box before accepting it. No crop was applied.' if proposals else 'No usable object box found. Try another detector or draw a crop manually.')}
    finally:
        _RUN_LOCK.release()
