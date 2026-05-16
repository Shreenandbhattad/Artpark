# Tabular Analytics

Natural-language query service over multi-source weather data. Runs on localhost (live) and designed for AWS EC2 (documented).

## Quick start (Windows)

```powershell
pip install cryptography
.\start.ps1
```

## Quick start (Linux/Mac)

```bash
pip install cryptography
python scripts/generate_certs.py
bash deploy.sh localhost
```

API health: http://localhost/health
Grafana: http://localhost:3000 (admin/admin)

## Running tests

```bash
pip install -r app/requirements.txt
cd app
DOMAIN=environment PROVIDER=mock DATA_ROOT=../data IMAGE_TAG=dev pytest tests/ -v
```

## Design decisions

What I left as-is: providers.py. The three-provider abstraction (mock, hosted, ollama) is clean and correct. Adding a new provider is one class plus one if-branch. I updated MockProvider to handle the two-pass engine but kept the structure.

What I changed:

data_loader.py now calls a reconciler for the environment domain instead of silently picking the first source. It returns a tuple (tables, version_hash). The version hash invalidates the query cache on data reload.

query_engine.py is now two-pass. LLM generates a JSON query spec (which table, which filters, what aggregation), Python executes it deterministically, then LLM formats the answer from the result. The same question on the same data always returns the same numeric answer regardless of LLM temperature drift.

main.py adds correlation ID middleware, Prometheus timing middleware, a rich /health, and mounts /metrics on the FastAPI app. Prometheus scrapes it on the internal Docker network; nginx blocks it externally.

logging_setup.py emits JSON lines via python-json-logger with correlation_id and query_id injected from Python contextvars. Every log line is linkable to a specific request.

Domain choice: environment. Three weather stations (Bangalore, Hyderabad, Pune). The two sources have a schema-level unit mismatch: local feed uses degrees C and humidity 0-100, API export uses degrees F and humidity 0-1 decimal. The reconciler must normalise before comparing. The real data has small deltas within tolerance; the reconciler detects and surfaces genuine disagreements when they exist.

Data extended? No. The existing 30 records (3 stations x 10 days) are sufficient to demonstrate the reconciliation logic. Adding synthetic records would add noise without adding signal. If the data grew large enough to matter, the two-pass engine already handles it since the LLM never sees raw rows.

## Future Directions

- Replace the in-process dict cache with Redis to support multiple uvicorn workers
- Add a /reload endpoint (admin-protected) for hot data reload without restart
- Add API key middleware; the slot is already in the correlation ID context var
- Proper TLS cert provisioning via Let's Encrypt for the AWS path

## Architecture

See ARCHITECTURE.md.

## Operations

See RUNBOOK.md.
