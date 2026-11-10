import copy
import csv
import json
import subprocess
import sys
import pytest
import numpy as np
from PIL import Image
from scripts.study_results import FIELDS, summarize
from evaluation.dataset import load_manifest
from evaluation.collection import validate_collection


def row(**changes):
    data=dict.fromkeys(FIELDS,'')
    data.update(session_code='S001',task_id='U01',device_class='desktop',input_method='keyboard',completion_status='independent',assistance_level='none',duration_seconds='90',timing_method='measured',recoverable_error_count='0',critical_error_count='0')
    return {**data,**changes}


def write_csv(tmp_path,rows,fields=FIELDS):
    path=tmp_path/'observations.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    return path


def test_observation_summary_empty_missing_deterministic(tmp_path):
    assert summarize(write_csv(tmp_path,[]))['sessions']==0
    path=write_csv(tmp_path,[row(),row(session_code='S002',completion_status='failed',duration_seconds='',timing_method='not_recorded')])
    result=summarize(path);assert result==summarize(path)
    assert result['tasks']['U01']['attempts']==2
    assert result['tasks']['U01']['independent_rate']==.5
    assert result['tasks']['U01']['timed_attempts']==1


@pytest.mark.parametrize('changes',[{'duration_seconds':'nan'},{'task_id':''},{'recoverable_error_count':'-1'},{'observer_notes_redacted':'email@example.edu'},{'assistance_level':'minor_hint'},{'completion_status':'not_attempted'}])
def test_invalid_observations_have_safe_messages(tmp_path,changes):
    result=summarize(write_csv(tmp_path,[row(**changes)]))
    assert result['invalid_records']==1 and result['errors'][0]['line']==2
    assert 'email@example.edu' not in json.dumps(result)


def test_observation_duplicate_private_and_missing_columns(tmp_path):
    assert summarize(write_csv(tmp_path,[row(),row()]))['invalid_records']==1
    assert summarize(write_csv(tmp_path,[],FIELDS+['email']))['errors']
    assert summarize(write_csv(tmp_path,[],FIELDS[:-1]))['errors']


def test_tool_cli_failure_messages_and_empty_file(tmp_path):
    path=tmp_path/'empty.csv';path.write_text('')
    assert summarize(path)['errors']
    result=subprocess.run([sys.executable,'-m','scripts.study_results',str(tmp_path/'absent.csv')],capture_output=True,text=True)
    assert result.returncode==2 and 'Cannot read observation CSV' in result.stderr
    result=subprocess.run([sys.executable,'-m','evaluation.collection','--development',str(tmp_path/'absent.json'),'--independent',str(tmp_path/'absent.json')],capture_output=True,text=True)
    assert result.returncode==2 and 'Invalid collection' in result.stderr


@pytest.fixture
def collection(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    def make(split):
        images=[]
        for n,role in enumerate(('query','gallery','gallery')):
            iid=f'{split}-{n}';path=iid+'.png'
            Image.fromarray(np.random.default_rng(n+(0 if split=='development' else 10)).integers(0,256,(60,70,3),dtype=np.uint8)).save(path)
            images.append(dict(id=iid,path=path,instance_id=split+('-a' if n<2 else '-b'),product_model_id='model-1',report_id=iid,role=role,capture_session_id=iid,source_asset_id=iid,label_provenance='TEST ONLY staged unit log',metadata={'category':'bottle'},capture={k:'TEST ONLY' for k in ('viewpoint','lighting','background','distance','occlusion')},selection_confirmed=True))
        q,a,b=[i['id'] for i in images]
        data=dict(schema_version=3,dataset_version='TEST ONLY v1',split=split,images=images,queries=[dict(id=q,image_id=q,gallery_ids=[a,b],positive_ids=[a],relations={a:'same_instance',b:'lookalike'},no_match=False),dict(id=q+'-absent',image_id=q,gallery_ids=[b],positive_ids=[],relations={b:'lookalike'},no_match=True)])
        return data
    return make('development'),make('independent')


def loaded(data):
    path=data['split']+'.json';open(path,'w',encoding='utf-8').write(json.dumps(data));return load_manifest(path)


def test_collection_accepts_same_instance_pairs_and_no_match(collection):
    dev,test=map(loaded,collection);result=validate_collection(dev,test)
    assert result['coverage']['independent']['same_model_negative_pairs']==2
    assert result['coverage']['independent']['no_match_queries']==1


@pytest.mark.parametrize('problem',['empty','missing','duplicate','model','leak','no_match','hard_negative','path'])
def test_collection_invalid(collection,problem):
    dev,test=copy.deepcopy(collection)
    if problem=='empty':test['images']=[];test['queries']=[]
    if problem=='missing':del test['images'][0]['capture']['lighting']
    if problem=='duplicate':test['images'].append(test['images'][0])
    if problem=='model':test['images'][1]['product_model_id']='conflict'
    if problem=='leak':
        for i in test['images'][:2]:i['instance_id']=dev['images'][0]['instance_id']
    if problem=='no_match':test['queries'][0]['no_match']=True
    if problem=='hard_negative':test['queries'][0]['relations'][test['images'][2]['id']]='unrelated'
    if problem=='path':test['images'][0]['path']='C:/private.png'
    with pytest.raises((ValueError,KeyError)):validate_collection(loaded(dev),loaded(test))
