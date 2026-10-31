"""Bounded insight cache keyed by facts, recommendations and model availability."""
import hashlib
import json
import threading
import time
from collections import OrderedDict

_CACHE = OrderedDict()
_LOCK = threading.Lock()

def cached_insights(dj, facts, recs, refresh=False):
    key = hashlib.sha256(json.dumps([dj.backend, facts, recs], sort_keys=True, default=str).encode()).hexdigest()
    with _LOCK:
        entry = _CACHE.get(key)
        if not refresh and entry and entry[0] > time.monotonic():
            _CACHE.move_to_end(key)
            return entry[1]
    result = dj.get_intel(facts, recs)
    ttl = 1800 if result.get('_status') == 'ready' else 45
    with _LOCK:
        _CACHE[key] = (time.monotonic() + ttl, result)
        _CACHE.move_to_end(key)
        while len(_CACHE) > 128:
            _CACHE.popitem(last=False)
    return result
