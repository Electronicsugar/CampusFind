"""Synthetic retrieval mechanics; these tests do not measure recognition accuracy."""
import json
from datetime import timedelta
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from backend.models import Item,ItemImage,MatchJob,MatchSuggestion,Notification,now
from backend.semantic import ModelUnavailable
from tests.test_platform import app,account,photo,report


class Encoder:
    model_version='synthetic-visual-search-v1'
    def __init__(self):self.calls=0
    def describe(self,image):
        self.calls+=1
        vector=np.mean(image,axis=(0,1)).astype(np.float32)+1
        vector/=np.linalg.norm(vector)
        return {'vector':vector,'label':'bottle' if self.calls==1 else 'bag','margin':.1,'non_item_margin':-.1,'alternatives':['bottle']}


@pytest.fixture
def encoder(monkeypatch):
    model=Encoder();monkeypatch.setattr('backend.visual_search.get_model',lambda:model);return model


def search(client,raw=None,**fields):
    return client.post('/api/v1/found/search-image',data={'selection':json.dumps({'confirmed':True,'box':None}),**fields},
        files={'photo':('query.jpg',photo() if raw is None else raw,'image/jpeg')})


def test_image_search_requires_auth_origin_and_csrf(app):
    assert search(TestClient(app)).status_code==401
    c=account(app);c.headers['origin']='https://attacker.example'
    assert search(c).status_code==403
    c.headers['origin']='http://testserver';c.headers['x-csrf-token']='bad'
    assert search(c).status_code==403


def test_search_existing_found_reports_without_publishing_or_notifications(app,encoder):
    finder=account(app);found=report(finder,count=2).json();c=account(app,'seeker@example.edu')
    files_before=set(app.state.settings.storage.glob('*.jpg'))
    with app.state.sessions() as db:
        counts_before=[db.scalar(select(func.count()).select_from(t)) for t in (Item,MatchJob,MatchSuggestion,Notification)]
    result=search(c)
    assert result.status_code==200,result.text
    data=result.json();assert data['total_reports']==1 and data['searched_photos']==2
    assert len(data['results'])==1 and data['results'][0]['item_id']==found['id']
    assert data['results'][0]['rank']==1 and 'visual_similarity' not in data['results'][0]
    assert 'identity' in data['notice'] and result.headers['cache-control']=='no-store'
    assert set(app.state.settings.storage.glob('*.jpg'))==files_before
    with app.state.sessions() as db:
        assert counts_before==[db.scalar(select(func.count()).select_from(t)) for t in (Item,MatchJob,MatchSuggestion,Notification)]
        assert all(row.cache_signature for row in db.scalars(select(ItemImage)))
    first_calls=encoder.calls
    assert search(c).status_code==200
    assert encoder.calls==first_calls+1 # Only the ephemeral query, not candidate images.


def test_private_inactive_lost_expired_and_deleted_reports_never_searchable(app,encoder):
    finder=account(app);ids=[report(finder,kind='LOST' if i==0 else 'FOUND').json()['id'] for i in range(6)]
    with app.state.sessions.begin() as db:
        db.get(Item,ids[1]).hidden=True
        db.get(Item,ids[2]).state='CLOSED'
        db.get(Item,ids[3]).expires_at=now()-timedelta(seconds=1)
        db.get(Item,ids[4]).deleted_at=now()
    c=account(app,'seeker@example.edu')
    result=search(c).json();assert [row['item_id'] for row in result['results']]==[ids[5]]
    assert search(c,category='wallet',strict_filters='true').json()['results']==[]
    assert search(c,q='Not the location',strict_filters='true').json()['total_reports']==0
    assert search(c,q='Library',category='bottle').json()['total_reports']==1


def test_filter_empty_state_distinguishes_existing_gallery_from_absent_reports(app,encoder):
    c=account(app);item=report(c).json()
    with app.state.sessions.begin() as db:
        row=db.get(Item,item['id']);row.category='other';row.title='Hair accessory / black clip';row.location='canteen table'
    blocked=search(c,category='black hair clip',q='canteen',strict_filters='true').json()
    assert blocked['total_reports']==blocked['searched_photos']==0
    assert blocked['empty_reason']=='filters'
    assert blocked['available_reports']==blocked['available_photos']==1
    assert blocked['applied_filters']=={'category':'black hair clip','q':'canteen'}
    assert encoder.calls==0
    broad=search(c).json()
    assert broad['results'][0]['item_id']==item['id'] and broad['empty_reason'] is None
    proper=search(c,category=' Other ',q=' canteen ').json()
    assert proper['total_reports']==1 and proper['applied_filters']=={'category':'other','q':'canteen'}
    assert search(c,q='Hair accessory').json()['total_reports']==1


@pytest.mark.parametrize('category',['hair clip','bottle','OTHER','unknown product 123'])
def test_default_image_search_never_excludes_reports_for_metadata_hints(app,encoder,category):
    c=account(app);item=report(c).json()
    with app.state.sessions.begin() as db:db.get(Item,item['id']).category='other'
    result=search(c,category=category,q='A different location').json()
    assert result['total_reports']==result['available_reports']==1
    assert result['searched_photos']==1 and result['results'][0]['item_id']==item['id']
    assert result['filter_mode']=='hints' and result['empty_reason'] is None
    assert result['results'][0]['metadata_matches']['text'] is False
    assert 'every category' in result['notice']


