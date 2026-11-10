from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
import time
import numpy as np
import pytest
from backend.embedding_cache import EmbeddingCache, CacheBusy, image_key


def test_cache_keys_include_content_shape_dtype_model_and_preprocessing():
    image=np.arange(120,dtype=np.uint8).reshape(4,10,3)
    key=image_key(image,'model1','center')
    assert key == image_key(image.copy(),'model1','center')
    assert key != image_key(image,'model2','center')
    assert key != image_key(image,'model1','square')
    assert key != image_key(image.reshape(10,4,3),'model1','center')
    changed=image.copy();changed[0,0,0]+=1
    assert key != image_key(changed,'model1','center')
    view=image[:,::2]
    assert image_key(view,'m','p') == image_key(view.copy(),'m','p')


def test_lru_is_bounded_and_results_cannot_poison_cached_vectors():
    cache=EmbeddingCache(max_entries=2);computed=[]
    def get(key):
        return cache.get_or_compute(key,lambda:(computed.append(key) or {'vector':np.array([1.,2.]),'labels':['a']}))
    first=get('a');get('b');first['vector'][0]=99;first['labels'].append('bad')
    assert get('a')['vector'][0] == 1
    assert get('a')['labels'] == ['a']
    get('c');get('b')
    assert computed == ['a','b','c','b']
    assert cache.stats()['entries'] == 2


def test_repeated_simultaneous_content_is_encoded_once():
    cache=EmbeddingCache();barrier=Barrier(6);calls=[]
    def compute():
        calls.append(1);time.sleep(.02);return np.array([1.,0.])
    def request(_):
        barrier.wait(timeout=2)
        return cache.get_or_compute('same',compute)
    with ThreadPoolExecutor(max_workers=6) as workers:
        results=list(workers.map(request,range(6)))
    assert len(calls) == 1
    assert all(np.array_equal(r,[1,0]) for r in results)
    assert cache.stats()['hits'] == 5


def test_different_images_still_bound_native_inference_concurrency():
    cache=EmbeddingCache();lock=Lock();state={'active':0,'peak':0}
    def compute():
        with lock:
            state['active']+=1;state['peak']=max(state['peak'],state['active'])
        time.sleep(.02)
        with lock:
            state['active']-=1
        return 1
    with ThreadPoolExecutor(max_workers=4) as workers:
        assert list(workers.map(lambda k:cache.get_or_compute(k,compute),range(4))) == [1]*4
    assert state['peak'] == 1


def test_failures_are_not_cached_and_do_not_hold_the_inference_slot():
    cache=EmbeddingCache()
    def fail():
        raise ValueError('bad model')
    with pytest.raises(ValueError):
        cache.get_or_compute('k',fail)
    assert cache.get_or_compute('k',lambda:2) == 2
    assert cache.stats()['failures'] == 1
    assert cache.stats()['inference_calls'] == 2


def test_busy_encoder_times_out_with_a_visible_retriable_error():
    cache=EmbeddingCache(wait_seconds=.01)
    cache._run.acquire()
    try:
        with pytest.raises(CacheBusy):
            cache.get_or_compute('k',lambda:1)
    finally:
        cache._run.release()
    assert cache.get_or_compute('k',lambda:1) == 1
