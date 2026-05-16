Write-Host "=== Tabular Analytics -- Windows startup ===" -ForegroundColor Cyan
Set-Location $PSScriptRoot

# skip self-signed cert check for local dev
add-type @"
using System.Net; using System.Security.Cryptography.X509Certificates;
public class TrustAll : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert, WebRequest req, int err) { return true; }
}
"@
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAll

Write-Host "`nStep 1: generating SSL certs..." -ForegroundColor Yellow
python scripts/generate_certs.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Cert generation failed. Run: pip install cryptography" -ForegroundColor Red
    exit 1
}

Write-Host "`nStep 2: starting docker stack (this builds the image, takes 2-4 min first time)..." -ForegroundColor Yellow
docker compose --env-file .env.localhost up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose failed. Is Docker Desktop running and signed in?" -ForegroundColor Red
    exit 1
}

Write-Host "`nStep 3: waiting for service to be healthy (up to 60s)..." -ForegroundColor Yellow
$max = 20
$ok = $false
for ($i = 1; $i -le $max; $i++) {
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-RestMethod -Uri "http://localhost/health" -TimeoutSec 3 -ErrorAction Stop
        if ($r.status -eq "ok" -or $r.status -eq "degraded") {
            Write-Host "  Service healthy! status=$($r.status)" -ForegroundColor Green
            $ok = $true
            break
        }
    } catch {
        Write-Host "  attempt $i/$max -- still starting..."
    }
}

if (-not $ok) {
    Write-Host "`nService not healthy yet. Check logs with:" -ForegroundColor Yellow
    Write-Host "  docker compose logs app"
    Write-Host "  docker compose ps"
    exit 1
}

Write-Host "`n=== Ready ===" -ForegroundColor Green
Write-Host ""
Write-Host "  API health:   http://localhost/health"
Write-Host "  Grafana:      http://localhost:3000   (login: admin / admin)"
Write-Host ""
Write-Host "Quick test:"
Write-Host '  Invoke-RestMethod -Uri "http://localhost/query" -Method Post -Body '"'"'{"question":"what is the average temperature at S001?"}'"'"' -ContentType "application/json" | ConvertTo-Json'
Write-Host ""
Write-Host "Stop everything:"
Write-Host "  docker compose --env-file .env.localhost down"
