"""Local CLIP semantic relevance. No network calls during inference."""
from functools import lru_cache
from pathlib import Path
from threading import Lock
import json
import hashlib
import logging
from time import perf_counter
import numpy as np
from PIL import Image
from backend.embedding_cache import EmbeddingCache, CacheBusy, image_key

MODEL_DIR = Path(__file__).resolve().parents[1] / 'models' / 'clip'
LABELS = {
    'earbuds': ['a photo of wireless earbuds in a charging case', 'a photo of a closed earbud charging case', 'a photo of a small earphone case'],
    'headphones': ['a photo of over-ear headphones', 'a photo of a headset'],
    'bottle': ['a photo of a water bottle', 'a photo of a reusable drinking flask'],
    'phone': ['a photo of a mobile phone', 'a photo of a smartphone'],
    'wallet': ['a photo of a wallet', 'a photo of a coin purse'],
    'bag': ['a photo of a backpack', 'a photo of a handbag'],
    'keys': ['a photo of keys on a keyring', 'a photo of a set of keys'],
    'glasses': ['a photo of eyeglasses', 'a photo of sunglasses in a case'],
    'watch': ['a photo of a wristwatch', 'a photo of a smartwatch'],
    'book': ['a photo of a book', 'a photo of a notebook'],
    'id_card': ['a photo of a student identity card', 'a photo of an ID badge'],
    'charger': ['a photo of a phone charger and cable', 'a photo of a power adapter'],
    'stationery': ['a photo of a pen', 'a photo of a pencil case'],
    'clothing': ['a photo of a jacket', 'a photo of a hat'],
    'umbrella': ['a photo of an umbrella'],
    'other_object': ['a photo of a personal belonging', 'a photo of an everyday physical object'],
    'chart_or_diagram': ['a screenshot of an oscilloscope waveform graph', 'a screenshot of a chart with axes and plotted lines', 'an image of a scientific diagram'],
    'document_or_interface': ['a screenshot of a computer software interface', 'a screenshot of a document with text', 'a screenshot of a spreadsheet'],
    'scene': ['a photo of a landscape', 'a photo of a room without a particular item', 'a photo of a person'],
}
NON_ITEM = {'chart_or_diagram', 'document_or_interface', 'scene'}
# Provisional decision margins, not confidence probabilities. Validate on broader data.
MARGIN = .025
_INIT_LOCK = Lock()
LOG = logging.getLogger(__name__)
PREPROCESSING_VERSION = 'clip-standard-short-edge224-center-bicubic-rgb-v1'

class ModelUnavailable(RuntimeError):
    pass

