import copy
import numpy as np
import pytest
from evaluation.dataset import validate_extended,audit
from evaluation.phase3 import score_queries,select_config,metadata_signal,gate_policies
from evaluation.metrics import summarize


def fixture():
    index={i:{'instance_id':identity,'metadata':{}} for i,identity in [('q','one'),('q2','one'),('a','one'),('a2','one'),('b','two')]}
    q={'id':'query','image_id':'q','gallery_ids':['a','b'],'positive_ids':['a'],'relations':{'a':'same_instance','b':'lookalike'},'view_ids':['q','q2'],'candidate_views':{'a':['a','a2']}}
    data={'index':index,'queries':[q]}
    vectors={'q':[1,0],'q2':[0,1],'a':[0,1],'a2':[1,0],'b':[.8,.6]}
    desc={i:{'vector':np.array(v,dtype=float)} for i,v in vectors.items()}
    return data,{'clip':desc,'dinov2':copy.deepcopy(desc)}


def test_multiview_groups_validated_without_automatic_label_grouping():
    data,_=fixture();validate_extended(data,data['index'])
    data['queries'][0]['candidate_views']['b']=['b','q2']
    with pytest.raises(ValueError,match='share photographs'):
        validate_extended(data,data['index'])


def test_multiview_rejects_mixed_physical_units():
    data,_=fixture();data['index']['a2']['instance_id']='other'
    with pytest.raises(ValueError,match='consistent physical'):
        validate_extended(data,data['index'])


def test_v2_requires_label_provenance():
    data,_=fixture();data['schema_version']=2
    with pytest.raises(ValueError,match='provenance'):
        validate_extended(data,data['index'])


def test_metadata_rejects_unrecognized_label_fields():
    data,_=fixture();data['index']['a']['metadata']={'identity':'one'}
    with pytest.raises(ValueError,match='Metadata'):
        validate_extended(data,data['index'])


def test_multiple_views_change_ranking_only_when_explicitly_enabled():
    data,desc=fixture()
    assert score_queries(data,desc)[0]['ranking'][0]=='b'
    assert score_queries(data,desc,aggregation='max')[0]['ranking'][0]=='a'
    assert score_queries(data,desc,aggregation='mean')[0]['ranking'][0]=='b'


def test_hybrid_endpoints_and_no_label_access():
    data,desc=fixture();desc['dinov2']['a']['vector']=np.array([1.,0.])
    assert score_queries(data,desc,alpha=0)[0]['ranking'][0]=='a'
    assert score_queries(data,desc,alpha=1)[0]['ranking'][0]=='b'
    before=score_queries(data,desc,alpha=.5)[0]['ranking']
    for entry in data['index'].values():entry['instance_id']='changed'
    data['queries'][0]['positive_ids']=['b']
    assert score_queries(data,desc,alpha=.5)[0]['ranking']==before


def test_selection_uses_development_rows_and_prefers_simple_ties():
    data,desc=fixture();rows=score_queries(data,desc)
    configs=[{'alpha':a,'metadata_weight':0.,'aggregation':'single'} for a in [.5,0,1]]
    assert select_config([(c,rows) for c in configs])==configs[-1]


def test_metadata_missing_is_neutral_and_not_identity_evidence():
    assert metadata_signal({}, {'category':'bottle'})==0
    assert metadata_signal({'brand':' Brand '},{'brand':'brand'})==1
    assert metadata_signal({'product_model':'a'},{'product_model':'a'})==0


def test_false_negative_counts_include_wrong_acceptance_and_rejection():
    rows=[{'query_id':'wrong','ranking':['b'],'positive_ids':['a'],'top_score':.9},
          {'query_id':'rejected','ranking':['a'],'positive_ids':['a'],'top_score':.5}]
    a=summarize(rows,.7)['acceptance']
    assert a['false_negative_count']==2 and a['false_negative_rate']==1
    assert a['false_positive_count']==1


def test_coverage_distinguishes_units_from_product_models():
    data,_=fixture()
    for entry in data['index'].values():entry['metadata']={'brand':'brand','product_model':'model','category':'bottle'}
    result=audit(data)
    assert result['physical_instances']==2 and result['product_models_with_multiple_units']==1
    assert result['multi_view_queries']==1


def test_gate_annotation_keeps_visual_match_without_changing_original():
    data,desc=fixture();q=data['queries'][0];q.pop('view_ids');q.pop('candidate_views')
    for key,value in desc['clip'].items():
        value.update(label='charger' if key=='q' else 'earbuds',margin=.01,non_item_margin=-.1)
    desc['clip']['a']['vector']=np.array([1.,0.])
    rng=np.random.default_rng(7);regions={i:rng.integers(0,256,(40,40,3),dtype=np.uint8) for i in data['index']}
    result=gate_policies(data,desc['clip'],regions)
    assert result['policies']['original']['queries'][0]['ranking']==[]
    assert result['policies']['category_as_annotation']['queries'][0]['ranking'][0]=='a'
    assert result['suppressed_positives']==1
    assert result['decisions'][0]['query_category']=='charger'


def test_conflicting_pair_labels_rejected(tmp_path):
    import json
    from PIL import Image
    from evaluation.dataset import load_manifest
    images=[]
    for iid,color in [('a','red'),('b','blue')]:
        path=tmp_path/(iid+'.png');Image.new('RGB',(30,30),color).save(path)
        images.append({'id':iid,'path':str(path)})
    queries=[{'id':iid,'image_id':iid,'gallery_ids':[other],'positive_ids':[], 'relations':{other:relation}}
             for iid,other,relation in [('a','b','lookalike'),('b','a','unrelated')]]
    path=tmp_path/'data.json';path.write_text(json.dumps({'split':'development','images':images,'queries':queries}))
    with pytest.raises(ValueError,match='Conflicting relation'):
        load_manifest(path)


def test_report_keeps_hybrid_table_contiguous():
    from evaluation.phase3 import markdown
    m={'recall_at_1':1.,'mrr':1.};trial={'config':{'alpha':1.,'aggregation':'single','metadata_weight':0.},'metrics':m}
    report={'coverage':{},'recipes':{r:{'development_trials':[trial]} for r in ['full_frame','manual_crop']},
            'models':{},'local_evidence':{},'peak_combined_process_memory_mib':0}
    text=markdown(report)
    assert '| full_frame | 1.0 | single | 0.0 | 1.0 | 1.0 |\n| manual_crop' in text
