$ErrorActionPreference = 'Stop'
$installerScript = Join-Path $PSScriptRoot 'install_plugin.py'
$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue

if ($pythonLauncher) {
    & $pythonLauncher.Source -3 $installerScript
} else {
    $pythonExecutable = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $pythonExecutable) {
        Write-Error 'Python 3.10+ is required. Install Python and its py launcher first.'
        exit 1
    }
    & $pythonExecutable.Source $installerScript
}
exit $LASTEXITCODE
