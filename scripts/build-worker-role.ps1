[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("monitor", "game-executor")]
    [string]$Role,

    [switch]$SkipDependencyInstall,
    [switch]$RecreateEnvironment,
    [switch]$KeepBuildArtifacts
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $ScriptDirectory ".."))
$WorkerDirectory = Join-Path $ProjectRoot "worker"
$RoleSlug = $Role
$RoleTitle = if ($Role -eq "monitor") { "Monitor Worker" } else { "Game Executor Worker" }
$ExecutableName = if ($Role -eq "monitor") { "auto-monitor.exe" } else { "auto-game-executor.exe" }
$EntryPoint = if ($Role -eq "monitor") { "monitor\main.py" } else { "game_executor\main.py" }
$RequirementFile = Join-Path $WorkerDirectory $(
    if ($Role -eq "monitor") { "requirements-monitor.txt" } else { "requirements-game-executor.txt" }
)
$EnvironmentTemplate = Join-Path $WorkerDirectory $(
    if ($Role -eq "monitor") { ".env.monitor.example" } else { ".env.game-executor.example" }
)
$BuildRequirementFile = Join-Path $WorkerDirectory "requirements-build.txt"
$CommonRequirementFile = Join-Path $WorkerDirectory "requirements-common.txt"
$VirtualEnvironment = Join-Path $ProjectRoot ".venv-$RoleSlug"
$VirtualPython = Join-Path $VirtualEnvironment "Scripts\python.exe"
$DistributionDirectory = Join-Path $WorkerDirectory "dist\$RoleSlug"
$BuildDirectory = Join-Path $WorkerDirectory "build\$RoleSlug"
$SpecName = [IO.Path]::GetFileNameWithoutExtension($ExecutableName)
$SpecFile = Join-Path $WorkerDirectory "$SpecName.spec"
$PackageFile = Join-Path $WorkerDirectory "dist\$SpecName-windows-x64.zip"
$CheckScript = Join-Path $ScriptDirectory "check-worker-package.bat"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-LastExitCode([string]$Message) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Message (exit code $LASTEXITCODE)"
    }
}

function Assert-SafeGeneratedPath([string]$Path) {
    $resolvedWorker = [IO.Path]::GetFullPath($WorkerDirectory).TrimEnd("\")
    $resolvedPath = [IO.Path]::GetFullPath($Path).TrimEnd("\")
    if (
        $resolvedPath -eq $resolvedWorker -or
        -not $resolvedPath.StartsWith(
            $resolvedWorker + "\",
            [StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "Refusing to clean path outside worker output directories: $resolvedPath"
    }
}

function Remove-GeneratedPath([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    Assert-SafeGeneratedPath $Path
    Remove-Item -LiteralPath $Path -Recurse -Force
}

function Test-Python([string]$Candidate) {
    if ([string]::IsNullOrWhiteSpace($Candidate) -or -not (Test-Path -LiteralPath $Candidate)) {
        return $false
    }
    try {
        & $Candidate -c "import platform,sys,venv; assert sys.version_info >= (3,10) and sys.version_info < (3,13); assert platform.architecture()[0] == '64bit'" 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Find-BootstrapPython {
    $candidates = [Collections.Generic.List[string]]::new()
    if ($env:PYTHON_EXE) {
        $candidates.Add($env:PYTHON_EXE)
    }

    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $candidates.Add($pythonCommand.Source)
    }

    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $launchedPython = & $pyLauncher.Source -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $launchedPython) {
                $candidates.Add(($launchedPython | Select-Object -First 1))
            }
        }
        catch {
            # Continue with explicit installation paths below.
        }
    }

    foreach ($candidate in @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    )) {
        $candidates.Add($candidate)
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Python $candidate) {
            return [IO.Path]::GetFullPath($candidate)
        }
    }
    return $null
}

function Get-RequirementsHash {
    $content = @(
        Get-Content -LiteralPath $BuildRequirementFile -Raw
        Get-Content -LiteralPath $CommonRequirementFile -Raw
        Get-Content -LiteralPath $RequirementFile -Raw
    ) -join "`n"
    $bytes = [Text.Encoding]::UTF8.GetBytes($content)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "")
    }
    finally {
        $sha.Dispose()
    }
}

function Get-GitCommit {
    $git = Get-Command git.exe -ErrorAction SilentlyContinue
    if (-not $git) {
        return "unknown"
    }
    $commit = & $git.Source -C $ProjectRoot rev-parse HEAD 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $commit) {
        return "unknown"
    }
    return ($commit | Select-Object -First 1).Trim()
}

function Invoke-PythonCode([string]$Python, [string]$Code) {
    # Windows PowerShell 5.1 can strip nested quotes from multiline native
    # arguments. Base64 keeps the preflight code a single unambiguous argument.
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Code))
    & $Python -c "import base64;exec(base64.b64decode('$encoded'))"
}

