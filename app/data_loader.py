import csv
import hashlib
import logging
import os
from typing import Any

import reconciler

log = logging.getLogger("data")


def _read_csv(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for k, v in list(row.items()):
                try:
                    row[k] = float(v)
                except (TypeError, ValueError):
                    pass
            rows.append(row)
    return rows


def _version_hash(domain_dir: str) -> str:
    mtimes = []
    for fname in sorted(os.listdir(domain_dir)):
        if fname.endswith(".csv"):
            mtimes.append(str(os.path.getmtime(os.path.join(domain_dir, fname))))
    return hashlib.sha256("|".join(mtimes).encode()).hexdigest()[:12]


def load_domain(domain: str, data_root: str) -> tuple[dict[str, list[dict[str, Any]]], str]:
    domain_dir = os.path.join(data_root, domain)
    if not os.path.isdir(domain_dir):
        raise FileNotFoundError(f"domain dir not found: {domain_dir}")

    tables: dict[str, list[dict[str, Any]]] = {}
    for fname in sorted(os.listdir(domain_dir)):
        if not fname.endswith(".csv"):
            continue
        key = fname[:-4]
        rows = _read_csv(os.path.join(domain_dir, fname))
        tables[key] = rows
        log.info("loaded csv", extra={"file": fname, "rows": len(rows)})

    if domain == "environment":
        local = tables.get("station_obs_local", [])
        api = tables.get("weather_api_export", [])
        stations = tables.get("stations", [])
        result = reconciler.reconcile(local, api, stations)
        tables["reconciled_obs"] = result["reconciled"]
        tables["_data_quality"] = [result["summary"]]
        tables["_disagreements"] = result["disagreements"]
        dq = result["summary"]
        log.info(
            "reconciliation done",
            extra={"agreed": dq["agreed"], "disagreed": dq["disagreed"], "total": dq["total_records"]}
        )

    version = _version_hash(domain_dir)
    return tables, version
