"""Post-deployment smoke check using only the Python standard library."""
import json
import os
import sys
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

base=os.environ.get("API_BASE_URL","").rstrip("/")
if not base:raise SystemExit("Set API_BASE_URL to the deployed backend origin")
def get(path):
    try:
        with urlopen(Request(base+path,headers={"User-Agent":"CivicLens-release-smoke/1.0"}),timeout=20) as response:
            assert response.status==200,f"{path} returned {response.status}";return json.load(response)
    except (HTTPError,URLError,TimeoutError,AssertionError) as error:raise SystemExit(f"Smoke check failed for {path}: {error}") from error
health=get("/api/health");ready=get("/api/ready");analytics=get("/api/public/analytics")
assert health.get("status")=="healthy" and health.get("database")=="connected"
assert ready.get("status")=="ready" and not ready.get("errors")
assert isinstance(analytics.get("total"),int)
print("CivicLens release smoke check passed",{"environment":ready.get("environment"),"storage":health.get("storage"),"reports":analytics.get("total")})
