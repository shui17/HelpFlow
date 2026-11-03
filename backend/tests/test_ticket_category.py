from uuid import uuid4

from tests.test_database import database_url
from tests.test_security import client, register, login


def test_category_create_update_filter_and_validation(client, database_url):
    _, email = register(client)
    headers = login(client, email)
    keyword = 'category-' + uuid4().hex
    tickets = []
    for category in ('technical', 'payment'):
        response = client.post('/api/v1/tickets', headers=headers,
            json={'title': keyword, 'description': '分类端到端验证', 'category': category})
        assert response.status_code == 201, response.text
        assert response.json()['data']['category'] == category
        tickets.append(response.json()['data'])
    filtered = client.get('/api/v1/tickets', headers=headers,
        params={'keyword': keyword, 'category': 'technical'}).json()['data']
    assert filtered['total'] == 1 and filtered['items'][0]['id'] == tickets[0]['id']
    updated = client.patch(f"/api/v1/tickets/{tickets[0]['id']}", headers=headers,
        json={'category': 'account'})
    assert updated.status_code == 200 and updated.json()['data']['category'] == 'account'
    assert client.get('/api/v1/tickets', headers=headers,
        params={'keyword': keyword, 'category': 'technical'}).json()['data']['total'] == 0
    assert client.get('/api/v1/tickets', headers=headers,
        params={'category': 'invalid'}).status_code == 422
    assert client.patch(f"/api/v1/tickets/{tickets[0]['id']}", headers=headers,
        json={'category': None}).status_code == 422
    assert client.post('/api/v1/tickets', headers=headers,
        json={'title': keyword, 'description': '错误分类', 'category': 'invalid'}).status_code == 422
