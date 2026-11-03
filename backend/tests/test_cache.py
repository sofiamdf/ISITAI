import json

import pytest

from isitai import cache, config


class FakeTable:
    def __init__(self, fail=False):
        self.items, self.fail, self.calls = {}, fail, []

    def _maybe_fail(self):
        if self.fail:
            raise ConnectionError('caché caída')

    def get_item(self, Key):
        self.calls.append(('get_item', Key['cache_key']))
        self._maybe_fail()
        item = self.items.get(Key['cache_key'])
        return {'Item': dict(item)} if item else {}

    def put_item(self, Item):
        self.calls.append(('put_item', Item['cache_key']))
        self._maybe_fail()
        self.items[Item['cache_key']] = dict(Item)

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues):
        self.calls.append(('update_item', Key['cache_key']))
        self._maybe_fail()
        self.items[Key['cache_key']]['expires_at'] = ExpressionAttributeValues[':e']


@pytest.fixture
def fake_cache(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(config, 'CACHE_TABLE', 'isitai-cache-test')
    monkeypatch.setattr(cache, '_state', {'table': None, 'disabled_until': 0.0})
    monkeypatch.setattr(cache, '_connect', lambda: table)
    return table


def test_disabled_without_table(monkeypatch):
    monkeypatch.setattr(config, 'CACHE_TABLE', '')
    assert cache.get_result('k', 60) is None and cache.ping() is None
    cache.put_result('k', {'a': 1}, 60)


def test_key_includes_deployment_and_model():
    assert cache.result_key('mock', 'cnn', 'abc') == 'isitai:v1:mock:cnn:abc'


def test_round_trip_renews_ttl(fake_cache, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(cache.time, 'time', lambda: now[0])
    cache.put_result('k', {'prob_ai': 0.5}, 60)
    assert json.loads(fake_cache.items['k']['value']) == {'prob_ai': 0.5}
    assert fake_cache.items['k']['expires_at'] == 1060
    now[0] = 1010.0
    assert cache.get_result('k', 100) == {'prob_ai': 0.5}
    assert fake_cache.calls[-1] == ('update_item', 'k')
    assert fake_cache.items['k']['expires_at'] == 1110


def test_expired_item_is_a_miss(fake_cache, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(cache.time, 'time', lambda: now[0])
    cache.put_result('k', {'prob_ai': 0.5}, 60)
    now[0] = 2000.0  # DynamoDB todavía no lo borró, pero ya venció
    assert cache.get_result('k', 60) is None
    assert ('update_item', 'k') not in fake_cache.calls


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


def test_ping_false_when_down(fake_cache):
    fake_cache.fail = True
    assert cache.ping() is False