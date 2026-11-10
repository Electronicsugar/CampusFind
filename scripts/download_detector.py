"""Explicit, pinned downloads only. Never called during image inference."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1] / 'models'
GD_REV = 'ff690b0a8050566c290287545bd059350f3e9096'
ZOO_REV = '48b10fa505aeb51fbd127fc60a5c660040e823b7'


def download(kind, metadata_only=False):
    if kind == 'grounding-dino':
        base = f'https://huggingface.co/onnx-community/grounding-dino-tiny-ONNX/resolve/{GD_REV}/'
        files = ['tokenizer.json', 'preprocessor_config.json', 'onnx/model_quantized.onnx']
        revision = GD_REV
    else:
        base = f'https://media.githubusercontent.com/media/opencv/opencv_zoo/{ZOO_REV}/models/object_detection_nanodet/'
        files = ['object_detection_nanodet_2022nov.onnx']
        revision = ZOO_REV
    folder = ROOT / kind
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'revision': revision, 'files': {}}
    if manifest['revision'] != revision:
        raise RuntimeError('Model revision changed; use a fresh model folder.')
    for remote in files:
        if metadata_only and remote.endswith('.onnx'):
            continue
        target = folder / Path(remote).name
        record = manifest['files'].get(remote)
        if target.exists() and record and hashlib.sha256(target.read_bytes()).hexdigest() == record['sha256']:
            continue
        print(f'Downloading {kind}: {remote}', flush=True)
        temporary = target.with_suffix(target.suffix + '.partial')
        digest = hashlib.sha256()
        # curl uses the Windows TLS/network stack and avoids observed urllib
        # streaming stalls for the large CDN object. Other systems can use urllib.
        curl = shutil.which('curl.exe')
        if curl:
            subprocess.run([curl, '--fail', '--location', '--silent', '--show-error',
                            '--connect-timeout', '20', '--max-time', '600', '--retry', '2',
                            '--continue-at', '-',
                            '--output', str(temporary), base+remote+'?download=true'], check=True, timeout=1850)
            with temporary.open('rb') as downloaded:
                while chunk := downloaded.read(1024 * 1024):
                    digest.update(chunk)
        else:
            with urlopen(base + remote, timeout=60) as response, temporary.open('wb') as out:
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    out.write(chunk)
        # Published LFS digest for this pinned Grounding DINO export.
        if remote.endswith('model_quantized.onnx') and digest.hexdigest() != '70bf2d3310d1ae73769c96a71e00cbf2861eb33a1f4d97d84a108a7bf02c03c9':
            raise RuntimeError('Detector download failed SHA-256 verification.')
        temporary.replace(target)
        manifest['files'][remote] = {'sha256': digest.hexdigest(), 'bytes': target.stat().st_size}
        manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f'Ready: {folder}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['grounding-dino', 'nanodet', 'all'], default='grounding-dino')
    parser.add_argument('--metadata-only', action='store_true')
    args = parser.parse_args()
    for kind in (['grounding-dino', 'nanodet'] if args.model == 'all' else [args.model]):
        download(kind, args.metadata_only)
