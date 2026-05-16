# Runbook

## Who to call at 3am

Check docker ps first. If the container is running but /health returns degraded, it is almost certainly the LLM provider. Switch to PROVIDER=mock (restart the app container) to restore service, then investigate the provider separately.

---

## Deploy (localhost)

Prerequisites: Docker with Compose v2, Python 3.10+, bash or PowerShell.

```bash
git clone <repo>
cd <repo>
python scripts/generate_certs.py
bash deploy.sh localhost
```

The script sources .env.localhost, validates required vars, brings up the full stack with docker compose up -d, then polls http://localhost/health for up to 60 seconds. On failure it reverts to the previous image.

---

## Deploy (AWS EC2)

bash deploy.sh aws prints the required steps and exits without executing them (no real AWS credentials required for evaluation).

One-time EC2 setup:

```bash
sudo apt-get install -y docker.io
sudo systemctl enable --now docker

mkdir -p /opt/tabular-analytics
cd /opt/tabular-analytics
git clone <repo> .

cp .env.aws .env.aws.local
vim .env.aws.local   # set IMAGE, IMAGE_TAG, GRAFANA_PASSWORD

sudo cp systemd/tabular-analytics.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tabular-analytics
```

Rolling deploy:

```bash
cd /opt/tabular-analytics
IMAGE_TAG=<new-sha> bash deploy.sh aws
```

The systemd unit uses Type=oneshot with RemainAfterExit=yes. This is correct for docker compose up -d which exits immediately after starting containers. systemctl status tabular-analytics shows the last ExecStart output.

---

## Rollback

deploy.sh rolls back automatically if health polling fails. To manually rollback:

```bash
docker images ghcr.io/org/tabular-analytics --format "{{.Tag}} {{.CreatedAt}}" | head -5

sed -i 's/^IMAGE=.*/IMAGE=ghcr.io\/org\/tabular-analytics:OLD_SHA/' .env.localhost

bash deploy.sh localhost
```

---

## /health field semantics

GET /health always returns HTTP 200. Read the body.

| Field | Meaning |
|---|---|
| status | "ok" means all checks pass. "degraded" means at least one check failed. |
| image_tag | Git SHA baked at build time. Confirms which version is running. |
| uptime_seconds | Time since process start. Unexpected low values mean recent restart. |
| checks.data.version | SHA of CSV mtimes at last load. Changes if data files changed. |
| checks.data.total_rows | Total rows across non-internal tables. Zero means data load failed. |
| checks.cache.entries | Active cache entries. High count is fine; cache is bounded by TTL. |
| checks.llm_provider.provider | Which provider is active. Should be HostedProvider in prod. |
| checks.data_quality.disagreed | Records where sources disagreed beyond tolerance. Non-zero is expected and surfaced to users. |

---

## Where logs live

Locally: docker compose logs app -f for the FastAPI service logs. Logs are JSON, one object per line.

In Loki: Grafana -> Explore -> Loki -> {app="tabular-analytics"}. Filter by correlation_id: {app="tabular-analytics"} |= "abc123def456".

On AWS: /var/lib/docker/containers/<id>/<id>-json.log (raw). Use docker logs tabular-analytics-app-1 --since 1h for recent logs.

---

## Grafana dashboard

http://localhost:3000, admin/admin (change password in .env.localhost).

Dashboard: Tabular Analytics Operator View

Reading the dashboard:
1. Request rate drops or error rate spikes: something is wrong
2. P95 end-to-end latency is high: look at LLM Pass 1 P95 and Pass 2 P95 panels
   - Pass 1 slow means LLM intent extraction is the bottleneck
   - Pass 2 slow means LLM answer formatting is the bottleneck
3. Degraded response rate rising: LLM returning non-JSON. Switch to mock or check provider status.
4. Cache hit rate near zero: cache keys are not matching. Data version may have changed.
5. Data disagreements table: shows which (field, station) pairs have disagreements. Non-zero is normal with two sources.

---

## Alerts

| Alert | Severity | Condition | Action |
|---|---|---|---|
| ServiceDown | critical | Prometheus cannot scrape /metrics for 1m | docker compose ps, restart if stopped |
| HighDegradedResponseRate | warning | >5% degraded responses over 2m | check LLM provider connectivity, switch to mock if needed |
| HighQueryLatency | warning | P95 /query > 10s for 3m | check LLM provider latency, check cache hit rate |

---

## Common failure modes

Container starts but /health returns degraded:
Check checks.data.status. If data is not loaded, run docker compose exec app python -c "from data_loader import load_domain; print(load_domain('environment','/data'))" and look for FileNotFoundError.

Queries return value=null with response_quality=degraded:
Mock provider always returns full quality. If you see degraded with PROVIDER=hosted, the LLM returned non-JSON. Check docker compose logs app | grep "pass2 non-json" for the raw response.

nginx 502:
App container is not healthy yet. Wait for health check to pass (docker compose ps). If persistently 502, check app logs with docker compose logs app.

Prometheus shows no data:
Prometheus scrapes app:8000/metrics directly, not through nginx. Confirm both containers are on the same backend network: docker network inspect artpark_backend.
