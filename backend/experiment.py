"""Run: python -m backend.experiment. Outputs are local and excluded from Git."""
import json
from pathlib import Path
import cv2
from backend.vision import decode_image, compare

ROOT = Path(__file__).resolve().parents[1]

def main():
    a = decode_image((ROOT/'data/samples/case-distant.jpg').read_bytes())
    b = decode_image((ROOT/'data/samples/case-close.jpg').read_bytes())
    # Manual normalized regions based on supplied images; not automatic detection.
    boxes = ([.26, .40, .60, .59], [.20, .41, .75, .75])
    records = {}
    for name, crop, normalize in [('full-original', False, False), ('crop-original', True, False), ('crop-normalized', True, True)]:
        result, visual = compare(a, b, *(boxes if crop else (None, None)), normalize=normalize)
        records[name] = result
        cv2.imwrite(str(ROOT/'reports'/f'{name}.jpg'), visual)
    (ROOT/'reports/baseline.json').write_text(json.dumps(records, indent=2))
    print(json.dumps(records, indent=2))

if __name__ == '__main__':
    main()
