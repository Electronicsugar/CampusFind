"""Interchangeable offline encoders. Model loading never initiates downloads."""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from backend.semantic import get_model, ModelUnavailable
from backend.embedding_cache import EmbeddingCache, image_key

ROOT=Path(__file__).resolve().parents[1]


class ClipEncoder:
    name='clip'
    semantic_routing=True
    def __init__(self):
        self.model=get_model()
        self.mean=self.model.mean
        self.version=self.model.model_version
    def describe(self,image):
        return self.model.describe(image)
    def clear_cache(self):
        if hasattr(self.model,'cache'):
            self.model.cache.clear()


class DinoEncoder:
    name='dinov2-small-int8'
    semantic_routing=False
    def __init__(self):
        import onnxruntime as ort
        folder=ROOT/'models/dinov2-small'
        try:
            config=json.loads((folder/'preprocessor_config.json').read_text())
            self.mean=np.array(config['image_mean'],np.float32)
            self.std=np.array(config['image_std'],np.float32)
            self.short_edge=config['size']['shortest_edge']
            crop=config['crop_size'];self.crop=(crop['width'],crop['height'])
            options=ort.SessionOptions();options.intra_op_num_threads=2;options.log_severity_level=3
            self.session=ort.InferenceSession(str(folder/'model_quantized.onnx'),options,providers=['CPUExecutionProvider'])
            with (folder/'model_quantized.onnx').open('rb') as weights:
                weight_hash=hashlib.file_digest(weights,'sha256').hexdigest()
            self.version=hashlib.sha256(weight_hash.encode()+(folder/'preprocessor_config.json').read_bytes()).hexdigest()
            self.cache=EmbeddingCache(max_entries=256)
        except Exception as exc:
            raise ModelUnavailable('Optional DINOv2 files missing or invalid; run scripts/download_dinov2.py explicitly.') from exc
    def describe(self,image):
        return self.cache.get_or_compute(image_key(image,self.version,'dino-bicubic256-center224-cls-v1'),lambda:self._describe_uncached(image))
    def _describe_uncached(self,image):
        rgb=Image.fromarray(image[:,:,::-1]);w,h=rgb.size
        scale=self.short_edge/min(w,h)
        rgb=rgb.resize((int(w*scale),int(h*scale)),Image.Resampling.BICUBIC)
        cw,ch=self.crop;left=(rgb.width-cw)//2;top=(rgb.height-ch)//2
        rgb=rgb.crop((left,top,left+cw,top+ch))
        pixels=((np.asarray(rgb,np.float32)/255-self.mean)/self.std).transpose(2,0,1)[None]
        outputs=dict(zip((i.name for i in self.session.get_outputs()),self.session.run(None,{'pixel_values':pixels})))
        if 'last_hidden_state' not in outputs:
            raise ModelUnavailable('DINOv2 export lacks last_hidden_state; refusing an unknown pooling convention.')
        # DINOv2's class token is the documented global retrieval descriptor.
        vector=outputs['last_hidden_state'][0,0].astype(np.float32)
        norm=np.linalg.norm(vector)
        if not np.isfinite(vector).all() or norm <= 0:
            raise ModelUnavailable('DINOv2 returned an invalid descriptor.')
        return {'vector':vector/norm}
    def clear_cache(self):
        self.cache.clear()
