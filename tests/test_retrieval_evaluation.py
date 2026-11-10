import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image,PngImagePlugin
from evaluation.metrics import summarize,fit_threshold
from evaluation.dataset import load_manifest,validate_isolation
from evaluation.pipeline import pad_square,reviewed_box,evaluate


def rows():
    return [
        {'query_id':'correct','positive_ids':['a'],'ranking':['a','b'],'top_score':.8},
        {'query_id':'wrong','positive_ids':['b'],'ranking':['a','b'],'top_score':.9},
        {'query_id':'absent-proposed','positive_ids':[],'ranking':['a'],'top_score':.85},
        {'query_id':'absent-empty','positive_ids':[],'ranking':[],'top_score':None}]


def test_metrics_include_missed_positives_and_wrong_acceptances():
    m=summarize(rows(),.84)
    assert m['recall_at_1'] == .5
    assert m['recall_at_5'] == 1
    assert m['mrr'] == .75
    assert m['proposal_no_match_rejection'] == .5
    assert m['acceptance']['false_positive_count'] == 2
    assert m['acceptance']['no_match_rejection'] == .5
    assert m['acceptance']['correct_acceptance_recall'] == 0
    assert summarize(rows())['acceptance'] is None


def test_empty_evaluation_is_inconclusive_not_zero_accuracy():
    m=summarize([])
    assert m['recall_at_1'] is None and m['mrr'] is None
    assert fit_threshold([])['status'] == 'insufficient_data'
    assert evaluate({'queries':[]},object())['status'] == 'inconclusive'


def test_multiple_ground_truth_images_use_recall_not_hit_rate():
    m=summarize([{'query_id':'q','positive_ids':['a','b'],'ranking':['a'],'top_score':.5}])
    assert m['recall_at_1'] == .5


def test_unseparable_development_scores_can_choose_reject_all():
    fit=fit_threshold(rows())
    assert fit['status'] == 'development_fit_only'
    assert fit['threshold'] > .9
    assert fit['development_metrics']['accepted_queries'] == 0


def manifest(tmp_path,name,split,color,instance=None,metadata=False):
    photo=tmp_path/(name+'.png');info=PngImagePlugin.PngInfo()
    if metadata:
        info.add_text('comment',name)
    Image.new('RGB',(40,50),color).save(photo,pnginfo=info)
    path=tmp_path/(name+'.json')
    path.write_text(json.dumps({'split':split,'images':[{'id':name,'path':str(photo),'instance_id':instance}], 'queries':[]}))
    return path


def test_exact_content_leakage_is_rejected(tmp_path):
    a=load_manifest(manifest(tmp_path,'a','development','red'))
    b=load_manifest(manifest(tmp_path,'b','independent','red'))
    with pytest.raises(ValueError,match='Content leakage'):
        validate_isolation(a,b)


def test_reencoded_lossless_photo_leakage_is_rejected(tmp_path):
    a=load_manifest(manifest(tmp_path,'a','development','red'))
    b=load_manifest(manifest(tmp_path,'b','independent','red',metadata=True))
    with pytest.raises(ValueError,match='Decoded-image'):
        validate_isolation(a,b)


def test_different_views_of_same_instance_cannot_cross_splits(tmp_path):
    a=load_manifest(manifest(tmp_path,'a','development','red','item-1'))
    b=load_manifest(manifest(tmp_path,'b','independent','blue','item-1'))
    with pytest.raises(ValueError,match='Physical-instance leakage'):
        validate_isolation(a,b)


def test_independent_instances_and_empty_test_split_are_supported(tmp_path):
    a=load_manifest(manifest(tmp_path,'a','development','red','item-1'))
    b=load_manifest(manifest(tmp_path,'b','independent','blue','item-2'))
    validate_isolation(a,b)


def test_square_padding_keeps_object_pixels_and_aspect_ratio():
    image=np.full((30,60,3),77,np.uint8)
    padded=pad_square(image,np.array([.4,.5,.6]))
    assert padded.shape == (60,60,3)
    assert np.array_equal(padded[15:45],image)
    assert padded[0,0].tolist() == [153,128,102]


def test_reviewed_detector_does_not_choose_by_score_or_ground_truth():
    proposals=[{'box':[0,0,1,1],'score':.99},{'box':[.2,.3,.8,.9],'score':.3}]
    record={'detector_review':{'decision':'accept','proposal_index':1,'box':[.2,.3,.8,.9]},'manual_box':[0,0,1,1]}
    assert reviewed_box(record,proposals) == proposals[1]['box']
    with pytest.raises(ValueError,match='explicit per-image review'):
        reviewed_box({},proposals)
    with pytest.raises(ValueError,match='unavailable'):
        reviewed_box(record,[])
    with pytest.raises(ValueError,match='changed since review'):
        reviewed_box(record,[proposals[0],{'box':[0,0,.5,.5]}])


@pytest.mark.parametrize('crop',[False,True])
def test_offline_baseline_agrees_with_the_working_gallery(crop):
    from backend.vision import decode_image,prepare
    from backend.gallery import rank_gallery
    from evaluation.encoders import ClipEncoder
    from evaluation.pipeline import rank_query
    if not Path('models/clip/vision_model_quantized.onnx').exists() or not Path('data/samples/case-distant.jpg').exists():
        pytest.skip('Local private development data/model not installed')
    data=load_manifest('data/retrieval-development.json');query=data['queries'][0]
    relevant_ids=[query['image_id']]+query['gallery_ids']
    images={i:decode_image(Path(data['index'][i]['path']).read_bytes()) for i in relevant_ids}
    boxes={i:data['index'][i]['manual_box'] if crop else None for i in relevant_ids}
    regions={i:prepare(images[i],boxes[i],normalize=False)[0] for i in relevant_ids}
    encoder=ClipEncoder();descriptions={i:encoder.describe(image) for i,image in regions.items()}
    offline=rank_query(query,descriptions,regions,encoder)
    live=rank_gallery(images[query['image_id']],[(n,i,images[i],boxes[i]) for n,i in enumerate(query['gallery_ids'])],boxes[query['image_id']])
    assert offline['ranking'] == [r['name'] for r in live if r['relevance']=='relevant']
    assert [(r['id'],r['relevance'],r['semantic_similarity']) for r in offline['candidates']] == [(r['name'],r['relevance'],r['semantic_similarity']) for r in live]
