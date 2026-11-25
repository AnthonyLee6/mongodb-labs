param(
    [ValidateSet('start','shell','check','stop')][string]$Action = 'check',
    [ValidateRange(1024,65535)][int]$Port = 27017
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$server = Join-Path $root 'server\bin\mongod.exe'
$shell = Join-Path $root 'shell\bin\mongosh.exe'
$data = Join-Path $root 'data'
$logs = Join-Path $root 'logs'
$statePath = Join-Path $root 'runtime.json'

function Test-Listening([int]$TargetPort) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect('127.0.0.1', $TargetPort, $null, $null)
        if (!$pending.AsyncWaitHandle.WaitOne(500)) { return $false }
        $client.EndConnect($pending)
        return $true
    } catch { return $false } finally { $client.Dispose() }
}

function Get-OwnedProcess($State) {
    if (!$State -or $State.root -ne $root) { return $null }
    $process = Get-Process -Id $State.processId -ErrorAction SilentlyContinue
    if (!$process) { return $null }
    if ($process.Path -ne $server) { return $null }
    if ($process.StartTime.ToUniversalTime().Ticks.ToString() -ne $State.startTicks) { return $null }
    return $process
}

try {
    if (!(Test-Path -LiteralPath $server) -or !(Test-Path -LiteralPath $shell)) {
        throw 'Extract the COMPLETE ZIP first. server/bin/mongod.exe or shell/bin/mongosh.exe is missing.'
    }
    $state = $null
    if (Test-Path -LiteralPath $statePath) { $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json }
    $owned = Get-OwnedProcess $state
    if ($Action -eq 'start') {
        if ($owned) {
            if (!(Test-Listening $state.port)) { throw 'Existing process is not ready. Check logs/mongod.log.' }
            Write-Host "Already running on 127.0.0.1:$($state.port). No data changed."
            exit 0
        }
        if (Test-Listening $Port) { throw "Port $Port is occupied. Do not stop another MongoDB. Ask the teacher for help." }
        New-Item -ItemType Directory -Path $data,$logs -Force | Out-Null
        $arguments = '--bind_ip 127.0.0.1 --port {0} --dbpath "{1}" --logpath "{2}" --logappend' -f $Port,$data,(Join-Path $logs 'mongod.log')
        $process = Start-Process -FilePath $server -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -PassThru
        $state = @{root=$root;processId=$process.Id;startTicks=$process.StartTime.ToUniversalTime().Ticks.ToString();port=$Port}
        $state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
        $ready = $false
        for ($attempt=0; $attempt -lt 100; $attempt++) {
            if ($process.HasExited) { throw 'MongoDB failed to start. Read logs/mongod.log; check Windows runtime requirements.' }
            if (Test-Listening $Port) { $ready=$true; break }
            Start-Sleep -Milliseconds 200
        }
        if (!$ready) { throw 'Startup timed out. Use 04_stop.bat before retrying; check logs/mongod.log.' }
        & $shell "mongodb://127.0.0.1:$Port/admin?directConnection=true&serverSelectionTimeoutMS=5000" --quiet --eval 'printjson(db.runCommand({ping:1}))'
        if ($LASTEXITCODE -ne 0) { throw 'Server started but ping failed. Use 04_stop.bat and contact the teacher.' }
        Write-Host 'READY. Open 02_shell.bat. Keep the data folder; restart does not reset your work.'
    } else {
        if (!$owned) {
            if ($Action -eq 'stop') { Write-Host 'This package has no running MongoDB. No other process was touched.'; exit 0 }
            throw 'Run 01_start.bat first. This launcher will not connect to an unowned MongoDB.'
        }
        $uri = "mongodb://127.0.0.1:$($state.port)/testdb?directConnection=true&serverSelectionTimeoutMS=5000"
        if ($Action -eq 'shell') {
            & $shell $uri
            exit $LASTEXITCODE
        }
        if ($Action -eq 'check') {
            & $shell $uri --quiet --file (Join-Path $root 'check.js')
            exit $LASTEXITCODE
        }
        if ($Action -eq 'stop') {
            $ErrorActionPreference = 'Continue'
            $shutdown = & $shell $uri --quiet --eval 'db.getSiblingDB(''admin'').shutdownServer()' 2>&1
            $ErrorActionPreference = 'Stop'
            if (!$owned.WaitForExit(15000)) { throw 'Graceful shutdown not confirmed. No force-kill performed; contact the teacher.' }
            Remove-Item -LiteralPath $statePath
            Write-Host 'STOPPED. Data retained. Only this package instance was stopped.'
        }
    }
    exit 0
} catch {
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