Write-Host "============================================================"
Write-Host "  $RoleTitle Windows x64 package build"
Write-Host "============================================================"
Write-Host "Project: $ProjectRoot"
Write-Host "Output : $DistributionDirectory"

foreach ($requiredPath in @(
    $RequirementFile,
    $CommonRequirementFile,
    $BuildRequirementFile,
    $EnvironmentTemplate,
    $CheckScript,
    (Join-Path $WorkerDirectory $EntryPoint)
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required build input is missing: $requiredPath"
    }
}

if ($RecreateEnvironment -and (Test-Path -LiteralPath $VirtualEnvironment)) {
    Write-Step "Recreating isolated build environment"
    $resolvedVenv = [IO.Path]::GetFullPath($VirtualEnvironment)
    if (-not $resolvedVenv.StartsWith(
        [IO.Path]::GetFullPath($ProjectRoot).TrimEnd("\") + "\.venv-",
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to remove unexpected virtual environment: $resolvedVenv"
    }
    Remove-Item -LiteralPath $VirtualEnvironment -Recurse -Force
}

if ((Test-Path -LiteralPath $VirtualPython) -and -not (Test-Python $VirtualPython)) {
    Write-Warning "The existing role build environment is invalid and will be recreated."
    Remove-Item -LiteralPath $VirtualEnvironment -Recurse -Force
}

if (-not (Test-Path -LiteralPath $VirtualPython)) {
    Write-Step "Creating isolated Python environment"
    $BootstrapPython = Find-BootstrapPython
    if (-not $BootstrapPython) {
        throw "Python 3.10-3.12 x64 was not found. Install it or set PYTHON_EXE."
    }
    Write-Host "Bootstrap Python: $BootstrapPython"
    & $BootstrapPython -m venv $VirtualEnvironment
    Assert-LastExitCode "Failed to create $VirtualEnvironment"
}

$PythonDescription = & $VirtualPython -c "import platform,sys; print(f'{sys.version.split()[0]} {platform.architecture()[0]}')"
Assert-LastExitCode "Unable to inspect build Python"
Write-Host "Build Python: $PythonDescription"

if (-not $SkipDependencyInstall) {
    Write-Step "Installing pinned build and $Role runtime dependencies"
    & $VirtualPython -m pip install `
        --disable-pip-version-check `
        -r $BuildRequirementFile `
        -r $RequirementFile
    Assert-LastExitCode "Dependency installation failed"
}
else {
    Write-Step "Skipping dependency installation by request"
}

Write-Step "Running dependency preflight"
if ($Role -eq "monitor") {
    $PreflightCode = @"
import boto3, bs4, patchright, pygame, requests, websockets, win32com.client
import common, monitor
from monitor.monitoring.registry import MONITOR_REGISTRY
assert {1, 2, 3}.issubset(set(MONITOR_REGISTRY))
print("monitor dependency preflight passed")
"@
}
else {
    $PreflightCode = @"
import boto3, cv2, numpy, paddle, paddleocr, paddlex, PIL, websockets, win32api, win32gui
import common, game_executor
from game_executor.executor.lineage_classic import LineageClassicExecutor
print("game executor dependency preflight passed")
"@
}
Push-Location $WorkerDirectory
try {
    Invoke-PythonCode $VirtualPython $PreflightCode
    Assert-LastExitCode "$Role dependency preflight failed"
}
finally {
    Pop-Location
}

Write-Step "Cleaning generated role output"
Remove-GeneratedPath $DistributionDirectory
Remove-GeneratedPath $BuildDirectory
if (Test-Path -LiteralPath $SpecFile) {
    Remove-Item -LiteralPath $SpecFile -Force
}
New-Item -ItemType Directory -Path $DistributionDirectory -Force | Out-Null

$PyInstallerArguments = @(
    "-m", "PyInstaller",
    "--onefile",
    "--console",
    "--clean",
    "--noconfirm",
    "--name", $SpecName,
    "--distpath", $DistributionDirectory,
    "--workpath", $BuildDirectory,
    "--specpath", $WorkerDirectory,
    "--collect-submodules", "common",
    "--add-data", "$EnvironmentTemplate;.",
    "--exclude-module", "tests"
)

if ($Role -eq "monitor") {
    $PyInstallerArguments += @(
        "--collect-submodules", "monitor",
        "--collect-all", "patchright",
        "--hidden-import", "pythoncom",
        "--hidden-import", "pywintypes",
        "--hidden-import", "win32com.client",
        "--hidden-import", "bs4",
        "--exclude-module", "game_executor",
        "--exclude-module", "paddle",
        "--exclude-module", "paddleocr",
        "--exclude-module", "paddlex",
        "--exclude-module", "cv2"
    )
}
else {
    $ImageDirectory = Join-Path $WorkerDirectory "game_executor\executor\lineage_classic\images"
    if (-not (Test-Path -LiteralPath $ImageDirectory)) {
        throw "Game recognition image directory is missing: $ImageDirectory"
    }
    $PyInstallerArguments += @(
        "--collect-submodules", "game_executor",
        "--collect-all", "paddle",
        "--collect-all", "paddleocr",
        "--collect-all", "paddlex",
        "--hidden-import", "pythoncom",
        "--hidden-import", "pywintypes",
        "--hidden-import", "win32com.client",
        "--add-data", "$ImageDirectory;game_executor\executor\lineage_classic\images",
        "--exclude-module", "monitor",
        "--exclude-module", "patchright",
        "--exclude-module", "playwright",
        "--exclude-module", "pygame"
    )
}
$PyInstallerArguments += (Join-Path $WorkerDirectory $EntryPoint)

Write-Step "Building $ExecutableName"
Push-Location $WorkerDirectory
try {
    & $VirtualPython @PyInstallerArguments
    Assert-LastExitCode "PyInstaller build failed"
}
finally {
    Pop-Location
}

$ExecutablePath = Join-Path $DistributionDirectory $ExecutableName
if (-not (Test-Path -LiteralPath $ExecutablePath)) {
    throw "PyInstaller did not produce $ExecutablePath"
}
if ((Get-Item -LiteralPath $ExecutablePath).Length -lt 1MB) {
    throw "Built executable is unexpectedly small: $ExecutablePath"
}

Write-Step "Preparing deployment files"
Copy-Item -LiteralPath $EnvironmentTemplate `
    -Destination (Join-Path $DistributionDirectory ".env.example") -Force
# Never package worker\.env: it may contain real credentials from the build machine.
Copy-Item -LiteralPath $EnvironmentTemplate `
    -Destination (Join-Path $DistributionDirectory ".env") -Force
Copy-Item -LiteralPath $CheckScript `
    -Destination (Join-Path $DistributionDirectory "check-package.bat") -Force

$RequirementsHash = Get-RequirementsHash
$BuildInfo = @(
    "role=$Role",
    "executable=$ExecutableName",
    "built_at_utc=$([DateTime]::UtcNow.ToString("o"))",
    "git_commit=$(Get-GitCommit)",
    "python=$PythonDescription",
    "requirements_sha256=$RequirementsHash"
) -join "`r`n"
Set-Content -LiteralPath (Join-Path $DistributionDirectory "build-info.txt") `
    -Value $BuildInfo -Encoding ASCII

$DeploymentText = if ($Role -eq "monitor") {
@"
1. Edit .env and set BACKEND_WS_URL and storage settings.
2. Ensure 64-bit Chrome or Edge is installed.
3. Run check-package.bat to verify and start auto-monitor.exe.
4. Browser profiles are stored in the user_data directory beside the EXE.
"@
}
else {
@"
1. Edit .env and set BACKEND_WS_URL plus the STORAGE_* RustFS settings.
2. Bind this machine to a Wireless HID device in the controller.
3. Keep the game client at 800x600 and run check-package.bat.
4. OCR models are downloaded to the PaddleX cache on first use.
"@
}
Set-Content -LiteralPath (Join-Path $DistributionDirectory "DEPLOYMENT.txt") `
    -Value $DeploymentText -Encoding UTF8

$ExecutableHash = (Get-FileHash -LiteralPath $ExecutablePath -Algorithm SHA256).Hash
Set-Content -LiteralPath (Join-Path $DistributionDirectory "$ExecutableName.sha256") `
    -Value $ExecutableHash -Encoding ASCII

Write-Step "Running packaged executable self-check"
Push-Location $DistributionDirectory
try {
    & $ExecutablePath --self-check
    Assert-LastExitCode "Packaged executable self-check failed"
}
finally {
    Pop-Location
}

Write-Step "Creating deployment ZIP"
if (Test-Path -LiteralPath $PackageFile) {
    Remove-Item -LiteralPath $PackageFile -Force
}
$PackageInputs = Get-ChildItem -LiteralPath $DistributionDirectory -Force |
    Select-Object -ExpandProperty FullName
Compress-Archive `
    -LiteralPath $PackageInputs `
    -DestinationPath $PackageFile `
    -CompressionLevel Optimal `
    -Force

if (-not $KeepBuildArtifacts) {
    Remove-GeneratedPath $BuildDirectory
    if (Test-Path -LiteralPath $SpecFile) {
        Remove-Item -LiteralPath $SpecFile -Force
    }
}

$ExecutableSizeMb = [Math]::Round((Get-Item $ExecutablePath).Length / 1MB, 1)
$PackageSizeMb = [Math]::Round((Get-Item $PackageFile).Length / 1MB, 1)
Write-Host ""
Write-Host "[SUCCESS] $RoleTitle package is ready." -ForegroundColor Green
Write-Host "EXE : $ExecutablePath ($ExecutableSizeMb MB)"
Write-Host "ZIP : $PackageFile ($PackageSizeMb MB)"
Write-Host "SHA : $ExecutableHash"
