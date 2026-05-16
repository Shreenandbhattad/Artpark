#!/usr/bin/env bash
set -euo pipefail

TARGET=${1:-localhost}
ENV_FILE=".env.${TARGET}"

echo "INFO: deploying to target=${TARGET}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERR: $ENV_FILE not found"
    exit 1
fi

set -a; source "$ENV_FILE"; set +a

for var in IMAGE DOMAIN PROVIDER; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERR: $var not set in $ENV_FILE"
        exit 1
    fi
done

if [[ "$TARGET" == "aws" ]]; then
    echo "INFO: AWS target -- stub path (no real AWS execution)"
    echo "INFO: full AWS deploy steps are in RUNBOOK.md#aws-deploy"
    echo "INFO: would run: aws ecr get-login-password | docker login ..."
    echo "INFO: would SSH to EC2 and run: docker compose --env-file .env.aws pull && docker compose up -d"
    echo "INFO: systemd unit is in systemd/tabular-analytics.service"
    exit 0
fi

if [[ ! -f "certs/cert.pem" ]]; then
    echo "INFO: no certs found, generating self-signed"
    bash certs/generate-certs.sh
fi

echo "INFO: pulling image ${IMAGE}"
docker compose --env-file "$ENV_FILE" pull app 2>/dev/null || true

OLD_ID=$(docker compose --env-file "$ENV_FILE" ps -q app 2>/dev/null || true)
OLD_IMAGE=""
if [[ -n "$OLD_ID" ]]; then
    OLD_IMAGE=$(docker inspect "$OLD_ID" --format '{{.Config.Image}}' 2>/dev/null || true)
fi

echo "INFO: bringing up stack"
docker compose --env-file "$ENV_FILE" up -d --remove-orphans

MAX=20
DELAY=3
echo "INFO: polling /health (max ${MAX}x${DELAY}s = $((MAX*DELAY))s)"

for i in $(seq 1 $MAX); do
    STATUS=$(curl -sk "https://localhost/health" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','error'))" \
        2>/dev/null || echo "error")

    if [[ "$STATUS" == "ok" ]]; then
        echo "INFO: health ok after $i attempts"
        echo "INFO: deploy complete"
        exit 0
    fi

    echo "INFO: attempt $i/$MAX status=$STATUS -- waiting ${DELAY}s"
    sleep $DELAY
done

echo "ERR: health check failed after $((MAX*DELAY))s -- rolling back"
docker compose --env-file "$ENV_FILE" down

if [[ -n "$OLD_IMAGE" ]]; then
    echo "INFO: rolling back to $OLD_IMAGE"
    sed -i "s|^IMAGE=.*|IMAGE=${OLD_IMAGE}|" "$ENV_FILE"
    docker compose --env-file "$ENV_FILE" up -d
    echo "WARN: rolled back to ${OLD_IMAGE}"
else
    echo "WARN: no previous image -- stack is down"
fi

exit 1
