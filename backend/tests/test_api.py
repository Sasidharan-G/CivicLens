def payload(lat=13.08,lon=80.27): return {'title':'Large pothole near school','description':'A dangerous road pothole requires urgent attention','category':'Pothole','severity':'high','department':'Roads Department','latitude':lat,'longitude':lon,'address':'Chennai'}
def test_health(client): assert client.get('/api/health').json()['status']=='healthy'
def test_deployment_readiness_detects_unsafe_production_config(client,monkeypatch):
    from app.config import settings
    assert client.get('/api/ready').json()['status']=='ready'
    monkeypatch.setattr(settings,'environment','production');monkeypatch.setattr(settings,'database_url','sqlite:///unsafe.db');monkeypatch.setattr(settings,'jwt_secret_key','development-only-change-me');monkeypatch.setattr(settings,'cors_origins','http://localhost:5173');monkeypatch.setattr(settings,'app_base_url','http://localhost:5173');monkeypatch.setattr(settings,'internal_jobs_secret',None)
    response=client.get('/api/ready');assert response.status_code==503;body=response.json();assert body['status']=='not_ready';assert len(body['errors'])>=5
def test_phase_eight_analytics_filters_privacy_and_exports(client,citizen,admin):
    client.post('/api/complaints',json={**payload(),"locality":"Adyar","ward":"Ward 101"},headers=citizen)
    public=client.get('/api/public/analytics?locality=Adyar').json();assert public['total']==1;assert public['ward_health'][0]['ward']=='Ward 101';assert 'department_performance' not in public;assert 'category_forecast' in public
    private=client.get('/api/admin/analytics?locality=Adyar',headers=admin);assert private.status_code==200;assert 'department_performance' in private.json()
    assert client.get('/api/admin/analytics').status_code==401
    csv_export=client.get('/api/admin/analytics/export?format=csv',headers=admin);assert csv_export.status_code==200;assert 'text/csv' in csv_export.headers['content-type'];assert 'civic_health_score' in csv_export.text
    pdf_export=client.get('/api/admin/analytics/export?format=pdf',headers=admin);assert pdf_export.status_code==200;assert pdf_export.content.startswith(b'%PDF')
def test_register_login_and_protection(client):
    x={'full_name':'Citizen One','email':'one@example.com','password':'Password123'}
    registered=client.post('/api/auth/register',json=x);assert registered.status_code==201;assert registered.json()['refresh_token']
    logged_in=client.post('/api/auth/login',json={'email':x['email'],'password':x['password']});assert logged_in.status_code==200
    refreshed=client.post('/api/auth/refresh',json={'refresh_token':logged_in.json()['refresh_token']});assert refreshed.status_code==200
    assert client.post('/api/auth/refresh',json={'refresh_token':logged_in.json()['refresh_token']}).status_code==401
    assert client.get('/api/auth/me').status_code==401
    assert registered.headers['x-content-type-options']=='nosniff'
def test_complaint_similarity_support_and_duplicate(client,citizen):
    c=client.post('/api/complaints',json=payload(),headers=citizen);assert c.status_code==201;cid=c.json()['id']
    s=client.post('/api/complaints/similar',json={**payload(13.0802,80.2702)},headers=citizen);assert len(s.json())==1
    assert client.post(f'/api/complaints/{cid}/support',headers=citizen).status_code==200
    assert client.post(f'/api/complaints/{cid}/support',headers=citizen).status_code==409
def test_admin_authorization_and_status(client,citizen,admin):
    cid=client.post('/api/complaints',json=payload(),headers=citizen).json()['id']
    assert client.patch(f'/api/admin/complaints/{cid}/status',json={'status':'verified','note':'Checked'},headers=citizen).status_code==403
    r=client.patch(f'/api/admin/complaints/{cid}/status',json={'status':'verified','note':'Checked'},headers=admin);assert r.status_code==200;assert r.json()['status']=='verified'
    notifications=client.get('/api/notifications',headers=citizen).json();assert notifications['unread']==1;notification=notifications['items'][0]
    assert client.patch(f"/api/notifications/{notification['id']}/read",headers=citizen).status_code==200
    assert client.get('/api/notifications',headers=citizen).json()['unread']==0
