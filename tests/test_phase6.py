"""Synthetic arrays verify mechanics only; never count as recognition evidence."""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from evaluation.dataset import load_manifest
from evaluation.integrity import validate_v3, screen_splits, coverage
from evaluation.metrics import summarize, fit_threshold
from evaluation.report_retrieval import Config, DescriptorStore, rank_reports, score_dataset
from evaluation.phase6 import transform, choose, run, independent_result, detector_diagnostics


def test_map_denominators_and_acceptance_precision_rejection_are_distinct():
    rows=[{'query_id':'q','positive_ids':['a','c'],'ranking':['a','b','c'],'top_score':.9},
          {'query_id':'wrong','positive_ids':['x'],'ranking':['y'],'top_score':.8},
          {'query_id':'absent','positive_ids':[],'ranking':['z'],'top_score':.7}]
    m=summarize(rows,.75)
    assert m['mean_average_precision']==pytest.approx((1+2/3)/4)
    assert m['acceptance']['precision']==.5
    assert m['acceptance']['false_rejection_rate_on_known_queries']==0
    assert m['acceptance']['false_negative_rate']==.5
    assert m['acceptance']['wrong_accepted_known_queries']==1
    assert summarize(rows,1.)['acceptance']['precision'] is None
    assert summarize([])['mean_average_precision'] is None


def descriptions():
    return {'clip':{k:{'vector':np.array(v)} for k,v in {'q':[1.,0.],'q2':[0.,1.],
                   'a':[1.,0.],'a2':[0.,1.],'b':[.8,.6]}.items()}}


def test_feature_flag_fails_closed_before_model_loading(tmp_path,monkeypatch):
    monkeypatch.setattr('evaluation.phase6.ClipEncoder',lambda:pytest.fail('Must not load'))
    with pytest.raises(RuntimeError,match='enable-experimental'):run({}, {}, tmp_path/'cache',enabled=False)
    with pytest.raises(RuntimeError,match='disabled'):rank_reports(['q'],{'a':['a']},descriptions(),Config())
    assert not (tmp_path/'cache').exists()


def test_hybrid_max_uses_same_pair_and_exposes_model_disagreement():
    desc=descriptions();desc['dinov2']=copy.deepcopy(desc['clip'])
    desc['dinov2']['a']['vector']=np.array([0.,1.]);desc['dinov2']['a2']['vector']=np.array([1.,0.])
    rows=rank_reports(['q'],{'item':['a','a2']},desc,Config(.5,'max'),enabled=True)
    assert rows[0]['score']==.5  # Independent per-model maxima would falsely yield 1.
    assert rows[0]['best_pair']['model_scores']=={'clip':1.,'dinov2':0.}
    assert rows[0]['best_pair']['candidate_image_id']=='a'


def test_report_evidence_handles_poor_views_and_stable_ties():
    desc=descriptions()
    single=rank_reports(['q','q2'],{'item':['a','a2']},desc,Config(),enabled=True)[0]
    mean=rank_reports(['q','q2'],{'item':['a','a2']},desc,Config(1,'mean'),enabled=True)[0]
    coverage_row=rank_reports(['q','q2'],{'item':['a','a2']},desc,Config(1,'bidirectional_best'),enabled=True)[0]
    assert single['score']==1 and mean['score']==.5 and coverage_row['score']==1
    assert mean['pair_score_min']==0 and mean['pair_score_max']==1
    assert coverage_row['query_view_best_scores']==[1.,1.]
    rows=rank_reports(['q'],{'first':['a'],'second':['a']},desc,Config(),enabled=True)
    assert [r['report_id'] for r in rows]==['first','second']
    with pytest.raises(ValueError):rank_reports(['q'],{'empty':[]},desc,Config(),enabled=True)
    with pytest.raises(ValueError):Config(float('nan'))
    with pytest.raises(ValueError):rank_reports(['q'],{'self':['q']},desc,Config(),enabled=True)


def test_report_dedup_and_labels_cannot_change_ranking():
    data={'index':{k:{'report_id':'same' if k in ('a','a2') else k} for k in descriptions()['clip']},
          'queries':[{'id':'q','image_id':'q','gallery_ids':['a','a2','b'],'positive_ids':['a','a2']}]}
    row=score_dataset(data,descriptions(),Config(1,'max'))[0]
    assert row['ranking']==['same','b'] and row['positive_ids']==['same']
    assert len(row['candidates'])==2
    data['queries'][0]['positive_ids']=['b']
    for entry in data['index'].values():entry['instance_id']='unrelated-label'
    assert score_dataset(data,descriptions(),Config(1,'max'))[0]['ranking']==row['ranking']


