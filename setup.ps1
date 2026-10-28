param([switch]$ConfigureOnly)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot 'scripts/common.ps1')
try {
    Require-Docker
    if (-not (Test-Path '.env')) {
        Write-Host 'BetterTube setup. Press Enter to use the defaults.'
        while ($true) {
            $data = Read-Host 'Folder for app data [./data]'
            $media = Read-Host 'Folder for downloaded videos [./media]'
            if (-not $data) { $data = './data' }
            if (-not $media) { $media = './media' }
            $data = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($data)
            $media = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($media)
            $repoPrefix = (Get-Location).Path.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
            $dataPrefix = $data.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
            $mediaPrefix = $media.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
            if ($repoPrefix.StartsWith($dataPrefix, [StringComparison]::OrdinalIgnoreCase) -or $repoPrefix.StartsWith($mediaPrefix, [StringComparison]::OrdinalIgnoreCase) -or $dataPrefix.StartsWith($mediaPrefix, [StringComparison]::OrdinalIgnoreCase) -or $mediaPrefix.StartsWith($dataPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                Write-Host 'Choose separate, non-nested storage folders, not the repository or one of its parents.'
                continue
            }
            foreach ($folder in @($data, $media)) {
                [IO.Directory]::CreateDirectory($folder) > $null
                $probe = Join-Path $folder ([IO.Path]::GetRandomFileName())
                [IO.File]::WriteAllText($probe, 'BetterTube storage check')
                Remove-Item -LiteralPath $probe
            }
            break
        }
        while ($true) {
            $port = Read-Host 'Web port [6645]'
            if (-not $port) { $port = '6645' }
            $number = 0
            if ([int]::TryParse($port, [ref]$number) -and $number -ge 1 -and $number -le 65535) { break }
            Write-Host 'Choose a number from 1 to 65535.'
        }
        $password = ''
        if ((Read-Host 'Protect the whole app with a shared password? [y/N]') -match '^(y|yes)$') {
            while ($true) {
                $password = Read-PasswordText 'Web password (Enter generates one)'
                if (-not $password) {
                    $bytes = New-Object byte[] 18
                    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
                    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
                    $password = [Convert]::ToBase64String($bytes)
                    Write-Host "Your generated password: $password"
                    Write-Host 'Save it somewhere safe before continuing.'
                    break
                }
                if ($password -eq (Read-PasswordText 'Repeat password')) { break }
                Write-Host 'The passwords did not match. Try again.'
            }
        } else { Write-Host 'Shared login is off. Optional profile PINs are available in Settings.' }
        function Quote-EnvValue([string]$Value) {
            return '"' + $Value.Replace('\', '\\').Replace('"', '\"').Replace('$', '$$') + '"'
        }
        $data = Quote-EnvValue ($data.Replace('\', '/'))
        $media = Quote-EnvValue ($media.Replace('\', '/'))
        $password = Quote-EnvValue $password
        $content = @"
BT_DATA_HOST_DIR=$data
BT_MEDIA_HOST_DIR=$media
BT_PORT=$number
BT_PASSWORD=$password
BT_SECRET=
BT_LLM_BASE_URL=
BT_LLM_MODEL=
BT_LLM_API_KEY=
BT_POT_URL=http://pot:4416
BT_YTDLP_AUTOUPDATE=1
"@
        [IO.File]::WriteAllText((Join-Path (Get-Location).Path '.env'), $content + "`n", (New-Object Text.UTF8Encoding($false)))
        $password = $null
        Write-Host 'Saved configuration to .env. More settings are available in the web app.'
    } else { Write-Host 'Using your existing .env. Your password and storage choices are preserved.' }
    if ($ConfigureOnly) {
        Invoke-Compose @('config', '--quiet')
        Write-Host 'Configuration saved. You can now restore a backup with manage.bat.'
    } else { Start-BetterTube }
} catch { Write-Host "BetterTube: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
