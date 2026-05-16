import json
import logging
import time
from typing import Any

import cache
import metrics
from config import DEFAULT_DOMAIN
from providers import LLMProvider

log = logging.getLogger("query")

PASS1_SYSTEM = """You are a query planner for tabular data. Given table metadata and a user question, return a JSON query spec:
{
  "table": "<table_name>",
  "filters": {"<col>": "<val_or_[min,max]>"},
  "aggregate": "mean|sum|min|max|list",
  "target_col": "<column_to_aggregate>",
  "group_by": "<column_or_null>"
}
Only return valid JSON. If the question cannot be answered, return {"error": "<reason>"}.
Prefer the reconciled_obs table for environment data. Use station_id values like S001, S002, S003."""

PASS2_SYSTEM = """You format a computation result into a cited natural-language answer.
Return JSON with exactly these keys:
  answer: str
  value: number or null
  chart: {"type": "line|bar|table", "x": str, "y": str} or null
  citations: [str]
  response_quality: "full" if value is not null and result is meaningful, else "degraded"
Be concise. Cite the table and row count used."""


def _summarize(tables: dict) -> dict:
    out = {}
    for name, rows in tables.items():
        if name.startswith("_"):  # internal
            continue
        if not rows:
            out[name] = {"rows": 0, "columns": []}
            continue
        cols = list(rows[0].keys())
        num_cols = [c for c in cols if isinstance(rows[0].get(c), (int, float))]
        stats = {}
        for c in num_cols:
            vals = [r[c] for r in rows if isinstance(r.get(c), (int, float))]
            if vals:
                stats[c] = {
                    "min": round(min(vals), 3),
                    "max": round(max(vals), 3),
                    "mean": round(sum(vals) / len(vals), 3)
                }
        out[name] = {"rows": len(rows), "columns": cols, "stats": stats}
    return out


def _execute(spec: dict, tables: dict) -> dict:
    table_name = spec.get("table", "")
    rows = list(tables.get(table_name, []))  # copy

    for col, val in spec.get("filters", {}).items():
        if isinstance(val, list) and len(val) == 2:
            rows = [r for r in rows if str(r.get(col, "")) >= str(val[0]) and str(r.get(col, "")) <= str(val[1])]
        else:
            rows = [r for r in rows if str(r.get(col, "")) == str(val)]

    target = spec.get("target_col", "")
    vals = [r[target] for r in rows if isinstance(r.get(target), (int, float))]

    agg = spec.get("aggregate", "mean")
    if not vals:
        result = None
    elif agg == "mean":
        result = round(sum(vals) / len(vals), 4)
    elif agg == "sum":
        result = round(sum(vals), 4)
    elif agg == "min":
        result = min(vals)
    elif agg == "max":
        result = max(vals)
    else:
        result = vals[:50]  # list, capped

    group_by = spec.get("group_by")
    grouped = None
    if group_by and rows:
        grp: dict[str, list] = {}
        for r in rows:
            k = str(r.get(group_by, ""))
            grp.setdefault(k, [])
            if isinstance(r.get(target), (int, float)):
                grp[k].append(r[target])
        grouped = {k: round(sum(v)/len(v), 4) if agg == "mean" else round(sum(v), 4) for k, v in grp.items() if v}

    return {
        "rows_matched": len(rows),
        "result": result,
        "grouped": grouped,
        "spec": spec
    }


def answer(question: str, tables: dict[str, list[dict[str, Any]]], provider: LLMProvider, domain: str = DEFAULT_DOMAIN) -> dict[str, Any]:
    t_total = time.perf_counter()

    cache_key = cache.make_key(question, domain)
    cached = cache.get(cache_key)
    if cached is not None:
        metrics.cache_hits_total.labels(outcome="hit").inc()
        return cached
    metrics.cache_hits_total.labels(outcome="miss").inc()

    dq_list = tables.get("_data_quality", [{}])
    dq = dq_list[0] if dq_list else {}
    dq_warning = None
    if dq.get("disagreed", 0) > 0:
        dq_warning = (
            f"{dq['disagreed']} of {dq['total_records']} records had source disagreements. "
            "Local station feed used as primary (no conversion rounding loss)."
        )

    summary = _summarize(tables)

    t1 = time.perf_counter()
    provider_name = type(provider).__name__
    raw1 = provider.complete(PASS1_SYSTEM, f"Question: {question}\n\nTable metadata:\n{json.dumps(summary)}")
    metrics.llm_duration_seconds.labels(pass_num="1", provider=provider_name).observe(time.perf_counter() - t1)

    try:
        spec = json.loads(raw1)
    except json.JSONDecodeError:
        log.warning("pass1 non-json", extra={"raw": raw1[:200]})
        metrics.response_quality_total.labels(quality="error").inc()
        return {"answer": "Could not parse query intent.", "value": None, "chart": None, "citations": [], "response_quality": "error"}

    if "error" in spec:
        metrics.response_quality_total.labels(quality="degraded").inc()
        r = {"answer": spec["error"], "value": None, "chart": None, "citations": [], "response_quality": "degraded"}
        if dq_warning:
            r["data_quality_warning"] = dq_warning
        return r

    exec_result = _execute(spec, tables)

    t2 = time.perf_counter()
    raw2 = provider.complete(PASS2_SYSTEM, f"Question: {question}\n\nResult: {json.dumps(exec_result)}")
    metrics.llm_duration_seconds.labels(pass_num="2", provider=provider_name).observe(time.perf_counter() - t2)

    try:
        result = json.loads(raw2)
    except json.JSONDecodeError:
        log.warning("pass2 non-json", extra={"raw": raw2[:200]})
        result = {"answer": raw2, "value": None, "chart": None, "citations": [], "response_quality": "degraded"}

    quality = result.get("response_quality", "full")
    if result.get("value") is None and quality == "full":
        quality = "degraded"
        result["response_quality"] = "degraded"
    metrics.response_quality_total.labels(quality=quality).inc()

    if dq_warning:
        result["data_quality_warning"] = dq_warning

    cache.put(cache_key, result)
    log.info("query done", extra={"elapsed": round(time.perf_counter() - t_total, 3), "quality": quality})
    return result
