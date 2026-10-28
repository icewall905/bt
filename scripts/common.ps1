$ErrorActionPreference = 'Stop'
$script:BetterTubeRoot = (Get-Location).Path
function Invoke-Compose {
    param([string[]]$ComposeArgs)
    & docker compose @ComposeArgs
    if ($LASTEXITCODE -ne 0) { throw 'Docker could not complete this action. Read the error above.' }
}
function Require-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install Docker Desktop, start it, and run setup again.' }
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Install or update Docker Desktop with Docker Compose.' }
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and wait until its engine is running, then try again.' }
    $help = & docker compose up --help
    if (-not ($help -match '--wait-timeout')) { throw 'Update Docker Desktop: setup requires Docker Compose 2.20 or newer.' }
}
function Invoke-StorageHelper {
    param([string[]]$HelperArgs)
    Get-Content -Raw (Join-Path $script:BetterTubeRoot 'scripts/deploy.py') | & docker compose run --rm -T --no-deps --entrypoint python @HelperArgs
    if ($LASTEXITCODE -ne 0) { throw 'Storage action failed. Read the message above; check permissions and Docker Desktop file sharing.' }
}
function Start-BetterTube {
    Invoke-Compose @('config', '--quiet')
    Write-Host 'Building BetterTube. The first build may take several minutes...'
    Invoke-Compose @('build')
    Invoke-StorageHelper @('bt-api', '-', 'check')
    Write-Host 'Starting services and waiting for the web app...'
    & docker compose up -d --wait --wait-timeout 240
    if ($LASTEXITCODE -ne 0) {
        & docker compose ps
        throw 'Startup failed. Check whether the chosen port is already used. Run docker compose logs --tail 60 for service errors.'
    }
    $binding = & docker compose port bt-api 6645
    if ($LASTEXITCODE -ne 0 -or -not $binding) { throw 'Could not find the web port.' }
    $port = ($binding | Select-Object -First 1) -replace '^.*:', ''
    $url = "http://localhost:$port"
    Write-Host "BetterTube is ready: $url"
    Write-Host "Other home devices: replace localhost with this computer's LAN IP address."
    if ($env:BT_NO_BROWSER -ne '1') { try { Start-Process $url } catch { Write-Host 'Open the address above in your browser.' } }
}
function Read-PasswordText {
    param([string]$Prompt)
    $secure = Read-Host $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $secure.Dispose() }
}
