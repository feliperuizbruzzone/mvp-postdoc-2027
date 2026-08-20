# Renderiza el sitio.
#
# Uso:  .\scripts\build.ps1

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

quarto render
if ($LASTEXITCODE -ne 0) { throw "falló el render" }

Write-Host "`nListo. _site/" -ForegroundColor Green
