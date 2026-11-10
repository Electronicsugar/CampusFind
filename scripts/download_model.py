"""Download pinned CLIP ONNX weights; no user images are transmitted."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1] / 'models' / 'clip'
ROOT.mkdir(parents=True, exist_ok=True)
REPO = 'Xenova/clip-vit-base-patch32'
manifest_path = ROOT / 'manifest.json'
manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
if not manifest:
    revision = 'd15189d7028b43f1d3e65039190477f6af591c2a'
    manifest = {'repository': REPO, 'revision': revision, 'files': {}}
    manifest_path.write_text(json.dumps(manifest, indent=2))
for name in ['onnx/vision_model_quantized.onnx', 'onnx/text_model_quantized.onnx', 'tokenizer.json', 'preprocessor_config.json']:
    target = ROOT / Path(name).name
    if target.exists() and name in manifest['files'] and hashlib.sha256(target.read_bytes()).hexdigest() == manifest['files'][name]['sha256']:
        continue
    print('Downloading ' + name, flush=True)
    temporary = target.with_suffix(target.suffix + '.partial')
    with urlopen(f'https://huggingface.co/{REPO}/resolve/{manifest["revision"]}/{name}', timeout=120) as response, temporary.open('wb') as out:
        while chunk := response.read(1024*1024):
            out.write(chunk)
    temporary.replace(target)
    manifest['files'][name] = {'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'bytes': target.stat().st_size}
    manifest_path.write_text(json.dumps(manifest, indent=2))
print('Model files ready at ' + str(ROOT), flush=True)
