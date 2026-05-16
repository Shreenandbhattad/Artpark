Write-Host "starting..." -ForegroundColor Cyan
Set-Location $PSScriptRoot

add-type @"
using System.Net; using System.Security.Cryptography.X509Certificates;
public class TrustAll : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert, WebRequest req, int err) { return true; }
}
"@
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAll

Write-Host "1] generating certs..." -ForegroundColor Yellow
python scripts/generate_certs.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "failed. run: pip install cryptography" -ForegroundColor Red
    exit 1
}

Write-Host "2] starting docker stack..." -ForegroundColor Yellow
docker compose --env-file .env.localhost up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose failed. is Docker Desktop running?" -ForegroundColor Red
    exit 1
}

Write-Host "3] waiting for health..." -ForegroundColor Yellow
$max = 20
$ok = $false
for ($i = 1; $i -le $max; $i++) {
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-RestMethod -Uri "http://localhost/health" -TimeoutSec 3 -ErrorAction Stop
        if ($r.status -eq "ok" -or $r.status -eq "degraded") {
            Write-Host "   up. status=$($r.status)" -ForegroundColor Green
            $ok = $true
            break
        }
    } catch {
        Write-Host "   attempt $i/$max"
    }
}

if (-not $ok) {
    Write-Host "not healthy. check: docker compose logs app" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "ready."
Write-Host "  api:     http://localhost/health"
Write-Host "  grafana: http://localhost:3000  (admin / admin)"
Write-Host "  stop:    docker compose --env-file .env.localhost down"