class FakeEncoder:
    name='fake';version='v1';semantic_routing=False
    def __init__(self):self.calls=0
    def describe(self,image):self.calls+=1;return {'vector':np.array([1.,0.],np.float32)}


def test_persistent_cache_survives_restart_and_invalidates_all_inputs(tmp_path):
    path=tmp_path/'cache.sqlite';encoder=FakeEncoder();image=np.zeros((30,40,3),np.uint8)
    store=DescriptorStore(path);store.describe(encoder,image,'crop');store.close()
    store=DescriptorStore(path);assert store.describe(encoder,image,'crop')['vector'].tolist()==[1.,0.]
    assert encoder.calls==1 and store.hits==1
    store.describe(encoder,image,'square');encoder.version='v2';store.describe(encoder,image,'crop')
    image[0,0]=1;store.describe(encoder,image,'crop');assert encoder.calls==4
    store.db.execute("UPDATE descriptors SET value='{}'");store.db.commit()
    store.describe(encoder,image,'crop');assert encoder.calls==5
    store.close()


def manifest(tmp_path,name,split,array,instance):
    image=tmp_path/(name+'.png');Image.fromarray(array).save(image)
    path=tmp_path/(name+'.json');path.write_text(json.dumps({'split':split,'images':[
        {'id':name,'path':str(image),'instance_id':instance}],'queries':[]}))
    return load_manifest(path)


def test_near_duplicate_reencoding_requires_hash_bound_review(tmp_path):
    rng=np.random.default_rng(4);a=rng.integers(20,230,(80,100,3),dtype=np.uint8)
    dev=manifest(tmp_path,'dev','development',a,'unit-a')
    test=manifest(tmp_path,'heldout','independent',a+1,'unit-b')
    screen=screen_splits(dev,test);assert screen['status']=='blocked_pending_review'
    pair=screen['suspected_near_duplicates'][0]['sha256_pair']
    test['near_duplicate_reviews']=[{'sha256_pair':pair,'decision':'distinct_capture','reviewer':'test reviewer','reason':'synthetic test only'}]
    assert screen_splits(dev,test)['status']=='screen_passed'
    test['index']['heldout']['source_asset_id']='same';dev['index']['dev']['source_asset_id']='same'
    with pytest.raises(ValueError,match='source_asset_id'):screen_splits(dev,test)


def test_unknown_heldout_id_blocks_even_without_duplicate(tmp_path):
    rng=np.random.default_rng(8)
    dev=manifest(tmp_path,'d','development',rng.integers(0,255,(50,50,3),dtype=np.uint8),'known')
    test=manifest(tmp_path,'i','independent',rng.integers(0,255,(50,50,3),dtype=np.uint8),None)
    assert screen_splits(dev,test)['unknown_independent_instance_images']==1
    assert screen_splits(dev,test)['status']=='blocked_pending_review'


def strict_data():
    index={}
    for iid,instance,report,role in [('q','unit1','lost','query'),('a','unit1','found','gallery'),('b','unit2','other','gallery')]:
        index[iid]={'instance_id':instance,'report_id':report,'product_model_id':'model1',
                    'capture_session_id':'session-'+iid,'source_asset_id':iid,'label_provenance':'fixture only',
                    'metadata':{'category':'bottle'},'capture':{'lighting':'shade'},'role':role}
    query={'id':'q','image_id':'q','gallery_ids':['a','b'],'positive_ids':['a'],'relations':{'a':'same_instance','b':'lookalike'}}
    return {'index':index,'queries':[query]}


def test_strict_report_schema_and_hard_negative_counts():
    data=strict_data();validate_v3(data,data['index'])
    assert coverage(data)['same_model_negative_pairs']==1
    data['index']['b']['report_id']='found'
    with pytest.raises(ValueError,match='Report photos'):validate_v3(data,data['index'])


@pytest.mark.parametrize('change',[{'manual_box':[0,0,0,1]},{'product_model_id':''},{'role':'both'},{'capture':{}},
                                    {'localization_boxes':[[0,0,1,1]]}])
def test_strict_schema_rejects_incomplete_or_invalid_annotations(change):
    data=strict_data();data['index']['q'].update(change)
    with pytest.raises(ValueError):validate_v3(data,data['index'])


