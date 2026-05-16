import metrics

TEMP_TOL = 0.3      # celsius
HUMID_TOL = 1.0     # percentage points

def _f_to_c(f: float) -> float:
    return round((f - 32) * 5 / 9, 2)

def reconcile(local_rows: list, api_rows: list, station_rows: list) -> dict:
    station_names = {r["station_id"]: r.get("station_name", r["station_id"]) for r in station_rows}

    local_canon: dict[tuple, dict] = {}
    for r in local_rows:
        key = (r["station_id"], r["date"])
        local_canon[key] = {
            "station_id": r["station_id"],
            "date": r["date"],
            "temp_c": float(r["temp_c"]),
            "humidity_pct": float(r["humidity_pct"])
        }

    api_canon: dict[tuple, dict] = {}
    for r in api_rows:
        sid = r.get("station") or r.get("station_id")
        date = r.get("day") or r.get("date")
        if sid is None or date is None:
            continue
        key = (sid, date)
        api_canon[key] = {
            "station_id": sid,
            "date": date,
            "temp_c": _f_to_c(float(r["temp_f"])),
            "humidity_pct": round(float(r["humidity"]) * 100, 1)  # normalize
        }

    reconciled = []
    disagreements = []
    agreed = local_only = api_only = 0

    for key in sorted(set(local_canon) | set(api_canon)):
        loc = local_canon.get(key)
        api = api_canon.get(key)

        if loc is None:
            api_only += 1
            disagreements.append({"station_id": key[0], "date": key[1], "status": "api_only"})
            reconciled.append({**api, "source": "api"})
            continue
        if api is None:
            local_only += 1
            disagreements.append({"station_id": key[0], "date": key[1], "status": "local_only"})
            reconciled.append({**loc, "source": "local"})
            continue

        row_diffs = []
        t_delta = abs(loc["temp_c"] - api["temp_c"])
        h_delta = abs(loc["humidity_pct"] - api["humidity_pct"])

        if t_delta > TEMP_TOL:
            row_diffs.append({
                "field": "temp_c",
                "local": loc["temp_c"], "api": api["temp_c"],
                "delta": round(t_delta, 3)
            })
            metrics.data_disagreements_total.labels(field="temp_c", station=key[0]).inc()

        if h_delta > HUMID_TOL:
            row_diffs.append({
                "field": "humidity_pct",
                "local": loc["humidity_pct"], "api": api["humidity_pct"],
                "delta": round(h_delta, 1)
            })
            metrics.data_disagreements_total.labels(field="humidity_pct", station=key[0]).inc()

        if row_diffs:
            disagreements.append({"station_id": key[0], "date": key[1], "fields": row_diffs})
            reconciled.append({**loc, "source": "local_primary"})  # local wins
        else:
            agreed += 1
            reconciled.append({**loc, "source": "both"})

    total = len(reconciled)
    disagreed = len([d for d in disagreements if "fields" in d])

    return {
        "reconciled": reconciled,
        "disagreements": disagreements,
        "summary": {
            "total_records": total,
            "agreed": agreed,
            "disagreed": disagreed,
            "local_only": local_only,
            "api_only": api_only
        }
    }
