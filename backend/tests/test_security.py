import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.database import db_session, init_db
from app.main import app
from app.seed_data import seed
from app.security import token_hash

init_db()
seed()
client = TestClient(app)


def guest():
    res = client.post('/api/login', json={'handle': 'g_' + uuid.uuid4().hex[:16]})
    assert res.status_code == 200
    body = res.json()
    return body, {'Authorization': 'Bearer ' + body['token']}


def photo():
    buf = io.BytesIO()
    Image.new('RGB', (16, 16), 'white').save(buf, format='PNG')
    return buf.getvalue()


def upload(headers, content=None, mime='image/png', filename='room.png'):
    return client.post('/api/submissions', headers=headers,
                       data={'budget': '300', 'style': 'modern'},
                       files={'image': (filename, photo() if content is None else content, mime)})


@pytest.mark.parametrize('headers', [{}, {'X-User-Id': '1'}, {'Authorization': 'Bearer invalid'}])
def test_protected_routes_require_valid_session(headers):
    for method, url in [('get', '/api/me'), ('get', '/api/designs'),
                        ('get', '/api/submissions/1'), ('post', '/api/generate/1'),
                        ('post', '/api/designs/1/save'), ('delete', '/api/designs/1/save'),
                        ('get', '/api/media/1/room'), ('get', '/api/media/1/generated'),
                        ('post', '/api/logout')]:
        assert getattr(client, method)(url, headers=headers).status_code == 401
    assert upload(headers).status_code == 401


def test_ownership_and_private_media():
    owner, headers = guest()
    _, attacker = guest()
    response = upload({**headers, 'X-User-Id': '999999'}, filename='../../escape.html')
    assert response.status_code == 200
    sub = response.json()
    assert sub['user_id'] == owner['id']
    assert sub['room_image_path'] == f"/api/media/{sub['id']}/room"
    assert client.get(sub['room_image_path'], headers=headers).status_code == 200
    generated = client.post(f"/api/generate/{sub['id']}", headers=headers)
    assert generated.status_code == 200
    generated_path = generated.json()['generated_image_path']
    assert generated_path == f"/api/media/{sub['id']}/generated"
    for method, url in [('get', f"/api/submissions/{sub['id']}"),
                        ('post', f"/api/generate/{sub['id']}"),
                        ('post', f"/api/designs/{sub['id']}/save"),
                        ('delete', f"/api/designs/{sub['id']}/save"),
                        ('get', sub['room_image_path']), ('get', generated_path)]:
        assert getattr(client, method)(url, headers=attacker).status_code == 404
    assert client.get('/api/designs', headers=attacker).json() == []
    media = client.get(generated_path, headers=headers)
    assert media.status_code == 200
    assert 'no-store' in media.headers['cache-control']
    with db_session() as db:
        stored = db.execute('SELECT room_image_path FROM submissions WHERE id=?', (sub['id'],)).fetchone()[0]
    assert Path(stored).parent.resolve() == Path(settings.upload_dir).resolve()
    assert Path(stored).suffix == '.jpg'
    assert client.get('/media/' + Path(stored).name).status_code == 404
    assert client.post('/api/login', json={'handle': owner['handle'].upper()}).status_code == 409


def test_tokens_hashed_expired_and_revoked():
    account, headers = guest()
    with db_session() as db:
        stored = db.execute('SELECT token_hash FROM sessions WHERE user_id=?', (account['id'],)).fetchone()[0]
        assert stored == token_hash(account['token']) and stored != account['token']
        db.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00' WHERE user_id=?", (account['id'],))
    assert client.get('/api/me', headers=headers).status_code == 401
    account, headers = guest()
    assert client.get('/api/me', headers=headers).json()['id'] == account['id']
    assert client.post('/api/logout', headers=headers).status_code == 204
    assert client.get('/api/me', headers=headers).status_code == 401


def test_upload_validation_and_metadata(monkeypatch):
    _, headers = guest()
    assert upload(headers, b'not an image').status_code == 400
    assert upload(headers, photo(), 'image/jpeg').status_code == 400
    assert upload(headers, photo(), 'text/html').status_code == 400
    monkeypatch.setattr(settings, 'max_upload_bytes', 20)
    assert upload(headers).status_code == 413
    monkeypatch.setattr(settings, 'max_upload_bytes', 8 * 1024 * 1024)
    monkeypatch.setattr(settings, 'max_image_pixels', 10)
    assert upload(headers).status_code == 400
    monkeypatch.setattr(settings, 'max_image_pixels', 20_000_000)
    buf = io.BytesIO()
    from PIL.PngImagePlugin import PngInfo
    metadata = PngInfo()
    metadata.add_text('private', 'sensitive room information')
    Image.new('RGB', (16, 16)).save(buf, format='PNG', pnginfo=metadata)
    sub = upload(headers, buf.getvalue()).json()
    image = client.get(sub['room_image_path'], headers=headers)
    with Image.open(io.BytesIO(image.content)) as decoded:
        assert not decoded.getexif()
        assert 'private' not in decoded.info


