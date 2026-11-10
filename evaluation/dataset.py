"""Validate labels, split isolation, and content duplicates before evaluation."""
import hashlib
import json
from pathlib import Path
from backend.vision import decode_image


def load_manifest(path):
    path=Path(path)
    manifest=json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('split') not in {'development','independent'}:
        raise ValueError('Manifest split must be development or independent.')
    images=manifest.get('images',[]); queries=manifest.get('queries',[])
    ids=[i['id'] for i in images]
    if len(set(ids)) != len(ids):
        raise ValueError('Image IDs must be unique.')
    index={i['id']:dict(i) for i in images}
    hashes={};pixels=set()
    for image in index.values():
        # Paths are repository-root relative, as documented in all local scripts.
        source=Path(image['path'])
        if not source.is_file():
            raise ValueError(f"Dataset image missing: {source}")
        raw=source.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        decoded=decode_image(raw)
        pixel_digest=hashlib.sha256(str(decoded.shape).encode()+decoded.tobytes()).hexdigest()
        if digest in hashes:
            raise ValueError('Duplicate image content within a split; use one image ID per file content.')
        if pixel_digest in pixels:
            raise ValueError('Duplicate decoded image content within a split.')
        hashes[digest]=image['id'];pixels.add(pixel_digest);image['sha256']=digest
    seen=set();pair_labels={}
    for query in queries:
        if query['id'] in seen:
            raise ValueError('Query IDs must be unique.')
        seen.add(query['id'])
        gallery=query['gallery_ids']; positives=query['positive_ids']
        if query['image_id'] not in index or any(i not in index for i in gallery):
            raise ValueError('Query/gallery references an unknown image.')
        if query['image_id'] in gallery or len(set(gallery)) != len(gallery):
            raise ValueError('Query image cannot be in its own gallery; candidates must be unique.')
        if not set(positives) <= set(gallery) or len(set(positives)) != len(positives):
            raise ValueError('Positive IDs must be unique gallery IDs.')
        relations=query.get('relations',{})
        if set(relations) != set(gallery) or any(r not in {'same_instance','lookalike','unrelated'} for r in relations.values()):
            raise ValueError('Every query-candidate pair needs an explicit relation label.')
        if {i for i,r in relations.items() if r == 'same_instance'} != set(positives):
            raise ValueError('Same-instance labels must agree with positive IDs.')
        instance=index[query['image_id']].get('instance_id')
        for candidate,relation in relations.items():
            pair=tuple(sorted((query['image_id'],candidate)))
            if pair in pair_labels and pair_labels[pair]!=relation:
                raise ValueError('Conflicting relation labels for the same photograph pair.')
            pair_labels[pair]=relation
            other=index[candidate].get('instance_id')
            if relation == 'same_instance' and (not instance or instance != other):
                raise ValueError('Same-instance positives require consistent explicit physical-instance IDs.')
            if relation != 'same_instance' and instance and instance == other:
                raise ValueError('Negative relation conflicts with physical-instance ID.')
    validate_extended(manifest,index)
    return {**manifest,'index':index,'content_hashes':set(hashes),'pixel_hashes':pixels,'manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def validate_extended(manifest,index):
    """Optional v2 annotations; legacy manifests retain their original meaning."""
    if manifest.get('schema_version',1) not in (1,2,3):
        raise ValueError('Unsupported dataset schema version.')
    for image in index.values():
        if manifest.get('schema_version') in (2,3):
            if not image.get('instance_id') or not image.get('label_provenance'):
                raise ValueError('Version 2 photos need physical instance ID and label provenance.')
            if not isinstance(image.get('capture',{}),dict):
                raise ValueError('Capture conditions must be an object.')
        metadata=image.get('metadata',{})
        if not isinstance(metadata,dict) or any(k not in {'category','brand','color','location','product_model'} or (v is not None and not isinstance(v,str)) for k,v in metadata.items()):
            raise ValueError('Metadata must contain supported text fields or null.')
    for query in manifest['queries']:
        query_views=query.get('view_ids',[query['image_id']])
        groups=query.get('candidate_views',{})
        if not isinstance(groups,dict) or not set(groups) <= set(query['gallery_ids']):
            raise ValueError('Candidate view groups must refer to gallery representatives.')
        used=set()
        for representative,views in [(query['image_id'],query_views)]+[(i,groups.get(i,[i])) for i in query['gallery_ids']]:
            if not isinstance(views,list) or not 1 <= len(views) <= 8 or representative not in views or len(set(views)) != len(views) or any(i not in index for i in views):
                raise ValueError('View groups need 1–8 unique known images including their representative.')
            if used & set(views):
                raise ValueError('Query and candidate view groups must not share photographs.')
            used.update(views)
            if len(views)>1:
                identity=index[representative].get('instance_id')
                if not identity or any(index[i].get('instance_id') != identity for i in views):
                    raise ValueError('View groups require consistent physical-instance labels.')
        if len({index[i].get('instance_id') for i in query['gallery_ids'] if index[i].get('instance_id')}) < len([i for i in query['gallery_ids'] if index[i].get('instance_id')]) and groups:
            raise ValueError('Multi-view item evaluation needs one representative per physical item.')
    if manifest.get('schema_version') == 3:
        from evaluation.integrity import validate_v3
        validate_v3(manifest,index)


def audit(data):
    """Coverage counts are observations, never evidence of accuracy."""
    images=list(data['index'].values()); models={};conditions={}
    for image in images:
        metadata=image.get('metadata',{})
        model=(metadata.get('brand'),metadata.get('product_model'))
        if model[1] and image.get('instance_id'):
            models.setdefault(model,set()).add(image['instance_id'])
        for key,value in image.get('capture',{}).items():
            if value is not None:
                conditions.setdefault(key,set()).add(str(value))
    return {'images':len(images),'physical_instances':len({i['instance_id'] for i in images if i.get('instance_id')}),
            'categories':sorted({i.get('metadata',{}).get('category') for i in images if i.get('metadata',{}).get('category')}),
            'product_models_with_multiple_units':sum(len(v)>1 for v in models.values()),
            'capture_values':{k:sorted(v) for k,v in conditions.items()},
            'no_match_queries':sum(not q['positive_ids'] for q in data['queries']),
            'multi_view_queries':sum(len(q.get('view_ids',[]))>1 or any(len(v)>1 for v in q.get('candidate_views',{}).values()) for q in data['queries']),
            'unknown_instance_images':sum(not i.get('instance_id') for i in images)}


def validate_isolation(development, independent):
    if development['split'] != 'development' or independent['split'] != 'independent':
        raise ValueError('Development and independent split roles must be explicit.')
    if development['content_hashes'] & independent['content_hashes']:
        raise ValueError('Content leakage between development and independent evaluation.')
    if development['pixel_hashes'] & independent['pixel_hashes']:
        raise ValueError('Decoded-image content leakage between development and independent evaluation.')
    def instances(data):
        return {r['instance_id'] for r in data['index'].values() if r.get('instance_id')}
    if instances(development) & instances(independent):
        raise ValueError('Physical-instance leakage between development and independent evaluation.')