def test_letter_fallback(client,citizen):
    r=client.post('/api/complaints/generate-letter',headers=citizen,json={'citizen_name':'Test Citizen','category':'Pothole','description':'Road damage needs attention','address':'Chennai','severity':'medium','department':'Roads'})
    assert r.status_code==200;assert 'Test Citizen' in r.json()['letter'];assert r.json()['is_demo'] is True
def test_password_reset_and_email_verification(client):
    client.post('/api/auth/register',json={'full_name':'Reset User','email':'reset@example.com','password':'Password123'})
    forgot=client.post('/api/auth/forgot-password',json={'email':'reset@example.com'}).json();assert forgot['development_token']
    assert client.post('/api/auth/reset-password',json={'token':forgot['development_token'],'new_password':'NewPassword123'}).status_code==200
    assert client.post('/api/auth/login',json={'email':'reset@example.com','password':'NewPassword123'}).status_code==200
    verify=client.post('/api/auth/request-verification',json={'email':'reset@example.com'}).json();assert client.post('/api/auth/verify-email',json={'token':verify['development_token']}).status_code==200
def test_multi_media_privacy_guidance_and_resolution_evidence(client,citizen,admin):
    import base64
    body={**payload(),"is_anonymous":True,"hide_exact_location":True,"locality":"Adyar","media":[{"url":"/uploads/one.jpg","public_id":"one.jpg","mime_type":"image/jpeg"},{"url":"/uploads/two.jpg","public_id":"two.jpg","mime_type":"image/jpeg"}]}
    created=client.post('/api/complaints',json=body,headers=citizen);assert created.status_code==201;item=created.json();assert len(item['media'])==2;assert item['reporter_id'] is None;assert item['latitude']==round(body['latitude'],3)
    detail=client.get(f"/api/complaints/{item['id']}").json();assert detail['reporter']['full_name']=='Anonymous citizen'
    guide=client.get('/api/categories/Pothole/guidance').json();assert guide['department']=='Roads Department';assert guide['questions']
    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
    evidence=client.post(f"/api/admin/complaints/{item['id']}/resolution-evidence",headers=admin,files={'file':('after.png',png,'image/png')});assert evidence.status_code==201;assert evidence.json()['media_type']=='resolution'
def test_complete_authority_sla_resolution_and_reopen_workflow(client,citizen,admin):
    import base64
    item=client.post('/api/complaints',json=payload(),headers=citizen).json();cid=item['id']
    assert client.patch(f'/api/admin/complaints/{cid}/status',json={'status':'verified','note':'Location verified'},headers=admin).status_code==200
    officer=client.get('/api/admin/officers',headers=admin).json()[0]
    assigned=client.patch(f'/api/admin/complaints/{cid}/assign',json={'assigned_to_id':officer['id'],'department':'Roads Department'},headers=admin);assert assigned.status_code==200;assert assigned.json()['sla_due_at']
    assert client.patch(f'/api/admin/complaints/{cid}/status',json={'status':'in_progress','note':'Officer inspection started'},headers=admin).status_code==200
    assert client.post(f'/api/admin/complaints/{cid}/internal-notes',json={'content':'Contractor team informed privately'},headers=admin).status_code==201
    assert len(client.get(f'/api/admin/complaints/{cid}/internal-notes',headers=admin).json())==1
    assert client.patch(f'/api/admin/complaints/{cid}/status',json={'status':'resolved','note':'Work completed'},headers=admin).status_code==409
    assert client.patch(f'/api/admin/complaints/{cid}/resolution',json={'summary':'Pothole filled and road surface compacted'},headers=admin).status_code==200
    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
    assert client.post(f'/api/admin/complaints/{cid}/resolution-evidence',headers=admin,files={'file':('after.png',png,'image/png')}).status_code==201
    resolved=client.patch(f'/api/admin/complaints/{cid}/status',json={'status':'resolved','note':'Work completed with evidence'},headers=admin);assert resolved.status_code==200
    assert client.post(f'/api/complaints/{cid}/confirm-resolution',headers=citizen).status_code==200
    reopened=client.post(f'/api/complaints/{cid}/reopen',json={'reason':'The repaired surface has failed again'},headers=citizen);assert reopened.status_code==200;assert reopened.json()['status']=='in_progress';assert reopened.json()['reopened_count']==1

