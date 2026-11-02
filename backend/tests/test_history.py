import boto3
import pytest
from moto import mock_aws

from isitai import config, history_repo
from isitai.handlers import history
from conftest import Ctx, parse


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'test')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test')
    with mock_aws():
        boto3.client('dynamodb').create_table(
            TableName='isitai-history', BillingMode='PAY_PER_REQUEST',
            AttributeDefinitions=[{'AttributeName': 'session_id', 'AttributeType': 'S'},
                                  {'AttributeName': 'sk', 'AttributeType': 'S'}],
            KeySchema=[{'AttributeName': 'session_id', 'KeyType': 'HASH'},
                       {'AttributeName': 'sk', 'KeyType': 'RANGE'}])
        monkeypatch.setattr(config, 'HISTORY_TABLE', 'isitai-history')
        monkeypatch.setattr(history_repo, '_state', {'table': None})
        yield


def item(i):
    return {'request_id': f'r{i}', 'sha256': 'a' * 64, 'content_type': 'image/png', 'size_bytes': 10,
            'label': 'uncertain', 'prob_ai': 0.5, 'model': 'cnn', 'model_version': 'mock-0.1',
            'cache_hit': False, 'latency_ms': 5, 'file_name': f'f{i}.png'}


def get(session='prueba-1234', **query):
    event = {'headers': {'x-session-id': session}, 'queryStringParameters': query or None}
    return parse(history.handler(event, Ctx()))


def test_newest_first_with_pagination(table):
    for i in range(3):
        history_repo.save('prueba-1234', f'2026-11-01T10:00:0{i}.000+00:00', item(i))
    history_repo.save('otra-sesion', '2026-11-01T11:00:00.000+00:00', item(9))
    status, page1 = get(limit='2')
    assert status == 200 and [x['request_id'] for x in page1['items']] == ['r2', 'r1']
    assert page1['items'][0]['model'] == 'cnn' and page1['items'][0]['prob_ai'] == 0.5
    _, page2 = get(limit='2', cursor=page1['next_cursor'])
    assert [x['request_id'] for x in page2['items']] == ['r0']


def test_invalid_cursor_is_400(table):
    status, body = get(cursor='no-es-un-cursor')
    assert status == 400 and body['error']['code'] == 'invalid_cursor'


def test_cursor_from_another_session_is_400(table):
    for i in range(2):
        history_repo.save('otra-sesion', f'2026-11-01T10:00:0{i}.000+00:00', item(i))
    _, page = get(session='otra-sesion', limit='1')
    status, _ = get(cursor=page['next_cursor'])
    assert status == 400


def test_missing_session_is_400(table):
    status, body = get(session='corta')
    assert status == 400 and body['error']['code'] == 'missing_session'


def test_disabled_history_is_503(monkeypatch):
    monkeypatch.setattr(config, 'HISTORY_TABLE', '')
    status, body = get()
    assert status == 503 and body['error']['code'] == 'history_disabled'
    history_repo.save('prueba-1234', '2026-11-01T10:00:00.000+00:00', item(0))


def test_page_matches_backend_contract(table):
    from conftest import backend_schema_errors
    history_repo.save('prueba-1234', '2026-11-01T10:00:00.000+00:00', item(0))
    _, page = get()
    assert backend_schema_errors('HistoryPage', page) == []
