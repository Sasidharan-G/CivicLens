import os
import subprocess
import sys

def test_alembic_upgrades_clean_database_to_head(tmp_path):
    database=tmp_path/'migration-test.db'
    env={**os.environ,'DATABASE_URL':f'sqlite:///{database.as_posix()}','JWT_SECRET_KEY':'migration-test-secret'}
    result=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=os.path.dirname(os.path.dirname(__file__)),env=env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    current=subprocess.run([sys.executable,'-m','alembic','current'],cwd=os.path.dirname(os.path.dirname(__file__)),env=env,capture_output=True,text=True,timeout=30)
    assert current.returncode==0
    assert '0007 (head)' in current.stdout