def test_explicit_filters_still_narrow_search_and_explain_zero_comparisons(app,encoder):
    c=account(app);report(c)
    result=search(c,category='wallet',strict_filters='true').json()
    assert result['filter_mode']=='strict' and result['empty_reason']=='filters'
    assert result['searched_photos']==0 and encoder.calls==0
    assert 'excluded 1 available found reports' in result['notice']


def test_empty_gallery_counts_do_not_expose_hidden_lost_or_deleted_records(app,encoder):
    c=account(app);found=report(c).json();report(c,kind='LOST')
    with app.state.sessions.begin() as db:db.get(Item,found['id']).hidden=True
    result=search(c,q='Library',strict_filters='true').json()
    assert result['empty_reason']=='gallery'
    assert result['available_reports']==result['available_photos']==0


@pytest.mark.parametrize('selection',[{'confirmed':False,'box':None},{'confirmed':True,'box':[True,0,1,1]}, {'confirmed':True,'box':[0,0,0,1]}, {'confirmed':True,'box':[float('nan'),0,1,1]},'bad'])
def test_invalid_selection_is_rejected_before_inference(app,encoder,selection):
    c=account(app);assert search(c,selection=json.dumps(selection)).status_code==400
    assert encoder.calls==0


def test_invalid_image_empty_gallery_and_model_failure(app,encoder,monkeypatch):
    c=account(app)
    assert search(c,raw=b'not an image').status_code==400
    result=search(c).json();assert result['total_reports']==0 and encoder.calls==0
    report(c)
    def unavailable():raise ModelUnavailable('Private model path must not leak')
    monkeypatch.setattr('backend.visual_search.get_model',unavailable)
    response=search(c);assert response.status_code==503 and 'Private model path' not in response.text


def test_search_bounds_and_busy_do_not_return_partial_rankings(app,encoder,monkeypatch):
    from backend.visual_search import SEARCH_WORK
    c=account(app);report(c,count=2)
    monkeypatch.setattr('backend.visual_search.MAX_GALLERY_PHOTOS',1)
    assert search(c).status_code==422
    assert SEARCH_WORK.acquire(blocking=False)
    try:assert search(c).status_code==429
    finally:SEARCH_WORK.release()
    monkeypatch.setattr('backend.visual_search.MAX_GALLERY_PHOTOS',2000)
    monkeypatch.setattr('backend.visual_search.MAX_SEARCH_SECONDS',-1)
    assert search(c).status_code==503


def test_visual_ranking_is_not_suppressed_by_category_predictions(app,encoder):
    c=account(app);first=report(c).json();second=report(c).json()
    # Deliberately mark the closest photo's category prediction as conflicting.
    from backend.matching import PreparedCache
    with app.state.sessions.begin() as db:
        cache=PreparedCache(encoder,app.state.settings)
        for image in db.scalars(select(ItemImage)):cache.get(image)
        a=db.get(ItemImage,first['images'][0]['id']);b=db.get(ItemImage,second['images'][0]['id'])
        a.descriptor={**a.descriptor,'vector':[1.,0.,0.],'label':'bag'}
        b.descriptor={**b.descriptor,'vector':[0.,1.,0.],'label':'bottle'}
    encoder.describe=lambda region:{'vector':np.array([1.,0.,0.]),'label':'bottle','margin':.1,'non_item_margin':-.1}
    result=search(c).json()
    assert [r['item_id'] for r in result['results']]==[first['id'],second['id']]
    assert result['next_offset'] is None


def test_search_ranks_entire_hundred_report_gallery_and_pages_results(app,encoder,monkeypatch):
    from datetime import date
    from uuid import uuid4
    c=account(app);owner=c.get('/api/v1/auth/me').json()['user']['id']
    encoder.describe=lambda region:{'vector':np.array([1.,0.,0.]),'label':'bottle','margin':.1}
    def descriptor(cache,image):
        i=image.position
        return ({'vector':np.array([i/124,(124-i)/124,0.]),'label':'bottle','margin':.1},None)
    monkeypatch.setattr('backend.visual_search.PreparedCache.get',descriptor)
    with app.state.sessions.begin() as db:
        for i in range(125):
            item=Item(owner_id=owner,kind='FOUND',title=f'Synthetic {i}',category='bottle',description='Synthetic gallery mechanics fixture',location='Library',event_date=date(2026,1,1),expires_at=now()+timedelta(days=1))
            db.add(item);db.flush()
            db.add(ItemImage(item_id=item.id,storage_key=uuid4().hex+'.jpg',content_hash='0'*64,position=i))
    first=search(c).json();second=search(c,offset='25').json()
    assert first['total_reports']==125 and first['searched_photos']==125
    assert first['results'][0]['title']=='Synthetic 124'
    assert len(first['results'])==len(second['results'])==25
    assert first['next_offset']==25 and second['next_offset']==50
    assert {r['item_id'] for r in first['results']}.isdisjoint(r['item_id'] for r in second['results'])
    assert search(c,offset='125').json()['results']==[]
