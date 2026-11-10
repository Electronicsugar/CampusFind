"""Create empty manifests or validate and audit a pair without loading models."""
import argparse
import json
from pathlib import Path
from evaluation.dataset import load_manifest,validate_isolation,audit


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--init',type=Path,help='Create a NEW dataset directory; never overwrites files.')
    parser.add_argument('--development',default='data/retrieval-development.json')
    parser.add_argument('--independent',default='data/retrieval-independent.json')
    parser.add_argument('--schema-version',type=int,choices=[2,3],default=3)
    parser.add_argument('--screen-leakage',action='store_true',help='Screen capture provenance and perceptual near duplicates.')
    args=parser.parse_args()
    if args.init:
        args.init.mkdir(parents=True,exist_ok=False)
        for split in ['development','independent']:
            (args.init/'photos'/split).mkdir(parents=True)
            (args.init/(split+'.json')).write_text(json.dumps({'schema_version':args.schema_version,'split':split,
                'label_provenance':'','images':[],'queries':[]},indent=2),encoding='utf-8')
        print('Empty manifests created. Add real reviewed photos following docs/PHASE6_DATASET.md (schema 3) or docs/PHASE3_DATASET.md (schema 2).')
    else:
        dev=load_manifest(args.development);test=load_manifest(args.independent);validate_isolation(dev,test)
        print(json.dumps({d['split']:audit(d) for d in [dev,test]},indent=2))
        if args.screen_leakage:
            from evaluation.integrity import screen_splits
            print(json.dumps(screen_splits(dev,test),indent=2))
