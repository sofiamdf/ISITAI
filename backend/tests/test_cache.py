import json

import pytest

from isitai import cache, config


class FakeValkey:
    def __init__(self, fail=False):
        self.data, self.fail, self.calls = {}, fail, []

    def _maybe_fail(self):
        if self.fail:
            raise ConnectionError('caché caída')

    def getex(self, key, ex):
        self.calls.append(('getex', key, ex))
        self._maybe_fail()
        return self.data.get(key)

    def set(self, key, value, ex):
        self.calls.append(('set', key, ex))
        self._maybe_fail()
        self.data[key] = value

    def ping(self):
        self._maybe_fail()
        return True


@pytest.fixture
def fake_cache(monkeypatch):
    client = FakeValkey()
    monkeypatch.setattr(config, 'CACHE_ENDPOINT', 'isitai-cache.example')
    monkeypatch.setattr(cache, '_state', {'client': None, 'disabled_until': 0.0})
    monkeypatch.setattr(cache, '_connect', lambda: client)
    return client


def test_disabled_without_endpoint(monkeypatch):
    monkeypatch.setattr(config, 'CACHE_ENDPOINT', '')
    assert cache.get_result('k', 60) is None and cache.ping() is None
    cache.put_result('k', {'a': 1}, 60)


def test_key_includes_deployment_and_model():
    assert cache.result_key('mock', 'cnn', 'abc') == 'isitai:v1:mock:cnn:abc'


def test_round_trip_renews_ttl(fake_cache):
    cache.put_result('k', {'prob_ai': 0.5}, 60)
    assert cache.get_result('k', 60) == {'prob_ai': 0.5}
    assert fake_cache.calls[-1] == ('getex', 'k', 60)
    assert json.loads(fake_cache.data['k']) == {'prob_ai': 0.5}


def test_failure_skips_cache_for_30_seconds(fake_cache, monkeypatch):
    fake_cache.fail = True
    now = [1000.0]
    monkeypatch.setattr(cache.time, 'monotonic', lambda: now[0])
    assert cache.get_result('k', 60) is None
    calls = len(fake_cache.calls)
    assert cache.get_result('k', 60) is None and len(fake_cache.calls) == calls
    now[0] += 31
    fake_cache.fail = False
    assert cache.get_result('k', 60) is None and len(fake_cache.calls) == calls + 1
    assert cache.ping() is True
