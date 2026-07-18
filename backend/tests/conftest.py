import os
os.environ["DATABASE_URL"]="sqlite:///./test_civiclens.db"
os.environ["JWT_SECRET_KEY"]="test-secret"
import asyncio
import httpx
import pytest
from app.database import Base,engine
from app.main import app

@pytest.fixture(autouse=True)
def clean():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

class ASGIClient:
    def request(self,method,path,**kwargs):
        async def call():
            transport=httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport,base_url="http://test") as client:
                return await client.request(method,path,**kwargs)
        return asyncio.run(call())
    def get(self,path,**kwargs): return self.request("GET",path,**kwargs)
    def post(self,path,**kwargs): return self.request("POST",path,**kwargs)
    def patch(self,path,**kwargs): return self.request("PATCH",path,**kwargs)
    def delete(self,path,**kwargs): return self.request("DELETE",path,**kwargs)

@pytest.fixture
def client(): return ASGIClient()

@pytest.fixture
def citizen(client):
    r=client.post('/api/auth/register',json={'full_name':'Test Citizen','email':'test@example.com','password':'Password123'})
    return {'Authorization':'Bearer '+r.json()['access_token']}

@pytest.fixture
def admin(client):
    from app.database import SessionLocal
    from app.models import User,Role
    from app.security import hash_password,create_token
    db=SessionLocal();u=User(full_name='Admin',email='admin@test.com',password_hash=hash_password('Password123'),role=Role.admin);db.add(u);db.commit();db.refresh(u);token=create_token(u);db.close()
    return {'Authorization':'Bearer '+token}
