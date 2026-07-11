$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ProjectDir
try {
    py -3 -m unittest discover -s tests -v
    py -3 -m PyInstaller --noconfirm --clean GBFRTextureFixer.spec
    Write-Host ""
    Write-Host "Build complete: $ProjectDir\dist\GBFRTextureFixer.exe"
}
finally {
    Pop-Location
}