def test_login_rate_limit_includes_failed_handle_attempts(monkeypatch):
    monkeypatch.setattr(settings, 'login_attempts_per_hour', 2)
    async def isolated_client(scope, receive, send):
        if scope['type'] == 'http':
            scope = {**scope, 'client': ('192.0.2.1', 1234)}
        await app(scope, receive, send)

    with TestClient(isolated_client) as isolated:
        handle = 'rate_' + uuid.uuid4().hex[:10]
        assert isolated.post('/api/login', json={'handle': handle}).status_code == 200
        assert isolated.post('/api/login', json={'handle': handle}).status_code == 409
        response = isolated.post('/api/login', json={'handle': 'another_handle'})
        assert response.status_code == 429
        assert response.headers['retry-after'] == '3600'


def test_generation_and_upload_limits(monkeypatch):
    _, headers = guest()
    first = upload(headers).json()
    second = upload(headers).json()
    monkeypatch.setattr(settings, 'generations_per_hour', 1)
    assert client.post(f"/api/generate/{first['id']}", headers=headers).status_code == 200
    assert client.post(f"/api/generate/{first['id']}", headers=headers).status_code == 200
    assert client.post(f"/api/generate/{second['id']}", headers=headers).status_code == 429
    monkeypatch.setattr(settings, 'uploads_per_hour', 2)
    assert upload(headers).status_code == 429


def test_legacy_accounts_and_ownerless_resources_stay_private():
    handle = 'legacy_' + uuid.uuid4().hex[:10]
    with db_session() as db:
        old = db.execute("INSERT INTO users(handle, created_at) VALUES (?, '2020-01-01')", (handle,)).lastrowid
        ids = []
        for user_id in [old, None]:
            ids.append(db.execute(
                "INSERT INTO submissions(created_at, room_image_path, budget, style, user_id) "
                "VALUES ('2020-01-01', 'missing.jpg', 100, 'modern', ?)", (user_id,)).lastrowid)
    assert client.post('/api/login', json={'handle': handle}).status_code == 409
    _, headers = guest()
    for sub_id in ids:
        assert client.get(f'/api/submissions/{sub_id}', headers=headers).status_code == 404
        assert client.post(f'/api/designs/{sub_id}/save', headers=headers).status_code == 404


def test_media_path_cannot_escape_upload_root():
    _, headers = guest()
    sub = upload(headers).json()
    with db_session() as db:
        db.execute('UPDATE submissions SET room_image_path=? WHERE id=?',
                   (str(Path(__file__).resolve()), sub['id']))
    assert client.get(sub['room_image_path'], headers=headers).status_code == 404


def test_cors_rejects_unconfigured_origin():
    response = client.options('/api/designs', headers={
        'Origin': 'http://localhost:9999', 'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'Authorization'})
    assert response.status_code == 400


def test_request_body_limit_before_multipart_parsing(monkeypatch):
    _, headers = guest()
    monkeypatch.setattr(settings, 'max_upload_bytes', 10)
    assert upload(headers, b'x' * 70000).status_code == 413
    # Streamed bodies have no Content-Length; the same bound still applies.
    streamed = client.post('/api/submissions', headers={**headers, 'Content-Type': 'application/octet-stream'},
                           content=iter([b'x' * 35000, b'x' * 35000]))
    assert streamed.status_code == 413
    assert client.post('/api/login', content=b'x' * 70000).status_code == 413


def test_provider_error_details_are_not_exposed(monkeypatch):
    from app.routers import generate
    _, headers = guest()
    sub = upload(headers).json()

    def fail():
        raise RuntimeError('secret-api-key internal-path confidential-notes')

    monkeypatch.setattr(generate, 'get_recommender', fail)
    response = client.post(f"/api/generate/{sub['id']}", headers=headers)
    assert response.status_code == 502
    assert 'secret-api-key' not in response.text


def test_ai_request_logging_omits_user_notes_by_default(caplog):
    from app.services.gemini_logging import log_gemini_request
    import logging
    with caplog.at_level(logging.INFO, logger='app.services.gemini'):
        log_gemini_request(label='test', model='test', contents='confidential-notes', config=object())
    assert 'confidential-notes' not in caplog.text
