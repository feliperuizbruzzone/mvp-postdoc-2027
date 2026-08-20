# Descarga los XBRL de la CMF y reconstruye los indicadores.
#
# Solo XBRL: los PDF de estados financieros pesan ~8 MB por año y por empresa, y
# el pipeline no los usa. Para bajarlos, correr cmf_descarga.py sin --docs.
#
# Idempotente: no vuelve a bajar lo que ya está. Se puede interrumpir y reanudar.
#
# Uso:  pwsh scripts/bajar_todo.ps1

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# RUT verificados contra la ficha de la CMF (pestaña 1, Identificación).
$empresas = [ordered]@{
    "91705000" = "Quinenco (Luksic)"
    "93834000" = "Cencosud (Paulmann)"
}

foreach ($rut in $empresas.Keys) {
    Write-Host "`n=== $($empresas[$rut]) — RUT $rut ===" -ForegroundColor Cyan
    py scripts/fuentes/cmf_descarga.py eeff $rut --desde 2009 --hasta 2019 --docs xbrl
}

Write-Host "`n=== Descomprimiendo los XBRL ===" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path datos/xbrl | Out-Null
$n = 0
foreach ($z in Get-ChildItem datos/cmf -Recurse -Filter *_xbrl.zip) {
    Expand-Archive -Path $z.FullName -DestinationPath datos/xbrl -Force
    $n++
}
Write-Host "$n archivos descomprimidos en datos/xbrl"

Write-Host "`n=== Reconstruyendo los indicadores ===" -ForegroundColor Cyan
py scripts/fuentes/parse_xbrl.py datos/xbrl -o datos/xbrl_facts.csv
py scripts/fuentes/indicadores.py
