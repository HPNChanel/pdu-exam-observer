$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$ResponseLeaf = Join-Path $PSScriptRoot "M2_S3E_CLEAN_ENVIRONMENT_RESPONSE.json"
$RuntimeRoot = Join-Path $PSScriptRoot ".pdu-m2-s3e-runtime"
$BundleRoot = Join-Path $PSScriptRoot "PDU-Exam-Observer"
$Executable = Join-Path $BundleRoot "PDUExamObserver.exe"
$DetachedManifest = Join-Path $PSScriptRoot "RELEASE_MANIFEST.json"
$BundledManifest = Join-Path $BundleRoot "RELEASE_MANIFEST.json"
$HandoffManifest = Join-Path $PSScriptRoot "M2_S3E_HANDOFF_MANIFEST.json"
$ReviewerPin = "m2-s3e-clean-environment-process-only"
$script:ServerProcess = $null
$script:ScriptArgumentCount = $args.Count

function ConvertTo-CanonicalJson([object]$Value) {
    return ($Value | ConvertTo-Json -Compress -Depth 32)
}

function Get-Utf8Bytes([string]$Value) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    return $encoding.GetBytes($Value)
}

function Get-Sha256Bytes([byte[]]$Bytes) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Get-Sha256File([string]$Path) {
    if (-not [IO.File]::Exists($Path)) { throw "HANDOFF_MANIFEST_MISMATCH" }
    $stream = [IO.File]::OpenRead($Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

function Write-CanonicalResult([object]$Document, [int]$ExitCode, [bool]$Persist) {
    $json = (ConvertTo-CanonicalJson $Document) + "`n"
    $bytes = Get-Utf8Bytes $json
    if ($Persist) {
        [IO.File]::WriteAllBytes($ResponseLeaf, $bytes)
    }
    [Console]::Out.Write($json)
    exit $ExitCode
}

function Write-BoundedFailure([string]$Code) {
    $allowed = @(
        "REQUEST_INVALID", "PLATFORM_UNSUPPORTED", "PROCESS_NOT_STANDARD_USER",
        "HANDOFF_MANIFEST_MISMATCH", "CANDIDATE_MANIFEST_MISMATCH",
        "DEPENDENCY_ISOLATION_FAILED", "PROCESS_START_FAILED", "HEALTH_TIMEOUT",
        "LOOPBACK_SCOPE_VIOLATION", "AUTHENTICATION_FAILED", "SYNTHETIC_RUN_FAILED",
        "EVIDENCE_EXPORT_FAILED", "REPRODUCTION_FAILED", "CANDIDATE_MUTATION_DETECTED",
        "PROCESS_CLEANUP_FAILED", "TEMP_CLEANUP_FAILED", "UNEXPECTED_FAILURE"
    )
    if ($allowed -notcontains $Code) { $Code = "UNEXPECTED_FAILURE" }
    $document = [ordered]@{
        failure_code = $Code
        result = "CLEAN_ENVIRONMENT_PROBE_NOT_VERIFIED"
        status = $null
    }
    Write-CanonicalResult $document 2 $false
}

function Assert-PlatformAndUser {
    if ($script:ScriptArgumentCount -ne 0) { throw "REQUEST_INVALID" }
    if ($PSVersionTable.PSEdition -ne "Desktop" -or $PSVersionTable.PSVersion -lt [Version]"5.1") {
        throw "PLATFORM_UNSUPPORTED"
    }
    if (-not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) {
        throw "PLATFORM_UNSUPPORTED"
    }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "PROCESS_NOT_STANDARD_USER"
    }
}

function Assert-HandoffAndCandidate {
    foreach ($path in @($Executable, $DetachedManifest, $BundledManifest, $HandoffManifest)) {
        if (-not [IO.File]::Exists($path)) { throw "HANDOFF_MANIFEST_MISMATCH" }
    }
    if ((Get-Sha256File $Executable) -ne "9d9aabe6b6176fabb1db423924d8c27a8ee9478d302b421680dc8bfc989c66aa") {
        throw "CANDIDATE_MANIFEST_MISMATCH"
    }
    if ((Get-Sha256File $DetachedManifest) -ne "8702963dddd8b9d2761120fce8875d9fd181177eb15f1576e72e7354ad3ae216") {
        throw "CANDIDATE_MANIFEST_MISMATCH"
    }
    if ((Get-Sha256File $BundledManifest) -ne "8702963dddd8b9d2761120fce8875d9fd181177eb15f1576e72e7354ad3ae216") {
        throw "CANDIDATE_MANIFEST_MISMATCH"
    }
    $manifest = Get-Content -LiteralPath $DetachedManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $expected = @{}
    foreach ($record in $manifest.files) {
        if ($null -eq $record.path -or $expected.ContainsKey([string]$record.path)) {
            throw "CANDIDATE_MANIFEST_MISMATCH"
        }
        $expected[[string]$record.path] = $record
    }
    $observed = @(Get-ChildItem -LiteralPath $BundleRoot -File -Recurse | Where-Object {
        $_.FullName -ne $BundledManifest
    })
    if ($observed.Count -ne $expected.Count) { throw "CANDIDATE_MANIFEST_MISMATCH" }
    foreach ($file in $observed) {
        $relative = $file.FullName.Substring($BundleRoot.Length + 1).Replace("\", "/")
        if (-not $expected.ContainsKey($relative)) { throw "CANDIDATE_MANIFEST_MISMATCH" }
        $record = $expected[$relative]
        if ($file.Length -ne [long]$record.size -or (Get-Sha256File $file.FullName) -ne [string]$record.sha256) {
            throw "CANDIDATE_MANIFEST_MISMATCH"
        }
    }
    $handoff = Get-Content -LiteralPath $HandoffManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($record in $handoff.body.artifacts) {
        $candidate = Join-Path $PSScriptRoot ([string]$record.path).Replace("/", "\")
        $resolved = [IO.Path]::GetFullPath($candidate)
        if (-not $resolved.StartsWith(([IO.Path]::GetFullPath($PSScriptRoot) + [IO.Path]::DirectorySeparatorChar), [StringComparison]::OrdinalIgnoreCase)) {
            throw "HANDOFF_MANIFEST_MISMATCH"
        }
        if (-not [IO.File]::Exists($resolved) -or (Get-Item -LiteralPath $resolved).Length -ne [long]$record.size -or (Get-Sha256File $resolved) -ne [string]$record.sha256) {
            throw "HANDOFF_MANIFEST_MISMATCH"
        }
    }
    return (Get-Sha256File $HandoffManifest)
}

function New-FreeLoopbackPort {
    $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try { return ([Net.IPEndPoint]$listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}

function New-CandidateStartInfo([string]$Mode, [int]$ExamPort, [int]$MonitorPort, [bool]$RedirectInput) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Executable
    $info.WorkingDirectory = $BundleRoot
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $RedirectInput
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.EnvironmentVariables.Clear()
    $systemPath = @(
        (Join-Path $env:SystemRoot "System32"),
        $env:SystemRoot,
        (Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0")
    ) -join ";"
    $values = [ordered]@{
        APPDATA = (Join-Path $RuntimeRoot "appdata")
        LOCALAPPDATA = (Join-Path $RuntimeRoot "localappdata")
        PATH = $systemPath
        PATHEXT = ".COM;.EXE;.BAT;.CMD"
        PDU_EXAM_PORT = [string]$ExamPort
        PDU_MONITOR_PORT = [string]$MonitorPort
        PDU_OPEN_BROWSER = "0"
        PDU_REVIEWER_PIN = $ReviewerPin
        PDU_RUNTIME_MODE = $Mode
        SystemDrive = $env:SystemDrive
        SystemRoot = $env:SystemRoot
        TEMP = $RuntimeRoot
        TMP = $RuntimeRoot
        windir = $env:windir
    }
    foreach ($item in $values.GetEnumerator()) { $info.EnvironmentVariables[$item.Key] = $item.Value }
    return $info
}

function Wait-Health([string]$Uri) {
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $value = Invoke-RestMethod -Method Get -Uri $Uri -TimeoutSec 2 -UseBasicParsing
            if ($value.status -eq "ok") { return }
        }
        catch { }
        Start-Sleep -Milliseconds 100
    }
    throw "HEALTH_TIMEOUT"
}

function Assert-LoopbackScope([int[]]$Ports, [int]$ProcessId) {
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object {
        $Ports -contains $_.LocalPort
    })
    $observedPorts = @{}
    foreach ($listener in $listeners) {
        if (@("127.0.0.1", "::1") -notcontains $listener.LocalAddress -or $listener.OwningProcess -ne $ProcessId) {
            throw "LOOPBACK_SCOPE_VIOLATION"
        }
        $observedPorts[[int]$listener.LocalPort] = $true
    }
    if ($observedPorts.Count -ne $Ports.Count) { throw "LOOPBACK_SCOPE_VIOLATION" }
    foreach ($port in $Ports) {
        if (-not $observedPorts.ContainsKey([int]$port)) { throw "LOOPBACK_SCOPE_VIOLATION" }
    }
    $connections = @(Get-NetTCPConnection -OwningProcess $ProcessId -ErrorAction SilentlyContinue)
    foreach ($connection in $connections) {
        if ($connection.State -eq "Listen") { continue }
        if (@("127.0.0.1", "::1", "0.0.0.0", "::") -notcontains $connection.RemoteAddress) {
            throw "LOOPBACK_SCOPE_VIOLATION"
        }
    }
}

function Invoke-ReviewerLogin([string]$Origin) {
    $headers = @{ Origin = $Origin }
    $payload = @{ pin = $ReviewerPin } | ConvertTo-Json -Compress
    try {
        $response = Invoke-RestMethod -Method Post -Uri "$Origin/api/v1/reviewer/login" -Headers $headers -ContentType "application/json" -Body $payload -TimeoutSec 5 -UseBasicParsing
    }
    catch { throw "AUTHENTICATION_FAILED" }
    if ([string]::IsNullOrWhiteSpace([string]$response.access_token)) { throw "AUTHENTICATION_FAILED" }
    return [string]$response.access_token
}

function Assert-AuthorityEnvelope([object]$Envelope) {
    if ($Envelope.authority_status -ne "AUTHORITY_NOT_ISSUED" -or
        $Envelope.collection_authorized -ne $false -or
        $Envelope.d1_go -ne $false -or
        $Envelope.device_gate_decision -ne "UNVERIFIED" -or
        $Envelope.evidence_kind -ne "SIMULATED" -or
        $Envelope.participant_collection_authorized -ne $false -or
        $Envelope.physical_camera_access_authorized -ne $false -or
        $Envelope.research_ready -ne $false) {
        throw "SYNTHETIC_RUN_FAILED"
    }
}

function Assert-IntegrationReceiptAuthority([object]$Receipt) {
    if ($Receipt.authority_status -ne "AUTHORITY_NOT_ISSUED" -or
        $Receipt.collection_authorized -ne $false -or
        $Receipt.d1_go -ne $false -or
        $Receipt.device_gate_decision -ne "UNVERIFIED" -or
        $Receipt.evidence_kind -ne "SIMULATED" -or
        $Receipt.package_contains_integration -ne $false -or
        $Receipt.participant_collection_authorized -ne $false -or
        $Receipt.physical_camera_access_authorized -ne $false) {
        throw "SYNTHETIC_RUN_FAILED"
    }
}

function Invoke-SyntheticRun([string]$Origin, [string]$Token, [string]$RunKind, [string]$IdempotencyKey, [int]$TimeoutSeconds, [int]$ExpectedCount, [int]$ExpectedSequence) {
    $headers = @{
        Authorization = "Bearer $Token"
        Origin = $Origin
        "Idempotency-Key" = $IdempotencyKey
    }
    try {
        $submitted = Invoke-RestMethod -Method Post -Uri "$Origin/api/v1/synthetic-runs" -Headers $headers -ContentType "application/json" -Body (@{ run_kind = $RunKind } | ConvertTo-Json -Compress) -TimeoutSec 5 -UseBasicParsing
    }
    catch { throw "SYNTHETIC_RUN_FAILED" }
    Assert-AuthorityEnvelope $submitted
    $requestId = [string]$submitted.run.request_id
    if ([string]::IsNullOrWhiteSpace($requestId)) { throw "SYNTHETIC_RUN_FAILED" }
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $current = Invoke-RestMethod -Method Get -Uri "$Origin/api/v1/synthetic-runs/$requestId" -Headers @{ Authorization = "Bearer $Token" } -TimeoutSec 5 -UseBasicParsing
        }
        catch { throw "SYNTHETIC_RUN_FAILED" }
        Assert-AuthorityEnvelope $current
        if ($current.run.job_status -eq "TERMINAL") {
            $run = $current.run
            $receipt = $run.receipt
            if ($run.run_kind -ne $RunKind -or $run.run_sequence -ne $ExpectedSequence -or
                $run.schema_version -ne 1 -or $run.service_failure_code -ne $null -or
                $null -eq $receipt) {
                throw "SYNTHETIC_RUN_FAILED"
            }
            Assert-IntegrationReceiptAuthority $receipt
            if ($receipt.integration_status -ne "PERSISTED" -or
                $receipt.d1_outcome -ne "BACKEND_CONTRACT_PASS" -or
                $receipt.observation_count -ne $ExpectedCount -or
                [string]::IsNullOrWhiteSpace([string]$receipt.artifact_sha256) -or
                [string]::IsNullOrWhiteSpace([string]$receipt.d1_receipt_digest)) {
                throw "SYNTHETIC_RUN_FAILED"
            }
            return [pscustomobject]@{
                artifact_sha256 = [string]$receipt.artifact_sha256
                d1_receipt_digest = [string]$receipt.d1_receipt_digest
                request_id = [string]$run.request_id
            }
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "SYNTHETIC_RUN_FAILED"
}

function Get-EvidenceBytes([string]$Origin, [string]$Token, [string]$RequestId) {
    try {
        $response = Invoke-WebRequest -Method Get -Uri "$Origin/api/v1/synthetic-runs/$RequestId/evidence" -Headers @{ Authorization = "Bearer $Token" } -TimeoutSec 15 -UseBasicParsing
        $bytes = Get-Utf8Bytes ([string]$response.Content)
        $header = [string]$response.Headers["X-PDU-Evidence-SHA256"]
    }
    catch { throw "EVIDENCE_EXPORT_FAILED" }
    if ($bytes.Length -gt 4000000 -or (Get-Sha256Bytes $bytes) -ne $header) { throw "EVIDENCE_EXPORT_FAILED" }
    return $bytes
}

function Stop-CandidateTree([Diagnostics.Process]$Process) {
    if ($null -eq $Process -or $Process.HasExited) { throw "PROCESS_CLEANUP_FAILED" }
    $killer = Start-Process -FilePath "taskkill.exe" -ArgumentList @("/PID", [string]$Process.Id, "/T", "/F") -Wait -PassThru -WindowStyle Hidden
    $Process.WaitForExit(15000) | Out-Null
    if ($killer.ExitCode -ne 0 -or -not $Process.HasExited) { throw "PROCESS_CLEANUP_FAILED" }
}

function Invoke-Reproduction([byte[]]$EvidenceBytes) {
    $info = New-CandidateStartInfo "m2synthetic-reproduce" 0 0 $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    if (-not $process.Start()) { throw "REPRODUCTION_FAILED" }
    try {
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.BaseStream.Write($EvidenceBytes, 0, $EvidenceBytes.Length)
        $process.StandardInput.BaseStream.Flush()
        $process.StandardInput.Close()
        if (-not $process.WaitForExit(120000)) {
            & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
            throw "REPRODUCTION_FAILED"
        }
        $stdout = $stdoutTask.Result
        $stderr = $stderrTask.Result
        $exitCode = $process.ExitCode
    }
    finally { $process.Dispose() }
    if ($exitCode -ne 0 -or -not [string]::IsNullOrEmpty($stderr)) { throw "REPRODUCTION_FAILED" }
    try { $receipt = $stdout | ConvertFrom-Json }
    catch { throw "REPRODUCTION_FAILED" }
    if ($receipt.classification -ne "EXACTLY_REPRODUCED" -or $receipt.failure_code -ne $null -or
        $receipt.temporary_workspace_state -ne "REMOVED" -or $receipt.authority_status -ne "AUTHORITY_NOT_ISSUED" -or
        $receipt.clean_machine_verified -eq $true -or $receipt.d1_go -ne $false -or
        $receipt.collection_authorized -ne $false -or $receipt.physical_camera_access_authorized -ne $false -or
        $receipt.source_bundle_sha256 -ne $receipt.reproduced_bundle_sha256 -or
        $receipt.source_artifact_sha256 -ne $receipt.reproduced_artifact_sha256 -or
        $receipt.source_observation_digest -ne $receipt.reproduced_observation_digest -or
        $receipt.source_d1_receipt_digest -ne $receipt.reproduced_d1_receipt_digest -or
        $receipt.source_result_digest -ne $receipt.reproduced_result_digest) {
        throw "REPRODUCTION_FAILED"
    }
    return $receipt
}

function Remove-OwnedRuntime {
    if (-not [IO.Directory]::Exists($RuntimeRoot)) { return }
    $resolvedParent = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd("\")
    $resolvedRuntime = [IO.Path]::GetFullPath($RuntimeRoot).TrimEnd("\")
    if ([IO.Directory]::GetParent($resolvedRuntime).FullName.TrimEnd("\") -ne $resolvedParent -or
        -not [IO.File]::Exists((Join-Path $RuntimeRoot ".owned"))) {
        throw "TEMP_CLEANUP_FAILED"
    }
    $items = @(Get-ChildItem -LiteralPath $RuntimeRoot -Force -Recurse)
    foreach ($item in $items) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "TEMP_CLEANUP_FAILED" }
    }
    Remove-Item -LiteralPath $RuntimeRoot -Force -Recurse
    if ([IO.Directory]::Exists($RuntimeRoot)) { throw "TEMP_CLEANUP_FAILED" }
}

try {
    Assert-PlatformAndUser
    $handoffManifestSha = Assert-HandoffAndCandidate
    if ([IO.Directory]::Exists($RuntimeRoot) -or [IO.File]::Exists($ResponseLeaf)) { throw "TEMP_CLEANUP_FAILED" }
    [IO.Directory]::CreateDirectory($RuntimeRoot) | Out-Null
    [IO.File]::WriteAllText((Join-Path $RuntimeRoot ".owned"), "owned`n", (New-Object Text.UTF8Encoding($false)))
    foreach ($name in @("appdata", "localappdata")) { [IO.Directory]::CreateDirectory((Join-Path $RuntimeRoot $name)) | Out-Null }

    $examPort = New-FreeLoopbackPort
    $monitorPort = New-FreeLoopbackPort
    while ($monitorPort -eq $examPort) { $monitorPort = New-FreeLoopbackPort }
    $serverInfo = New-CandidateStartInfo "m2synthetic" $examPort $monitorPort $false
    $script:ServerProcess = New-Object Diagnostics.Process
    $script:ServerProcess.StartInfo = $serverInfo
    if (-not $script:ServerProcess.Start()) { throw "PROCESS_START_FAILED" }
    $serverOut = $script:ServerProcess.StandardOutput.ReadToEndAsync()
    $serverErr = $script:ServerProcess.StandardError.ReadToEndAsync()
    $examOrigin = "http://127.0.0.1:$examPort"
    $monitorOrigin = "http://localhost:$monitorPort"
    Wait-Health "$examOrigin/api/v1/health"
    Wait-Health "$monitorOrigin/api/v1/health"
    Assert-LoopbackScope @($examPort, $monitorPort) $script:ServerProcess.Id
    $token = Invoke-ReviewerLogin $monitorOrigin
    $preflight = Invoke-SyntheticRun $monitorOrigin $token "PREFLIGHT_60S" "m2-s3e-preflight-0001" 30 977 1
    $nominal = Invoke-SyntheticRun $monitorOrigin $token "NOMINAL_20M" "m2-s3e-nominal-0001" 60 18077 2
    Assert-LoopbackScope @($examPort, $monitorPort) $script:ServerProcess.Id
    $preflightBytes = Get-EvidenceBytes $monitorOrigin $token ([string]$preflight.request_id)
    $nominalBytes = Get-EvidenceBytes $monitorOrigin $token ([string]$nominal.request_id)
    Stop-CandidateTree $script:ServerProcess
    $script:ServerProcess = $null
    $preflightReproduction = Invoke-Reproduction $preflightBytes
    $nominalReproduction = Invoke-Reproduction $nominalBytes
    $null = Assert-HandoffAndCandidate
    Remove-OwnedRuntime

    $authority = [ordered]@{
        authority_status = "AUTHORITY_NOT_ISSUED"
        clean_machine_verified = $false
        collection_authorized = $false
        d1_go = $false
        device_gate_decision = "UNVERIFIED"
        distribution_ready = $false
        execution_authorized = $false
        participant_collection_authorized = $false
        physical_camera_access_authorized = $false
        release_authorized = $false
        research_ready = $false
    }
    $cleanup = [ordered]@{
        candidate_bytes_unchanged = $true
        process_tree_terminated = $true
        temporary_workspace_state = "REMOVED"
    }
    $environment = [ordered]@{
        air_gapped_machine_verified = $false
        child_path_sanitized = $true
        external_environment_classification = "UNVERIFIED_PENDING_SOURCE_IMPORT"
        external_runtime_dependency_supplied = $false
        network_scope = "LOOPBACK_ONLY_OBSERVED"
        process_elevated = $false
        windows_powershell_5_1_or_newer = $true
        windows_x64 = $true
    }
    $handoffBinding = [ordered]@{
        handoff_manifest_sha256 = $handoffManifestSha
        s3d_candidate_tree_sha256 = "64686518c09679f98b6f3c01805535ca9aad50413781424a08020c2460d017e1"
    }
    $projection = [ordered]@{
        nominal_artifact_sha256 = [string]$nominal.artifact_sha256
        nominal_bundle_sha256 = Get-Sha256Bytes $nominalBytes
        nominal_d1_receipt_digest = [string]$nominal.d1_receipt_digest
        nominal_reproduction_result_digest = [string]$nominalReproduction.result_digest
        preflight_artifact_sha256 = [string]$preflight.artifact_sha256
        preflight_bundle_sha256 = Get-Sha256Bytes $preflightBytes
        preflight_d1_receipt_digest = [string]$preflight.d1_receipt_digest
        preflight_reproduction_result_digest = [string]$preflightReproduction.result_digest
    }
    $runContract = [ordered]@{
        candidate_process_count = 3
        full_cycle_count = 1
        nominal_observation_count = 18077
        preflight_observation_count = 977
        reproduction_count = 2
    }
    $body = [ordered]@{
        authority_ceiling = $authority
        cleanup = $cleanup
        environment_observations = $environment
        failure_code = $null
        handoff_binding = $handoffBinding
        projection = $projection
        result = "CLEAN_ENVIRONMENT_PROBE_COMPLETED"
        run_contract = $runContract
    }
    $bodySha = Get-Sha256Bytes (Get-Utf8Bytes (ConvertTo-CanonicalJson $body))
    $document = [ordered]@{
        artifact_kind = "M2_S3E_CLEAN_ENVIRONMENT_RESPONSE"
        body = $body
        body_sha256 = $bodySha
        schema_version = 1
        status = "M2_S3E_CLEAN_ENVIRONMENT_PROBE_COMPLETED_PENDING_IMPORT_VALIDATION"
    }
    Write-CanonicalResult $document 0 $true
}
catch {
    $code = [string]$_.Exception.Message
    if ($null -ne $script:ServerProcess -and -not $script:ServerProcess.HasExited) {
        try { & taskkill.exe /PID $script:ServerProcess.Id /T /F 2>$null | Out-Null } catch { }
    }
    try { Remove-OwnedRuntime } catch { $code = "TEMP_CLEANUP_FAILED" }
    Write-BoundedFailure $code
}
