#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname "$0")"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$(dirname "$0")/key.pem" \
    -out "$(dirname "$0")/cert.pem" \
    -subj "/CN=localhost/O=tabular-analytics" \
    2>/dev/null
echo "certs written to $(dirname "$0")"
