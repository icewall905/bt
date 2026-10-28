$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
# Parse every script before running the installer with a simulated Docker CLI.
foreach ($file in @('setup.ps1', 'manage.ps1', 'scripts/common.ps1')) {
    $errors = $null; $tokens = $null
    [Management.Automation.Language.Parser]::ParseFile((Join-Path $repo $file), [ref]$tokens, [ref]$errors) > $null
    if ($errors.Count) { throw ($errors | Out-String) }
}
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('bt-powershell-test-' + [guid]::NewGuid())
[IO.Directory]::CreateDirectory($fixture) > $null
Copy-Item (Join-Path $repo 'setup.ps1') $fixture
Copy-Item (Join-Path $repo 'manage.ps1') $fixture
Copy-Item (Join-Path $repo 'scripts') (Join-Path $fixture 'scripts') -Recurse
$env:BT_NO_BROWSER = '1'
$global:answers = [Collections.Generic.Queue[string]]::new()
foreach ($answer in @('./app data', './video $folder', 'wrong', '7777', 'y', "test `$password#with'quote", "test `$password#with'quote")) { $global:answers.Enqueue($answer) }
$global:dockerCalls = [Collections.Generic.List[string]]::new()
function global:Read-Host {
    param([string]$Prompt, [switch]$AsSecureString)
    $answer = $global:answers.Dequeue()
    if ($AsSecureString) { return ConvertTo-SecureString $answer -AsPlainText -Force }
    return $answer
}
function global:docker {
    $command = $args -join ' '
    $global:dockerCalls.Add($command)
    $global:LASTEXITCODE = 0
    switch ($command) {
        'compose up --help' { '--wait-timeout' }
        'compose port bt-api 6645' { '0.0.0.0:7777' }
    }
}
try {
    & (Join-Path $fixture 'setup.ps1')
    $config = [IO.File]::ReadAllText((Join-Path $fixture '.env'))
    if (-not $config.Contains('BT_PASSWORD="test $$password#with''quote"')) { throw 'Password quoting failed' }
    if (-not $config.Contains('video $$folder')) { throw 'Path quoting failed' }
    if (-not $global:dockerCalls.Contains('compose up -d --wait --wait-timeout 240')) { throw 'Readiness was not checked' }
    & (Join-Path $fixture 'setup.ps1')
    if ($config -ne [IO.File]::ReadAllText((Join-Path $fixture '.env'))) { throw 'Existing configuration changed' }
    Remove-Item -LiteralPath (Join-Path $fixture '.env') -Force
    foreach ($answer in @('./app data', './video $folder', '7777', '')) { $global:answers.Enqueue($answer) }
    & (Join-Path $fixture 'setup.ps1')
    if (-not ([IO.File]::ReadAllText((Join-Path $fixture '.env'))).Contains('BT_PASSWORD=""')) { throw 'Login must be off by default' }
    Write-Host 'PowerShell parsing, optional login and setup checks passed.'
} finally {
    Set-Location $repo
    Remove-Item $fixture -Recurse -Force
    Remove-Item function:Read-Host
    Remove-Item function:docker
}
