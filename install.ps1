# Self-contained bootstrap: supports Invoke-RestMethod ... | Invoke-Expression.
& {
    $ErrorActionPreference = 'Stop'
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    $pythonExecutable = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $pythonLauncher -and -not $pythonExecutable) {
        throw 'Python 3.10+ is required. Install Python and its py launcher first.'
    }
    $bootstrapFile = Join-Path ([IO.Path]::GetTempPath()) ('playbook-bootstrap-' + [guid]::NewGuid().ToString('N') + '.py')
    try {
        Invoke-WebRequest -UseBasicParsing -ErrorAction Stop `
            -Uri 'https://raw.githubusercontent.com/JingchaoGu/Testing/main/scripts/install_plugin.py' `
            -OutFile $bootstrapFile
        if ($pythonLauncher) {
            & $pythonLauncher.Source -3 $bootstrapFile
        } else {
            & $pythonExecutable.Source $bootstrapFile
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Playbook Testing installer failed with exit code $LASTEXITCODE."
        }
    } finally {
        Remove-Item -LiteralPath $bootstrapFile -Force -ErrorAction SilentlyContinue
    }
}
