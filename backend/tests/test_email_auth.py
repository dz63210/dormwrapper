import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import db_session, init_db
from app.main import app
from app.services import email_auth

init_db()
client = TestClient(app)


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, 'supabase_url', 'https://auth.example.com')
    monkeypatch.setattr(settings, 'supabase_publishable_key', 'test-publishable-key')
    calls = []
    pending = set()

    def response(request):
        body = json.loads(request.content)
        calls.append((request, body))
        email = body['email']
        if request.url.path == '/auth/v1/otp':
            pending.add(email)
            return httpx.Response(200, json={})
        if body['token'] != '123456' or email not in pending:
            return httpx.Response(403, json={'error': 'invalid code'})
        pending.remove(email)
        return httpx.Response(200, json={
            'access_token': 'provider-access-secret', 'refresh_token': 'provider-refresh-secret',
            'user': {'id': str(uuid.uuid5(uuid.NAMESPACE_URL, email)), 'email': email,
                     'email_confirmed_at': '2026-10-11T12:00:00Z'}})

    transport = httpx.MockTransport(response)
    monkeypatch.setattr(email_auth, 'provider_client', lambda: httpx.Client(transport=transport))
    return calls, pending


def address():
    return f'user-{uuid.uuid4().hex[:12]}@example.com'


def verify(email, headers=None, code='123456'):
    return client.post('/api/auth/verify-code', json={'email': email, 'code': code}, headers=headers or {})


def test_email_sign_in_requires_verification_and_recovers_account(provider):
    calls, pending = provider
    email = address()
    requested = client.post('/api/auth/request-code', json={'email': ' ' + email.upper() + ' '})
    assert requested.status_code == 200
    assert 'token' not in requested.json()
    assert calls[0][1] == {'email': email, 'create_user': True}
    assert calls[0][0].headers['apikey'] == 'test-publishable-key'
    assert verify(email, code='000000').status_code == 400
    response = verify(email)
    assert response.status_code == 200
    first = response.json()
    assert first['email'] == email
    assert 'provider-access-secret' not in response.text
    assert 'provider-refresh-secret' not in response.text
    assert verify(email).status_code == 400  # provider OTP consumed
    headers = {'Authorization': 'Bearer ' + first['token']}
    assert client.get('/api/me', headers=headers).json()['email'] == email
    assert client.post('/api/logout', headers=headers).status_code == 204
    pending.add(email)  # simulate a newly delivered code on a later visit
    returning = verify(email).json()
    assert returning['id'] == first['id']
    assert returning['token'] != first['token']


def test_guest_upgrade_preserves_design_ownership(provider):
    from tests.test_security import photo
    guest = client.post('/api/login', json={'handle': 'upgrade_' + uuid.uuid4().hex[:10]}).json()
    headers = {'Authorization': 'Bearer ' + guest['token']}
    sub = client.post('/api/submissions', headers=headers, data={'budget': 200, 'style': 'modern'},
                      files={'image': ('room.png', photo(), 'image/png')}).json()
    email = address()
    provider[1].add(email)
    linked = verify(email, headers=headers)
    assert linked.status_code == 200
    assert linked.json()['id'] == guest['id']
    new_headers = {'Authorization': 'Bearer ' + linked.json()['token']}
    assert client.get(f"/api/submissions/{sub['id']}", headers=new_headers).status_code == 200
    assert client.get('/api/me', headers=headers).status_code == 401


def test_guest_can_merge_into_existing_verified_account(provider):
    email = address()
    provider[1].add(email)
    existing = verify(email).json()
    guest = client.post('/api/login', json={'handle': 'merge_' + uuid.uuid4().hex[:10]}).json()
    with db_session() as db:
        sub_id = db.execute("INSERT INTO submissions(created_at, room_image_path, budget, style, user_id) "
                            "VALUES ('2020-01-01', 'missing.jpg', 100, 'modern', ?)", (guest['id'],)).lastrowid
    provider[1].add(email)
    merged = verify(email, headers={'Authorization': 'Bearer ' + guest['token']})
    assert merged.status_code == 200
    assert merged.json()['id'] == existing['id']
    with db_session() as db:
        assert db.execute('SELECT user_id FROM submissions WHERE id=?', (sub_id,)).fetchone()[0] == existing['id']
        assert db.execute('SELECT id FROM users WHERE id=?', (guest['id'],)).fetchone() is not None


def test_invalid_guest_credential_cannot_claim_data(provider):
    email = address()
    provider[1].add(email)
    response = verify(email, headers={'Authorization': 'Bearer forged'})
    assert response.status_code == 401
    assert email in provider[1]  # no provider exchange occurred


def test_verified_account_cannot_be_overwritten_by_another_email(provider):
    first_email, other_email = address(), address()
    provider[1].add(first_email)
    first = verify(first_email).json()
    provider[1].add(other_email)
    response = verify(other_email, headers={'Authorization': 'Bearer ' + first['token']})
    assert response.status_code == 409
    assert client.get('/api/me', headers={'Authorization': 'Bearer ' + first['token']}).json()['email'] == first_email


@pytest.mark.parametrize('user', [
    {'id': str(uuid.uuid4()), 'email': 'unexpected@example.com', 'email_confirmed_at': '2026-01-01'},
    {'id': str(uuid.uuid4()), 'email': 'user@example.com', 'email_confirmed_at': None},
    {'id': 'not-a-uuid', 'email': 'user@example.com', 'email_confirmed_at': '2026-01-01'},
])
def test_unconfirmed_or_mismatched_provider_identity_rejected(provider, monkeypatch, user):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'access_token': 'x', 'user': user}))
    monkeypatch.setattr(email_auth, 'provider_client', lambda: httpx.Client(transport=transport))
    assert verify('user@example.com').status_code == 400
    with db_session() as db:
        assert db.execute("SELECT id FROM users WHERE email='user@example.com'").fetchone() is None


def test_send_and_verify_rate_limits(provider, monkeypatch):
    email = address()
    assert client.post('/api/auth/request-code', json={'email': email}).status_code == 200
    assert client.post('/api/auth/request-code', json={'email': email}).status_code == 429
    monkeypatch.setattr(settings, 'email_verifications_per_hour', 1)
    assert verify(email, code='000000').status_code == 400
    assert verify(email).status_code == 429


def test_provider_errors_sanitized(provider, monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(500, json={'message': 'provider-key-secret'}))
    monkeypatch.setattr(email_auth, 'provider_client', lambda: httpx.Client(transport=transport))
    response = client.post('/api/auth/request-code', json={'email': address()})
    assert response.status_code == 503
    assert 'provider-key-secret' not in response.text


def test_email_configuration_required_and_guest_login_off(monkeypatch):
    monkeypatch.setattr(settings, 'allow_guest_login', False)
    assert client.post('/api/login', json={'handle': 'not_public'}).status_code == 403
    monkeypatch.setattr(settings, 'supabase_url', '')
    response = client.post('/api/auth/request-code', json={'email': address()})
    assert response.status_code == 503


def test_email_and_code_validation():
    assert client.post('/api/auth/request-code', json={'email': 'not-an-email'}).status_code == 422
    assert verify('user@example.com', code='wrong').status_code == 422
