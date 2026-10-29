#Requires -Version 7.0
# TASK-CWT-000 infrastructure checks only; no Python, packages, or real data.
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ($repoRoot -ne 'D:\Code\Python_Projects\DPS_Studio_CWT') {
    throw 'Run this check only in the independent CWT repository.'
}
$environmentScript = Join-Path $PSScriptRoot 'cwt_env.ps1'
$checks = [Collections.Generic.List[object]]::new()

function Assert-Check {
    param([string] $Name, [bool] $Condition)
    $checks.Add([pscustomobject]@{ name = $Name; passed = $Condition })
    if (-not $Condition) { throw "Check failed: $Name" }
}

$tokens = $null
$parseErrors = $null
[void][Management.Automation.Language.Parser]::ParseFile(
    $environmentScript, [ref] $tokens, [ref] $parseErrors
)
Assert-Check 'PowerShell parser accepts cwt_env.ps1' ($parseErrors.Count -eq 0)
$previousPreference = $ErrorActionPreference
Set-Location -LiteralPath (Join-Path $repoRoot 'docs')
. $environmentScript
Assert-Check 'Dot-source returns location to exact repository root' ((Get-Location).Path -eq $repoRoot)
Assert-Check 'Caller ErrorActionPreference is preserved' ($ErrorActionPreference -eq $previousPreference)
Assert-Check 'Helper does not leak into caller' (-not (Test-Path Function:\Assert-CwtDirectoryPath))
Assert-Check 'PYTHONPATH is empty' ([string]::IsNullOrEmpty($env:PYTHONPATH))

$cacheRoot = Join-Path $repoRoot '.local_cache'
$environmentNames = @(
    'PYTHONPYCACHEPREFIX', 'RUFF_CACHE_DIR', 'MYPY_CACHE_DIR', 'MPLCONFIGDIR',
    'PIP_CACHE_DIR', 'UV_CACHE_DIR', 'XDG_CACHE_HOME', 'NUMBA_CACHE_DIR',
    'TEMP', 'TMP', 'TMPDIR', 'UV_PROJECT_ENVIRONMENT'
)
$observed = [ordered]@{}
foreach ($name in $environmentNames) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    $observed[$name] = $value
    Assert-Check "$name is an existing directory under .local_cache" (
        $value.StartsWith($cacheRoot + '\', [StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $value -PathType Container)
    )
}
$observed['PYTEST_ADDOPTS'] = $env:PYTEST_ADDOPTS
$expectedOptions = '--basetemp="{0}/pytest_tmp" -o cache_dir="{0}/pytest_cache"' -f $cacheRoot.Replace('\', '/')
Assert-Check 'pytest options use absolute central cache/tmp paths' ($env:PYTEST_ADDOPTS -eq $expectedOptions)
$before = $observed | ConvertTo-Json -Compress
. $environmentScript
$after = [ordered]@{}
foreach ($name in $observed.Keys) { $after[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
Assert-Check 'Repeated sourcing is idempotent' (($after | ConvertTo-Json -Compress) -eq $before)

# Wrong-root execution uses a uniquely named copy within disposable cache only.
$testDirectory = Join-Path $cacheRoot ('scaffold_check_' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $testDirectory) { throw 'Refusing to reuse a test directory.' }
[void][IO.Directory]::CreateDirectory($testDirectory)
$wrongRootScript = Join-Path $testDirectory 'cwt_env.ps1'
[IO.File]::Copy($environmentScript, $wrongRootScript, $false)
$message = ''
try { . $wrongRootScript } catch { $message = $_.Exception.Message }
Assert-Check 'Wrong-root copy is refused' ($message -like 'CWT cache setup refused: expected*')
Assert-Check 'Wrong-root refusal preserves environment' ($env:PYTEST_ADDOPTS -eq $expectedOptions)

function Invoke-MetadataRejection {
    param([ValidateSet('Reparse', 'File')] [string] $Scenario)
    # Mock metadata only: no real symlink/junction or outside-repo access.
    function Get-Item {
        param([string] $LiteralPath, [switch] $Force)
        $blockedPath = if ($Scenario -eq 'Reparse') { $cacheRoot } else { Join-Path $cacheRoot 'ruff' }
        if ($LiteralPath -eq $blockedPath) {
            $metadata = [pscustomobject]@{
                Attributes = $(if ($Scenario -eq 'Reparse') { [IO.FileAttributes]::ReparsePoint } else { [IO.FileAttributes]::Normal })
                PSIsContainer = ($Scenario -eq 'Reparse')
                FullName = $LiteralPath
            }
            $metadata | Add-Member -MemberType ScriptMethod -Name ResolveLinkTarget -Value {
                param([bool] $FinalTarget)
                [pscustomobject]@{ FullName = 'D:\simulated-external-target' }
            }
            return $metadata
        }
        Microsoft.PowerShell.Management\Get-Item @PSBoundParameters
    }
    $priorTemp = $env:TEMP
    $priorLocation = (Get-Location).Path
    $message = ''
    try { . $environmentScript } catch { $message = $_.Exception.Message }
    $expected = if ($Scenario -eq 'Reparse') { '*reparse point*' } else { '*directory required*' }
    Assert-Check "$Scenario metadata is refused before environment/location mutation" (
        $message -like $expected -and $env:TEMP -eq $priorTemp -and
        (Get-Location).Path -eq $priorLocation
    )
}
Invoke-MetadataRejection Reparse
Invoke-MetadataRejection File

[pscustomobject]@{
    task = 'TASK-CWT-000'
    time = [DateTimeOffset]::Now.ToString('o')
    powershell_version = $PSVersionTable.PSVersion.ToString()
    checks = $checks.ToArray()
    passed = @($checks | Where-Object passed).Count
    failed = @($checks | Where-Object { -not $_.passed }).Count
    environment = $observed
    wrong_root_copy = $wrongRootScript
    rejection_test_boundary = 'Reparse/file failure cases use mocked metadata; no real links created.'
    python_or_package_tools_run = $false
}
