import logging
import os
import time
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from prometheus_client import make_asgi_app
from pydantic import BaseModel
import cache
import ctx
import metrics
from config import DATA_ROOT, DEFAULT_DOMAIN, IMAGE_TAG, LOG_LEVEL
from data_loader import load_domain
from logging_setup import setup_logging
from providers import get_provider
from query_engine import answer

setup_logging(LOG_LEVEL)
log = logging.getLogger("app")

_STARTUP = time.time()

app = FastAPI(title="Tabular Analytics", version="0.1.0")
app.mount("/metrics", make_asgi_app())

DOMAIN = os.environ.get("DOMAIN", DEFAULT_DOMAIN)
DATA, DATA_VERSION = load_domain(DOMAIN, DATA_ROOT)
cache.set_version(DATA_VERSION)
PROVIDER = get_provider()

import time as _t
metrics.data_version_info.labels(domain=DOMAIN).set(_t.time())

log.info("startup complete", extra={"domain": DOMAIN, "version": DATA_VERSION, "provider": type(PROVIDER).__name__})


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID") or ctx.new_cid()
    qid = ctx.new_cid()
    ctx.correlation_id.set(cid)
    ctx.query_id.set(qid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    dur = time.perf_counter() - t0
    endpoint = request.url.path
    metrics.request_duration_seconds.labels(endpoint=endpoint).observe(dur)
    metrics.requests_total.labels(endpoint=endpoint, status_code=str(response.status_code)).inc()
    return response


class QueryRequest(BaseModel):
    question: str


@app.get("/health")
def health() -> dict[str, Any]:
    data_ok = bool(DATA)
    dq = DATA.get("_data_quality", [{}])
    dq_summary = dq[0] if dq else {}

    checks = {
        "data": {
            "status": "ok" if data_ok else "degraded",
            "domain": DOMAIN,
            "tables": [k for k in DATA if not k.startswith("_")],
            "total_rows": sum(len(v) for k, v in DATA.items() if not k.startswith("_")),
            "version": DATA_VERSION
        },
        "cache": {
            "status": "ok",
            "entries": cache.size()
        },
        "llm_provider": {
            "status": "ok",
            "provider": type(PROVIDER).__name__
        },
        "data_quality": dq_summary
    }

    overall = "ok" if all(
        v.get("status") == "ok"
        for v in checks.values()
        if isinstance(v, dict) and "status" in v
    ) else "degraded"

    return {
        "status": overall,
        "timestamp": time.time(),
        "image_tag": IMAGE_TAG,
        "uptime_seconds": round(time.time() - _STARTUP, 1),
        "checks": checks
    }


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": IMAGE_TAG, "git_sha": IMAGE_TAG}


@app.post("/query")
def query(req: QueryRequest) -> dict[str, Any]:
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question required")
    try:
        result = answer(req.question, DATA, PROVIDER, DOMAIN)
    except Exception as e:
        log.error("query failed", extra={"err": str(e)})
        raise HTTPException(status_code=500, detail="query failed")
    return result
