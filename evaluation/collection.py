"""Phase VIII collection preflight layered over schema-3 integrity checks."""
import argparse
import json
from pathlib import Path, PureWindowsPath
from evaluation.dataset import load_manifest
from evaluation.integrity import screen_splits, coverage

CAPTURE = ('viewpoint','lighting','background','distance','occlusion')


def validate_collection(development, independent):
    for data in (development,independent):
        if data.get('schema_version')!=3 or not isinstance(data.get('dataset_version'),str) or not data['dataset_version'].strip():
            raise ValueError('Collection requires schema 3 and dataset_version.')
        if not data['images'] or not data['queries']:raise ValueError('Collection is empty: add reviewed photographs and queries.')
        for e in data['images']:
            path=e['path']
            if not isinstance(path,str) or Path(path).is_absolute() or PureWindowsPath(path).drive or '\\' in path or '..' in path.split('/'):
                raise ValueError('Use portable repository-relative image paths without traversal.')
            if any(not isinstance(e.get('capture',{}).get(k),str) or not e['capture'][k].strip() for k in CAPTURE):
                raise ValueError('Missing required capture annotation.')
            if not e.get('selection_confirmed') or type(e['selection_confirmed']) is not bool:
                raise ValueError('Explicit selection_confirmed=true required; manual_box omission means full frame.')
        for q in data['queries']:
            if type(q.get('no_match')) is not bool or q['no_match']!= (not q['positive_ids']):raise ValueError('no_match must agree with the designated gallery and positive_ids.')
            a=data['index'][q['image_id']]
            for cid in q['gallery_ids']:
                b=data['index'][cid]
                if a['product_model_id']==b['product_model_id'] and a['instance_id']!=b['instance_id'] and q['relations'][cid]!='lookalike':
                    raise ValueError('Same-model different-instance negatives must be labeled lookalike.')
    return {'coverage':{d['split']:coverage(d) for d in (development,independent)},'screening':screen_splits(development,independent)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--development',required=True);p.add_argument('--independent',required=True);a=p.parse_args()
    try:result=validate_collection(load_manifest(a.development),load_manifest(a.independent))
    except (ValueError,KeyError,TypeError,OSError) as error:p.exit(2,'Invalid collection: '+str(error)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True));return int(result['screening']['status']!='screen_passed')


if __name__=='__main__':raise SystemExit(main())
