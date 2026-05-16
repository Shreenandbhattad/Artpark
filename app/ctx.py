import contextvars
import uuid

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")
query_id: contextvars.ContextVar[str] = contextvars.ContextVar("query_id", default="-")

def new_cid() -> str:
    return uuid.uuid4().hex[:12]
