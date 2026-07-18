import base64

from app.middleware import SimpleRateLimitMiddleware

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')

def test_upload_requires_authentication(client):
    response=client.post('/api/complaints/media',files={'files':('issue.png',PNG,'image/png')})
    assert response.status_code==401

def test_upload_rejects_extension_and_mime_spoofing(client,citizen):
    executable=client.post('/api/complaints/media',headers=citizen,files={'files':('payload.exe',b'MZ malicious payload','application/octet-stream')})
    assert executable.status_code==400
    spoofed=client.post('/api/complaints/media',headers=citizen,files={'files':('fake.png',b'<script>alert(1)</script>','image/png')})
    assert spoofed.status_code==400
    assert 'valid image' in spoofed.json()['detail'].lower()

def test_upload_enforces_file_count_and_size(client,citizen):
    six=[('files',(f'{i}.png',PNG,'image/png')) for i in range(6)]
    assert client.post('/api/complaints/media',headers=citizen,files=six).status_code==400
    oversized=b'0'*(8*1024*1024+1)
    assert client.post('/api/complaints/media',headers=citizen,files={'files':('large.png',oversized,'image/png')}).status_code==413

def test_security_headers_and_auth_rate_limit(client):
    response=client.get('/api/health',headers={'X-Request-ID':'security-test'})
    assert response.headers['x-request-id']=='security-test'
    assert response.headers['x-content-type-options']=='nosniff'
    assert response.headers['x-frame-options']=='DENY'
    assert response.headers['referrer-policy']=='strict-origin-when-cross-origin'
    SimpleRateLimitMiddleware.buckets.clear()
    payload={'email':'missing@example.com','password':'not-the-password'}
    responses=[client.post('/api/auth/login',json=payload) for _ in range(16)]
    assert responses[-1].status_code==429
    assert responses[-1].headers['retry-after']=='60'
    SimpleRateLimitMiddleware.buckets.clear()
