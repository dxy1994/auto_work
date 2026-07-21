param(
    [Parameter(Mandatory = $true)]
    [string]$PythonExe
)

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workerDir = Join-Path $projectRoot 'worker'
$logDir = Join-Path $workerDir 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$runtimePackages = Join-Path $workerDir '.runtime-site-packages'
$existingPackages = Join-Path $projectRoot '.venv\Lib\site-packages'
$env:PYTHONPATH = @(
    $runtimePackages
    (Join-Path $runtimePackages 'win32')
    (Join-Path $runtimePackages 'win32\lib')
    (Join-Path $runtimePackages 'pythonwin')
    $existingPackages
) -join ';'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $workerDir

& $PythonExe -u -c "import pywin32_bootstrap, runpy; runpy.run_module('game_executor.main', run_name='__main__')" `
    1>> (Join-Path $logDir 'real-order-dry-run.out.log') `
    2>> (Join-Path $logDir 'real-order-dry-run.err.log')