def test_smart_duplicate_signals_safe_merge_and_cluster(client,citizen,admin):
    primary=client.post('/api/complaints',json=payload(),headers=citizen).json();duplicate=client.post('/api/complaints',json={**payload(13.0801,80.2701),'title':'Deep pothole beside school gate','description':'Another view of dangerous road damage at the same school entrance'},headers=citizen).json()
    similar=client.post('/api/complaints/similar',json={**payload(13.0802,80.2702)},headers=citizen).json()
    assert similar and 'semantic' in similar[0]['signals'];assert similar[0]['recommendation'] in {'support_existing','review'}
    assert client.post(f"/api/complaints/{primary['id']}/support",headers=citizen).status_code==200
    assert client.post(f"/api/complaints/{duplicate['id']}/support",headers=citizen).status_code==200
    assert client.post(f"/api/complaints/{duplicate['id']}/comments",json={'content':'Same location and same road damage'},headers=citizen).status_code==201
    merged=client.post(f"/api/admin/complaints/{primary['id']}/merge",json={'duplicate_id':duplicate['id'],'note':'Verified duplicate'},headers=admin)
    assert merged.status_code==200;assert merged.json()['primary']['support_count']==1
    detail=client.get(f"/api/complaints/{primary['id']}").json();assert len(detail['comments'])==1
    clusters=client.get('/api/admin/duplicate-clusters',headers=admin).json();assert len(clusters)==1;assert clusters[0]['member_count']==2

def test_notification_preferences_and_push_subscription(client,citizen):
    prefs=client.get('/api/notification-preferences',headers=citizen);assert prefs.status_code==200;assert prefs.json()['status_alerts'] is True
    updated=client.request('PUT','/api/notification-preferences',headers=citizen,json={"email_enabled":False,"push_enabled":False,"whatsapp_enabled":False,"status_alerts":True,"nearby_critical_alerts":False,"ward_digest":False});assert updated.status_code==200;assert updated.json()['email_enabled'] is False
    subscribed=client.post('/api/push-subscriptions',headers=citizen,json={"endpoint":"https://push.example.test/subscription/123","p256dh":"test-public-key","auth":"test-auth-key"});assert subscribed.status_code==201

def test_pii_moderation_suspension_and_appeal(client,citizen,admin):
    complaint=client.post('/api/complaints',json=payload(),headers=citizen).json();comment=client.post(f"/api/complaints/{complaint['id']}/comments",headers=citizen,json={'content':'Contact resident at test.person@example.com about road repair'}).json();assert '[email hidden]' in comment['content']
    report=client.post('/api/moderation/reports',headers=citizen,json={'target_type':'comment','target_id':comment['id'],'reason':'privacy','details':'Personal contact information'});assert report.status_code==201
    queue=client.get('/api/admin/moderation',headers=admin).json();assert len(queue['reports'])==1
    reviewed=client.patch(f"/api/admin/moderation/reports/{report.json()['id']}",headers=admin,json={'action':'suspend','note':'Repeated privacy violation'});assert reviewed.status_code==200
    assert client.get('/api/auth/me',headers=citizen).status_code==403
    appeal=client.post('/api/moderation/appeals',headers=citizen,json={'message':'I understand the privacy rule and will not repeat this issue.'});assert appeal.status_code==201
    appeals=client.get('/api/admin/moderation',headers=admin).json()['appeals'];assert len(appeals)==1
    assert client.patch(f"/api/admin/moderation/appeals/{appeal.json()['id']}",headers=admin,json={'approve':True,'note':'First appeal accepted'}).status_code==200
    assert client.get('/api/auth/me',headers=citizen).status_code==200
