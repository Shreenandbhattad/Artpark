# Architecture

## The three choices

### 1. What the LLM sees

The LLM sees table metadata and computation results, not raw rows.

Pass 1 (intent extraction): the LLM receives a JSON summary of each table - column names, row count, and per-column min/max/mean. It returns a structured query spec describing which table to query, what filters to apply, what aggregation to compute, and what column to target.

Pass 2 (answer formatting): the LLM receives the Python-computed result (a scalar or small list) and formats a natural-language answer with citations.

Why not raw rows? The original code sent up to 200 raw rows per table. At scale this wastes context, leaks intermediate data to a third-party API, and lets the LLM compute the answer itself which makes results non-reproducible. With the two-pass approach, the LLM is a query planner and answer formatter, not a calculator.

Trade-off: a smart LLM would sometimes produce a better answer with full row access (e.g. spotting an outlier). We accept this because reproducibility and auditability are higher priorities for a data-analytics service than answer creativity.

### 2. Where deterministic compute lives

All numeric computation lives in Python (query_engine._execute), never in the LLM.

_execute applies filters (exact match or [min, max] range), then runs the requested aggregation (mean, sum, min, max, list) on the target column. The same query spec on the same data always produces the same result.

Reproducibility: the query spec is logged alongside the answer. To reproduce a result, replay the spec against the same data version. The data version (SHA256 of CSV mtimes) is in /health and in every structured log line.

Day-2 resilience: if the curveball is "add a new aggregation type" or "add percentile support", only _execute changes. The LLM prompt and all infrastructure are unchanged.

### 3. What is cacheable, at which layer, with what invalidation rule

Cached: the final answer for each query, keyed by SHA256(domain + data_version + normalised_question).

Not cached: the /health response (must reflect live state), the data load itself (loaded once at startup, stored in process memory), and the reconciliation result (stored in the tables dict, recomputed only on restart).

Invalidation rule: the cache key includes data_version, which is a hash of the CSV modification times. When data changes and the service restarts, data_version changes, the cache key changes, and stale entries are unreachable. TTL=3600s provides a secondary eviction path in case the version hash does not change (e.g. CSV overwritten with identical content).

Layer: in-process Python dict. Simpler than Redis, sufficient for single-worker deployment. The single-worker constraint is documented. The cache interface (get, put, make_key, set_version) is an abstraction boundary: replace the dict with redis.get/set to scale horizontally without changing any other module.

---

## System diagram

```
Browser / API Client
        |
        | HTTPS (443) or HTTP (80)
        v
  nginx (TLS termination)
        |  X-Correlation-ID forwarded
        |  /metrics blocked externally
        v
  FastAPI (port 8000)
        |
        +-- middleware: correlation_id (ctx.ContextVar)
        +-- middleware: prometheus timing
        |
        +-- GET /health
        |       checks: data loaded, cache size, provider type, data_quality summary
        |
        +-- GET /metrics  (Prometheus scrapes this directly, Docker network only)
        |
        +-- POST /query
                |
                +-- cache.get(sha256(q + domain + version))
                |       hit: return immediately
                |
                +-- Pass 1: LLM(metadata summary) -> query_spec JSON
                |       timed: analytics_llm_duration_seconds{pass_num="1"}
                |
                +-- _execute(query_spec, tables) -> scalar result
                |       pure Python, deterministic, no LLM
                |
                +-- Pass 2: LLM(result) -> formatted answer
                |       timed: analytics_llm_duration_seconds{pass_num="2"}
                |
                +-- cache.put(key, answer)
                +-- emit: analytics_response_quality_total{quality="full|degraded|error"}

Data load (at startup):
  data/environment/*.csv
        |
        +-- station_obs_local  (temp_c, humidity 0-100)
        +-- weather_api_export (temp_f, humidity 0-1)  -> reconciler normalises units
        +-- stations           (registry)
        |
        reconciler.reconcile()
        |
        +-- reconciled_obs     (canonical, local-primary)
        +-- _data_quality      (disagreement summary, surfaced in /health and query responses)

Observability:
  stdout (JSON)  -> promtail -> Loki <- Grafana (logs panel)
  /metrics       -> Prometheus        <- Grafana (10 metric panels)
  Prometheus     -> alerts.yml (ServiceDown, HighDegradedResponseRate, HighQueryLatency)
```

---

## Data quality rule (environment domain)

When the local station feed and the API export disagree on the same (station_id, date):

1. Normalize API to canonical units: temperature F to C via (f-32)*5/9, humidity 0-1 to 0-100.
2. Compare. Tolerance: temperature +-0.3 degrees C, humidity +-1 percentage point. The tolerance covers rounding from the float conversion. The 0.3 degree margin handles sensor precision differences, not conversion slop.
3. If outside tolerance: record the disagreement with both values and delta. Use the local feed as the primary value since it has no conversion loss.
4. Never pick silently. The disagreement count is in /health["checks"]["data_quality"] and in any query response as data_quality_warning.
5. Emit analytics_data_disagreements_total{field, station} for each disagreed field.

---

## The one surprise

Failure mode: LLM response degradation is invisible in standard metrics.

The original code falls back to wrapping the raw LLM output as a plain text answer when JSON parsing fails. This returns HTTP 200 with value: null. Standard monitoring (error rate, status codes) shows zero errors. Users see a soft failure - they get words but no number.

This happens when: the LLM is rate-limited and returns a partial response, the model changes and the JSON schema drifts, or the question triggers a response that exceeds the context window.

Fix implemented:

Every query response now includes response_quality: "full" or "degraded" or "error". The query engine sets this before returning and emits analytics_response_quality_total{quality=...}. The Grafana dashboard has a Degraded Response Rate stat panel. The HighDegradedResponseRate alert fires when degraded / total > 5% for 2 minutes.

This turns a previously invisible failure mode into a pageable signal.
