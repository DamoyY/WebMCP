param(
    [string]$SshTarget = "Fro",
    [string]$RemoteDir = "/opt/web-mcp",
    [string]$ServiceName = "web-mcp.service",
    [string]$PublicHealthUrl = "https://the-mars.dog/web-mcp/health"
)

$ErrorActionPreference = "Stop"

if ($RemoteDir -ne "/opt/web-mcp") {
    throw "Refusing to deploy to unexpected remote directory: $RemoteDir"
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$archive = Join-Path $env:TEMP ("web-mcp-" + [guid]::NewGuid().ToString("N") + ".tar.gz")
$remoteScriptPath = Join-Path $env:TEMP ("web-mcp-sync-" + [guid]::NewGuid().ToString("N") + ".sh")

try {
    Push-Location $projectRoot
    tar -czf $archive --exclude=".venv" --exclude=".pytest_cache" --exclude="__pycache__" --exclude="*.pyc" --exclude=".git" .
    Pop-Location

    scp $archive "${SshTarget}:/tmp/web-mcp.tar.gz"

    $remotePrefix = @"
set -euo pipefail
REMOTE_DIR='$RemoteDir'
SERVICE_NAME='$ServiceName'
PUBLIC_HEALTH_URL='$PublicHealthUrl'
"@

    $remoteBody = @'
if [ "$REMOTE_DIR" != "/opt/web-mcp" ]; then
    echo "Refusing to deploy to unexpected remote directory: $REMOTE_DIR" >&2
    exit 1
fi

STAGING="$(mktemp -d /tmp/web-mcp.XXXXXX)"
cleanup() {
    rm -rf "$STAGING"
}
trap cleanup EXIT

tar -xzf /tmp/web-mcp.tar.gz -C "$STAGING"
test -f "$STAGING/requirements.txt"
test -f "$STAGING/config/production.yaml"

if [ -d "$REMOTE_DIR/.venv" ]; then
    mv "$REMOTE_DIR/.venv" "$STAGING/.venv"
else
    python3 -m venv "$STAGING/.venv"
fi

"$STAGING/.venv/bin/python" -m pip install --no-cache-dir -r "$STAGING/requirements.txt"

rm -rf "${REMOTE_DIR}.previous"
if [ -d "$REMOTE_DIR" ]; then
    mv "$REMOTE_DIR" "${REMOTE_DIR}.previous"
fi
mv "$STAGING" "$REMOTE_DIR"
trap - EXIT

install -m 0644 "$REMOTE_DIR/deploy/systemd/web-mcp.service" /etc/systemd/system/web-mcp.service
install -D -m 0644 "$REMOTE_DIR/deploy/nginx/web-mcp.locations.conf" /etc/nginx/snippets/web-mcp.locations.conf

python3 - <<'PY'
from datetime import datetime
from pathlib import Path

path = Path("/etc/nginx/sites-available/the-mars.dog")
text = path.read_text()
include = "    include /etc/nginx/snippets/web-mcp.locations.conf;\n\n"
if include not in text:
    marker = "    location / {\n        try_files $uri $uri/ =404;\n    }\n"
    index = text.rfind(marker)
    if index == -1:
        raise SystemExit("target location block not found")
    backup = path.with_name(path.name + ".bak.web-mcp." + datetime.now().strftime("%Y%m%d%H%M%S"))
    backup.write_text(text)
    path.write_text(text[:index] + include + text[index:])
PY

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
nginx -t
systemctl reload nginx
for attempt in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:18080/health; then
        break
    fi
    if [ "$attempt" -eq 30 ]; then
        echo "Local health check failed after restart" >&2
        exit 1
    fi
    sleep 1
done
printf '\n'
curl -fsS "$PUBLIC_HEALTH_URL"
printf '\n'
rm -f /tmp/web-mcp.tar.gz
'@

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($remoteScriptPath, ($remotePrefix + "`n" + $remoteBody), $utf8NoBom)
    scp $remoteScriptPath "${SshTarget}:/tmp/web-mcp-sync.sh"
    ssh $SshTarget "bash /tmp/web-mcp-sync.sh; code=`$?; rm -f /tmp/web-mcp-sync.sh; exit `$code"
}
finally {
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force
    }
    if (Test-Path -LiteralPath $remoteScriptPath) {
        Remove-Item -LiteralPath $remoteScriptPath -Force
    }
}
