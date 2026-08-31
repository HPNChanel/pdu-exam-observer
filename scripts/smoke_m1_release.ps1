[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [int]$ExamPort = 8875,
    [int]$MonitorPort = 8876,
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$exe = (Resolve-Path -LiteralPath $Executable).Path
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$workRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot ("pdu-m1-smoke-" + [Guid]::NewGuid().ToString("N"))))
if (-not $workRoot.StartsWith($tempRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing smoke workspace outside the system temporary directory"
}

$localAppData = Join-Path $workRoot "localappdata"
$dataRoot = Join-Path $workRoot "research-root"
$process = $null
$saved = @{}
foreach ($name in @("LOCALAPPDATA", "PDU_OPEN_BROWSER", "PDU_REVIEWER_PIN", "PDU_RUNTIME_MODE", "PDU_EXAM_PORT", "PDU_MONITOR_PORT")) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

function Stop-PduProcess {
    if ($script:process -and -not $script:process.HasExited) {
        & taskkill.exe /PID $script:process.Id /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "M1 smoke process-tree cleanup failed" }
        $script:process.WaitForExit()
    }
    $script:process = $null
}

function Start-PduProcess {
    $script:process = Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe) -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if ($script:process.HasExited) { throw "M1 release process exited before health checks completed" }
        $ready = $true
        foreach ($uri in @("http://127.0.0.1:$ExamPort/api/v1/health", "http://localhost:$MonitorPort/api/v1/health")) {
            try {
                $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2
                if ($response.StatusCode -ne 200) { $ready = $false }
            } catch { $ready = $false }
        }
        if ($ready) { return }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    throw "M1 health checks did not pass before timeout"
}

function New-IdempotencyKey([string]$scope) {
    return "$scope-$([Guid]::NewGuid().ToString('N'))"
}

try {
    New-Item -ItemType Directory -Path $localAppData -Force | Out-Null
    $env:LOCALAPPDATA = $localAppData
    $env:PDU_OPEN_BROWSER = "0"
    $env:PDU_REVIEWER_PIN = "m1-smoke-process-only"
    $env:PDU_RUNTIME_MODE = "m1"
    $env:PDU_EXAM_PORT = [string]$ExamPort
    $env:PDU_MONITOR_PORT = [string]$MonitorPort

    & $exe configure --root $dataRoot --encryption-status VERIFIED --acl-status VERIFIED
    if ($LASTEXITCODE -ne 0) { throw "Packaged M1 native configuration failed" }

    Start-PduProcess
    $origin = "http://localhost:$MonitorPort"
    $login = Invoke-RestMethod -Method Post -Uri "$origin/api/v1/reviewer/login" -Headers @{ Origin = $origin } -ContentType "application/json" -Body '{"pin":"m1-smoke-process-only"}'
    $auth = @{ Origin = $origin; Authorization = "Bearer $($login.access_token)" }

    $studyCode = "smoke-$([Guid]::NewGuid().ToString('N').Substring(0, 12))"
    $study = Invoke-RestMethod -Method Post -Uri "$origin/api/v1/research/studies" -Headers ($auth + @{ "Idempotency-Key" = (New-IdempotencyKey "study") }) -ContentType "application/json" -Body (@{ study_code = $studyCode } | ConvertTo-Json -Compress)
    $participant = Invoke-RestMethod -Method Post -Uri "$origin/api/v1/research/participants" -Headers ($auth + @{ "Idempotency-Key" = (New-IdempotencyKey "participant") }) -ContentType "application/json" -Body (@{ study_id = $study.study_id } | ConvertTo-Json -Compress)
    $session = Invoke-RestMethod -Method Post -Uri "$origin/api/v1/research/sessions" -Headers ($auth + @{ "Idempotency-Key" = (New-IdempotencyKey "session") }) -ContentType "application/json" -Body (@{ study_id = $study.study_id; participant_id = $participant.participant_id; retention_end_date = (Get-Date).AddDays(30).ToString("yyyy-MM-dd") } | ConvertTo-Json -Compress)
    $consent = Invoke-RestMethod -Method Post -Uri "$origin/api/v1/research/sessions/$($session.session_id)/consent-confirmation" -Headers ($auth + @{ "Idempotency-Key" = (New-IdempotencyKey "consent") }) -ContentType "application/json" -Body (@{ consent_receipt_id = "receipt-smoke"; consent_version = "v1" } | ConvertTo-Json -Compress)
    $readiness = Invoke-RestMethod -Method Get -Uri "$origin/api/v1/research/sessions/$($session.session_id)/readiness" -Headers $auth
    if ($readiness.ready -ne $false) { throw "M1 readiness must remain false" }
    foreach ($gate in @("INSTITUTIONAL_APPROVAL_REQUIRED", "RETENTION_AUTHORITY_UNVERIFIED", "RESEARCH_COLLECTION_NOT_IMPLEMENTED")) {
        if ($readiness.blocking_gates -notcontains $gate) { throw "Missing blocking readiness gate: $gate" }
    }
    $withdrawal = Invoke-RestMethod -Method Post -Uri "$origin/api/v1/research/sessions/$($session.session_id)/withdrawal" -Headers ($auth + @{ "Idempotency-Key" = (New-IdempotencyKey "withdraw") }) -ContentType "application/json" -Body '{}'
    if ($withdrawal.terminal -ne $true) { throw "Withdrawal was not terminal" }

    Stop-PduProcess
    Start-PduProcess
    $login2 = Invoke-RestMethod -Method Post -Uri "$origin/api/v1/reviewer/login" -Headers @{ Origin = $origin } -ContentType "application/json" -Body '{"pin":"m1-smoke-process-only"}'
    $auth2 = @{ Origin = $origin; Authorization = "Bearer $($login2.access_token)" }
    $status = Invoke-RestMethod -Method Get -Uri "$origin/api/v1/research/sessions/$($session.session_id)/withdrawal-status" -Headers $auth2
    if ($status.terminal -ne $true) { throw "Withdrawal did not survive process restart" }
    Write-Output "M1 smoke passed: configure, health, governance flow, fail-closed readiness, withdrawal, and restart persistence."
} finally {
    Stop-PduProcess
    foreach ($name in $saved.Keys) {
        if ($null -eq $saved[$name]) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($name, $saved[$name], "Process") }
    }
    if (Test-Path -LiteralPath $workRoot) {
        $resolvedWork = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $workRoot).Path)
        if (-not $resolvedWork.StartsWith($tempRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove an unexpected M1 smoke workspace"
        }
        $removed = $false
        for ($attempt = 1; $attempt -le 20; $attempt++) {
            try {
                Remove-Item -LiteralPath $resolvedWork -Recurse -Force
                $removed = $true
                break
            } catch {
                if ($attempt -eq 20) { throw }
                Start-Sleep -Milliseconds 250
            }
        }
        if (-not $removed) { throw "M1 smoke workspace cleanup did not complete" }
    }
}