class SemanticModel:
    def __init__(self):
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
            config = json.loads((MODEL_DIR/'preprocessor_config.json').read_text())
            self.mean = np.array(config['image_mean'], dtype=np.float32)
            self.std = np.array(config['image_std'], dtype=np.float32)
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            self.vision = ort.InferenceSession(str(MODEL_DIR/'vision_model_quantized.onnx'), opts, providers=['CPUExecutionProvider'])
            text = ort.InferenceSession(str(MODEL_DIR/'text_model_quantized.onnx'), opts, providers=['CPUExecutionProvider'])
            tokenizer = Tokenizer.from_file(str(MODEL_DIR/'tokenizer.json'))
            tokenizer.enable_truncation(max_length=77)
            tokenizer.enable_padding(length=77, pad_id=49407, pad_token='<|endoftext|>')
            prompts = [prompt for group in LABELS.values() for prompt in group]
            encoded = tokenizer.encode_batch(prompts)
            inputs = {'input_ids': np.array([e.ids for e in encoded], dtype=np.int64),
                      'attention_mask': np.array([e.attention_mask for e in encoded], dtype=np.int64)}
            output = text.run(None, {i.name: inputs[i.name] for i in text.get_inputs()})[0]
            output = output / np.linalg.norm(output, axis=1, keepdims=True)
            groups, offset = [], 0
            for prompts in LABELS.values():
                vector = output[offset:offset+len(prompts)].mean(axis=0)
                groups.append(vector/np.linalg.norm(vector))
                offset += len(prompts)
            self.text_vectors = np.array(groups)
            self.labels = list(LABELS)
            with (MODEL_DIR/'vision_model_quantized.onnx').open('rb') as weights:
                vision_hash=hashlib.file_digest(weights,'sha256').hexdigest()
            fingerprint=hashlib.sha256(vision_hash.encode())
            fingerprint.update(self.text_vectors.tobytes())
            fingerprint.update(self.mean.tobytes());fingerprint.update(self.std.tobytes())
            fingerprint.update(json.dumps(self.labels).encode())
            self.model_version=fingerprint.hexdigest()
            self.cache=EmbeddingCache(max_entries=256,wait_seconds=10)
        except Exception as exc:
            raise ModelUnavailable('Semantic model unavailable. Run .\\.venv\\Scripts\\python.exe scripts/download_model.py and restart the server. Search will not fall back to the old appearance score.') from exc

    def describe(self, bgr):
        started=perf_counter()
        key=image_key(bgr,self.model_version,PREPROCESSING_VERSION)
        try:
            result=self.cache.get_or_compute(key,lambda:self._describe_uncached(bgr))
        except CacheBusy as exc:
            raise ModelUnavailable(str(exc)) from exc
        except Exception as exc:
            LOG.exception('Local CLIP encoding failed')
            raise ModelUnavailable('Local visual encoding failed. Try again or restart the server; ranking will not fall back to appearance scores.') from exc
        LOG.debug('CLIP describe elapsed_ms=%.2f', (perf_counter()-started)*1000)
        return result

    def _describe_uncached(self, bgr):
        rgb = Image.fromarray(bgr[:, :, ::-1])
        w, h = rgb.size
        scale = 224/min(w,h)
        rgb = rgb.resize((int(w*scale), int(h*scale)), Image.Resampling.BICUBIC)
        left, top = (rgb.width-224)//2, (rgb.height-224)//2
        rgb = rgb.crop((left,top,left+224,top+224))
        pixels = ((np.asarray(rgb,dtype=np.float32)/255-self.mean)/self.std).transpose(2,0,1)[None]
        vector = self.vision.run(None, {'pixel_values': pixels})[0][0]
        norm=np.linalg.norm(vector)
        if not np.isfinite(vector).all() or norm <= 0:
            raise ModelUnavailable('The visual encoder returned an invalid embedding.')
        vector = vector/norm
        scores = self.text_vectors @ vector
        order = np.argsort(scores)[::-1]
        return {'vector': vector, 'label': self.labels[order[0]],
                'margin': float(scores[order[0]]-scores[order[1]]),
                'non_item_margin': float(max(scores[i] for i,label in enumerate(self.labels) if label in NON_ITEM)-max(scores[i] for i,label in enumerate(self.labels) if label not in NON_ITEM)),
                'alternatives': [self.labels[i] for i in order[:3]]}

@lru_cache(maxsize=1)
def _load_model():
    return SemanticModel()

def get_model():
    with _INIT_LOCK:
        return _load_model()

def relevance(reference, candidate):
    similarity = float(np.clip(reference['vector'] @ candidate['vector'], -1, 1))
    q, c = reference['label'], candidate['label']
    confident_q, confident_c = reference['margin'] >= MARGIN, candidate['margin'] >= MARGIN
    if q in NON_ITEM:
        status, reason = 'uncertain', 'Reference may be a scene or screenshot. Select the physical item more tightly.'
    elif c in NON_ITEM and candidate.get('non_item_margin', candidate['margin']) >= MARGIN:
        status, reason = 'excluded', 'Candidate appears to be a '+c.replace('_', ' ')+', rather than the reference item.'
    elif q == c and q != 'other_object':
        status, reason = 'relevant', 'Both crops are predicted to show '+q.replace('_', ' ')+'. Identity is not confirmed.'
    elif q != c and q != 'other_object' and c != 'other_object' and confident_q and confident_c and similarity < .70:
        status, reason = 'excluded', 'Predicted object categories differ: '+q.replace('_', ' ')+' and '+c.replace('_', ' ')+'.'
    else:
        status, reason = 'uncertain', 'Category evidence is ambiguous. Inspect this candidate separately.'
    return {'relevance': status, 'relevance_reason': reason, 'semantic_similarity': round(similarity, 4),
            'predicted_category': c, 'category_margin': round(candidate['margin'], 4)}
