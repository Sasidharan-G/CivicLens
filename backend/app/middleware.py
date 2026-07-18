import time,uuid
from collections import defaultdict,deque
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request:Request,call_next):
        request.state.request_id=request.headers.get("X-Request-ID") or str(uuid.uuid4());response=await call_next(request)
        response.headers.update({"X-Request-ID":request.state.request_id,"X-Content-Type-Options":"nosniff","X-Frame-Options":"DENY","Referrer-Policy":"strict-origin-when-cross-origin","Permissions-Policy":"camera=(self), geolocation=(self)","Cache-Control":"no-store" if request.url.path.startswith("/api/auth") else "no-cache"})
        return response

class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    buckets:dict[str,deque]=defaultdict(deque)
    async def dispatch(self,request:Request,call_next):
        if request.url.path.startswith("/api/auth/"):
            key=f"{request.client.host if request.client else 'unknown'}:{request.url.path}";now=time.monotonic();bucket=self.buckets[key]
            while bucket and bucket[0]<now-60:bucket.popleft()
            limit=15 if request.method=="POST" else 60
            if len(bucket)>=limit:return JSONResponse({"detail":"Too many requests. Please try again shortly."},429,headers={"Retry-After":"60"})
            bucket.append(now)
        return await call_next(request)
