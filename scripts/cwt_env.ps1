#Requires -Version 7.0
# Dot-source before Python or development tools: . .\scripts\cwt_env.ps1
# Process-local environment only; no installs, Git mutations, or cleanup.
# A child scope prevents helper functions and preferences leaking into the caller.
& {
    param([string] $ScriptDirectory)

    $ErrorActionPreference = 'Stop'
    if ($PSVersionTable.PSEdition -ne 'Core') {
        throw 'CWT cache setup refused: PowerShell 7 is required.'
    }

    $expectedRepoRoot = 'D:\Code\Python_Projects\DPS_Studio_CWT'
    $repoRoot = [IO.Path]::GetFullPath((Join-Path $ScriptDirectory '..'))
    if (-not [string]::Equals(
            $repoRoot.TrimEnd('\'), $expectedRepoRoot.TrimEnd('\'),
            [StringComparison]::OrdinalIgnoreCase
        )) {
        throw "CWT cache setup refused: expected $expectedRepoRoot; resolved $repoRoot"
    }

    function Assert-CwtDirectoryPath {
        param([string] $Path)

        # Inspect every existing ancestor before any mkdir or environment change.
        $cursor = [IO.Path]::GetFullPath($Path)
        while ($cursor) {
            if (Test-Path -LiteralPath $cursor) {
                $item = Get-Item -LiteralPath $cursor -Force
                if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    $target = $item.ResolveLinkTarget($true)
                    throw "CWT cache setup refused: reparse point $cursor -> $($target.FullName)"
                }
                if (-not $item.PSIsContainer) {
                    throw "CWT cache setup refused: directory required at $cursor"
                }
            }
            $parent = [IO.Path]::GetDirectoryName($cursor)
            if ($parent -eq $cursor) { break }
            $cursor = $parent
        }
    }

    Assert-CwtDirectoryPath $repoRoot
    Assert-CwtDirectoryPath $ScriptDirectory
    Assert-CwtDirectoryPath (Join-Path $repoRoot '.git')
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot '.git') -PathType Container)) {
        throw 'CWT cache setup refused: expected the independent repository .git directory.'
    }
    $scriptFile = Get-Item -LiteralPath (Join-Path $ScriptDirectory 'cwt_env.ps1') -Force
    if (($scriptFile.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        $target = $scriptFile.ResolveLinkTarget($true)
        throw "CWT cache setup refused: script is a reparse point -> $($target.FullName)"
    }

    $cacheRoot = Join-Path $repoRoot '.local_cache'
    $environmentPaths = [ordered]@{
        PYTHONPYCACHEPREFIX = Join-Path $cacheRoot 'pycache'
        RUFF_CACHE_DIR = Join-Path $cacheRoot 'ruff'
        MYPY_CACHE_DIR = Join-Path $cacheRoot 'mypy'
        MPLCONFIGDIR = Join-Path $cacheRoot 'matplotlib'
        PIP_CACHE_DIR = Join-Path $cacheRoot 'pip'
        UV_CACHE_DIR = Join-Path $cacheRoot 'uv'
        XDG_CACHE_HOME = Join-Path $cacheRoot 'xdg'
        NUMBA_CACHE_DIR = Join-Path $cacheRoot 'numba'
        TEMP = Join-Path $cacheRoot 'tmp'
        TMP = Join-Path $cacheRoot 'tmp'
        TMPDIR = Join-Path $cacheRoot 'tmp'
        UV_PROJECT_ENVIRONMENT = Join-Path $cacheRoot 'venv'
    }
    $pytestCache = Join-Path $cacheRoot 'pytest_cache'
    $pytestTemporary = Join-Path $cacheRoot 'pytest_tmp'
    $directories = @($cacheRoot, $pytestCache, $pytestTemporary) + @($environmentPaths.Values)

    # Validate the complete set before writing; reject even internal junctions.
    foreach ($directory in $directories) {
        if (-not $directory.StartsWith($repoRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw "CWT cache setup refused: path outside repository: $directory"
        }
        Assert-CwtDirectoryPath $directory
    }
    foreach ($directory in $directories) {
        [void][IO.Directory]::CreateDirectory($directory)
    }

    foreach ($entry in $environmentPaths.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
    $env:PYTHONPATH = $null
    # Absolute, quoted pytest paths remain central when invoked from a subfolder.
    $env:PYTEST_ADDOPTS = '--basetemp="{0}" -o cache_dir="{1}"' -f (
        $pytestTemporary.Replace('\', '/'), $pytestCache.Replace('\', '/')
    )
    Set-Location -LiteralPath $repoRoot
    Write-Host "CWT environment ready. Root: $repoRoot"
    Write-Host "Disposable caches: $cacheRoot"
    Write-Host 'Persistent experiment outputs: artifacts/TASK-CWT-XXX/'
    Write-Host 'No interpreter selected; any future venv belongs at .local_cache/venv/.'
} $PSScriptRoot
