import time
from fastapi import Request


async def record_latency(request: Request, call_next):
    t0 = time.monotonic()
    response = await call_next(request)
    response.headers["x-latency-ms"] = str(int((time.monotonic() - t0) * 1000))
    return response
