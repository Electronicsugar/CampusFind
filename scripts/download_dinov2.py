"""Explicit optional 24.5 MB experiment. No imports from the application server."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from urllib.request import urlopen

REVISION='c2bb04a51fab207c420665f1946016107bffc701'
EXPECTED='3afdc8bc63b50558d6e5770f5b799bb82455c2311183a2de43803f343a29d917'
ROOT=Path(__file__).resolve().parents[1]/'models/dinov2-small'


def download():
    ROOT.mkdir(parents=True,exist_ok=True)
    manifest={'repository':'Xenova/dinov2-small','revision':REVISION,'files':{}}
    for remote in ['preprocessor_config.json','onnx/model_quantized.onnx']:
        target=ROOT/Path(remote).name
        if target.exists() and (not remote.endswith('.onnx') or hashlib.sha256(target.read_bytes()).hexdigest() == EXPECTED):
            pass
        else:
            print('Downloading '+remote,flush=True)
            url=f'https://huggingface.co/Xenova/dinov2-small/resolve/{REVISION}/{remote}?download=true'
            temporary=target.with_suffix(target.suffix+'.partial')
            curl=shutil.which('curl.exe')
            if curl:
                subprocess.run([curl,'--fail','--location','--silent','--show-error','--connect-timeout','20','--max-time','120','--output',str(temporary),url],check=True,timeout=130)
            else:
                with urlopen(url,timeout=30) as response,temporary.open('wb') as out:
                    shutil.copyfileobj(response,out)
            if remote.endswith('.onnx') and hashlib.sha256(temporary.read_bytes()).hexdigest() != EXPECTED:
                raise RuntimeError('DINOv2 published SHA-256 mismatch; refusing installation.')
            temporary.replace(target)
        manifest['files'][remote]={'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('DINOv2 ready; weights verified against published SHA-256.',flush=True)


if __name__ == '__main__':
    download()
