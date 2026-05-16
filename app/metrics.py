from prometheus_client import Counter, Histogram, Gauge, REGISTRY

def _counter(name, doc, labels):
    try:
        return Counter(name, doc, labels)
    except ValueError:
        return REGISTRY._names_to_collectors.get(name)

def _histogram(name, doc, labels, buckets):
    try:
        return Histogram(name, doc, labels, buckets=buckets)
    except ValueError:
        return REGISTRY._names_to_collectors.get(name)

def _gauge(name, doc, labels):
    try:
        return Gauge(name, doc, labels)
    except ValueError:
        return REGISTRY._names_to_collectors.get(name)


requests_total = _counter(
    "analytics_requests_total",
    "HTTP requests by endpoint and status",
    ["endpoint", "status_code"]
)

request_duration_seconds = _histogram(
    "analytics_request_duration_seconds",
    "End-to-end request latency",
    ["endpoint"],
    [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

llm_duration_seconds = _histogram(
    "analytics_llm_duration_seconds",
    "LLM call time per pass",
    ["pass_num", "provider"],
    [0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

cache_hits_total = _counter(
    "analytics_cache_hits_total",
    "Cache outcomes",
    ["outcome"]
)

response_quality_total = _counter(
    "analytics_response_quality_total",
    "LLM response quality",
    ["quality"]
)

data_disagreements_total = _counter(
    "analytics_data_disagreements_total",
    "Source disagreements per field and station",
    ["field", "station"]
)

data_version_info = _gauge(
    "analytics_data_version_info",
    "Unix ts of last data reload",
    ["domain"]
)
