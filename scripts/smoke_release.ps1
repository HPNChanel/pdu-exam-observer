[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [int]$ExamPort = 8765,
    [int]$MonitorPort = 8766,
    [string]$ExamHealthPath = "/api/v1/health",
    [string]$MonitorHealthPath = "/api/v1/health",
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$exe = (Resolve-Path -LiteralPath $Executable).Path
$oldOpen = [Environment]::GetEnvironmentVariable("PDU_OPEN_BROWSER", "Process")
$oldBind = [Environment]::GetEnvironmentVariable("PDU_BIND_HOST", "Process")
$oldPin = [Environment]::GetEnvironmentVariable("PDU_REVIEWER_PIN", "Process")
$oldExamPort = [Environment]::GetEnvironmentVariable("PDU_EXAM_PORT", "Process")
$oldMonitorPort = [Environment]::GetEnvironmentVariable("PDU_MONITOR_PORT", "Process")
$process = $null
try {
    $env:PDU_OPEN_BROWSER = "0"
    $env:PDU_BIND_HOST = "127.0.0.1"
    $env:PDU_REVIEWER_PIN = "m0-smoke-process-only"
    $env:PDU_EXAM_PORT = [string]$ExamPort
    $env:PDU_MONITOR_PORT = [string]$MonitorPort
    $process = Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe) -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $origins = @(
        "http://127.0.0.1:$ExamPort$ExamHealthPath",
        "http://localhost:$MonitorPort$MonitorHealthPath"
    )
    do {
        if ($process.HasExited) { throw "release process exited before both health checks completed" }
        $ready = $true
        foreach ($uri in $origins) {
            try {
                $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2
                if ($response.StatusCode -ne 200) { $ready = $false }
            } catch { $ready = $false }
        }
        if ($ready) { break }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    if (-not $ready) { throw "health checks did not pass before timeout" }
    foreach ($uri in @("http://127.0.0.1:$ExamPort/exam", "http://localhost:$MonitorPort/monitor")) {
        $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -ne 200) { throw "static route check failed" }
    }
    Write-Output "Smoke checks passed for loopback health and /exam + /monitor static routes."
} finally {
    if ($process -and -not $process.HasExited) {
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "release process tree cleanup failed" }
        $process.WaitForExit()
    }
    if ($null -eq $oldOpen) { Remove-Item Env:PDU_OPEN_BROWSER -ErrorAction SilentlyContinue } else { $env:PDU_OPEN_BROWSER = $oldOpen }
    if ($null -eq $oldBind) { Remove-Item Env:PDU_BIND_HOST -ErrorAction SilentlyContinue } else { $env:PDU_BIND_HOST = $oldBind }
    if ($null -eq $oldPin) { Remove-Item Env:PDU_REVIEWER_PIN -ErrorAction SilentlyContinue } else { $env:PDU_REVIEWER_PIN = $oldPin }
    if ($null -eq $oldExamPort) { Remove-Item Env:PDU_EXAM_PORT -ErrorAction SilentlyContinue } else { $env:PDU_EXAM_PORT = $oldExamPort }
    if ($null -eq $oldMonitorPort) { Remove-Item Env:PDU_MONITOR_PORT -ErrorAction SilentlyContinue } else { $env:PDU_MONITOR_PORT = $oldMonitorPort }
}
