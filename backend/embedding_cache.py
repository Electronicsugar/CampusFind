"""Bounded, memory-only descriptor cache with single-flight CPU inference."""
from collections import OrderedDict
from copy import deepcopy
import hashlib
from threading import Lock, BoundedSemaphore
from time import perf_counter


class CacheBusy(RuntimeError):
    pass


def image_key(image, model_version, preprocessing):
    digest=hashlib.sha256()
    for value in (model_version,preprocessing,str(image.shape),str(image.dtype)):
        digest.update(value.encode('utf-8'));digest.update(b'\0')
    digest.update(image.tobytes(order='C'))
    return digest.digest()


class EmbeddingCache:
    def __init__(self,max_entries=256,wait_seconds=10):
        if max_entries < 1:
            raise ValueError('Cache capacity must be positive.')
        self.max_entries=max_entries;self.wait_seconds=wait_seconds
        self._values=OrderedDict();self._lock=Lock();self._run=BoundedSemaphore(1)
        self._hits=0;self._misses=0;self._failures=0;self._inference_ms=0

    def get_or_compute(self,key,compute):
        with self._lock:
            if key in self._values:
                self._hits+=1;self._values.move_to_end(key)
                return deepcopy(self._values[key])
        if not self._run.acquire(timeout=self.wait_seconds):
            raise CacheBusy('Visual encoder is busy. Try again shortly.')
        try:
            with self._lock:
                # Another request may have computed this exact content while we waited.
                if key in self._values:
                    self._hits+=1;self._values.move_to_end(key)
                    return deepcopy(self._values[key])
                self._misses+=1
            started=perf_counter()
            try:
                value=compute()
            except Exception:
                with self._lock:
                    self._failures+=1
                raise
            finally:
                with self._lock:
                    self._inference_ms+=(perf_counter()-started)*1000
            with self._lock:
                self._values[key]=deepcopy(value);self._values.move_to_end(key)
                while len(self._values)>self.max_entries:
                    self._values.popitem(last=False)
            return deepcopy(value)
        finally:
            self._run.release()

    def clear(self):
        if not self._run.acquire(timeout=self.wait_seconds):
            raise CacheBusy('Encoder is running; cannot clear the cache now.')
        try:
            with self._lock:
                self._values.clear();self._hits=0;self._misses=0;self._failures=0;self._inference_ms=0
        finally:
            self._run.release()

    def stats(self):
        with self._lock:
            return {'entries':len(self._values),'max_entries':self.max_entries,'hits':self._hits,
                    'inference_calls':self._misses,'failures':self._failures,
                    'inference_ms':round(self._inference_ms,3),'max_concurrent_inferences':1}
