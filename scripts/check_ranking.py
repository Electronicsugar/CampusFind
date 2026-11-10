from pathlib import Path
from backend.vision import decode_image,prepare
from backend.gallery import rank_gallery
import json
p=Path('data/samples')
read=lambda n: decode_image((p/n).read_bytes())
candidates=[(i,n,read(n),None) for i,n in enumerate(['white-case.jpg','silver-oneplus.webp','black-oneplus.webp','case-close.jpg','graph-negative.png'])]
records=[]
for name,box in [('case-query.jpg',None),('case-distant.jpg',None),('case-distant.jpg',[.26,.40,.60,.59])]:
    rows=rank_gallery(read(name),candidates,box)
    record={'query':name,'crop':box,'results':[{k:v for k,v in r.items() if k not in ['preview','appearance_method']} for r in rows]}
    records.append(record)
    print(json.dumps(record),flush=True)
Path('reports/ranking-regression.json').write_text(json.dumps(records,indent=2))