def test_segmentation_requires_review_hash_and_preserves_foreground(tmp_path):
    image=np.full((40,60,3),200,np.uint8);mask=np.zeros((40,60),np.uint8);mask[:,10:50]=255
    path=tmp_path/'mask.png';Image.fromarray(mask).save(path)
    entry={'manual_box':[0,0,1,1]}
    with pytest.raises(ValueError,match='reviewed'):transform(entry,image,'segmented',[0,0,0])
    entry['segmentation']={'path':str(path),'reviewed':True,'provenance':'test','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    region=transform(entry,image,'segmented',[0,0,0]);assert region.shape==(60,60,3)
    assert np.all(region[10:50,10:50]==200) and np.all(region[10:50,:10]==0)
    entry['segmentation']['sha256']='changed'
    with pytest.raises(ValueError,match='changed'):transform(entry,image,'segmented',[0,0,0])


def test_detector_localization_does_not_use_manual_crop_as_truth(tmp_path):
    data=manifest(tmp_path,'a','development',np.full((40,40,3),100,np.uint8),'one')
    data['index']['a']['manual_box']=[0,0,1,1]
    class Detector:
        def detect(self,image):return [{'box':[0,0,1,1]}]
    _,diagnostic=detector_diagnostics(data,Detector())
    assert diagnostic['proposal_recall_iou50'] is None
    data['index']['a'].update(localization_boxes=[[0,0,1,1]],localization_provenance='test')
    _,diagnostic=detector_diagnostics(data,Detector())
    assert diagnostic['proposal_recall_iou50']==1


def test_selection_and_heldout_absence_do_not_imply_validation():
    row={'query_id':'q','positive_ids':['a'],'ranking':['a'],'top_score':.8}
    trials=[{'config':{'alpha':alpha,'aggregation':'single'},'development':{'metrics':summarize([row])}}
            for alpha in (.5,0.,1.)]
    assert choose(trials)['config']['alpha']==1
    assert choose([]) is None
    assert fit_threshold([row])['threshold'] is None
    assert independent_result({'queries':[]},{},Config(),None,{'status':'screen_passed'})['status']=='inconclusive'


def test_independent_threshold_is_applied_unchanged(monkeypatch):
    data=strict_data()
    def forbidden(*args,**kwargs):pytest.fail('Independent evaluation must not fit thresholds')
    monkeypatch.setattr('evaluation.phase6.fit_threshold',forbidden)
    result=independent_result(data,descriptions(),Config(),1.1,{'status':'screen_passed'})
    assert result['metrics']['acceptance']['threshold']==1.1
    assert result['metrics']['acceptance']['accepted_queries']==0
    assert independent_result(data,descriptions(),Config(),.5,{'status':'blocked_pending_review'})['status']=='inconclusive'


def test_runner_marks_incomplete_recipe_unavailable_without_dropping_images(tmp_path,monkeypatch):
    rng=np.random.default_rng(11);photos=[]
    for iid in ('q','a'):
        path=tmp_path/(iid+'.png');Image.fromarray(rng.integers(0,255,(40,40,3),dtype=np.uint8)).save(path)
        photos.append({'id':iid,'path':str(path),'instance_id':'unit'})
    photos[0]['manual_box']=[0,0,1,1]
    path=tmp_path/'dev.json';path.write_text(json.dumps({'split':'development','images':photos,
        'queries':[{'id':'q','image_id':'q','gallery_ids':['a'],'positive_ids':['a'],'relations':{'a':'same_instance'}}]}))
    test_path=tmp_path/'test.json';test_path.write_text(json.dumps({'split':'independent','images':[],'queries':[]}))
    class Encoder(FakeEncoder):
        mean=np.array([0.,0.,0.])
    def missing():raise RuntimeError('Model unavailable in synthetic regression')
    monkeypatch.setattr('evaluation.phase6.ClipEncoder',missing)
    monkeypatch.setattr('evaluation.phase6.DinoEncoder',Encoder)
    monkeypatch.setattr('evaluation.phase6.get_detector',lambda *args:None)
    result=run(load_manifest(path),load_manifest(test_path),tmp_path/'cache',enabled=True,recipes=['full_frame','manual_crop'])
    assert result['recipes']['full_frame']['development_trials'][0]['development']['metrics']['queries']==1
    assert result['recipes']['manual_crop']['development_trials']==[]
    assert 'dinov2/development' in result['recipes']['manual_crop']['unavailable']
    assert result['recipes']['manual_crop']['independent']['status']=='inconclusive'
    assert result['production_ranking_changed'] is False
