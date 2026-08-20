# Fuentes de datos

Un script por fuente, con la metodología documentada en su cabecera. Cada uno
escribe a `datos/` y es idempotente: se puede volver a correr sin duplicar nada.

## Pipeline

```
CMF (web)                 cmf_descarga.py  ──> datos/cmf/<rut>/*.zip *.pdf
   │                                            │
   └─ .xbrl ────────────> parse_xbrl.py  ─────> datos/xbrl_facts.csv   (no versionado)
                                                │
imm_serie.csv           ─> ipc.py ────────────>│ datos/ipc.csv
                                                ▼
                                     indicadores.py ──> datos/indicadores.csv  ← lo consume el dash
ESI .rds + esi_2024.csv ──> esi_cise.R ────────────────> datos/cise.csv        ← lo consume el dash
```

## Scripts

| Script | Qué produce | Insumo |
|---|---|---|
| `cmf_descarga.py` | XBRL, EEFF PDF, análisis razonado, memorias, accionistas | web de la CMF, por RUT |
| `parse_xbrl.py` | `datos/xbrl_facts.csv`, un hecho por fila | archivos `.xbrl` |
| `ipc.py` | `datos/ipc.csv`, deflactor anual | `imm_serie.csv`, por argumento o `IMM_SERIE` |
| `indicadores.py` | `datos/indicadores.csv`, la serie del dash, cortada en 2019 | los tres anteriores |
| `esi_cise.R` | `datos/cise.csv`, fuerza de trabajo por CISE | microdatos ESI |

## Orden para reconstruir todo

```bash
py scripts/fuentes/cmf_descarga.py eeff 91705000 --desde 2009 --hasta 2019 --docs xbrl
py scripts/fuentes/cmf_descarga.py eeff 93834000 --desde 2009 --hasta 2019 --docs xbrl
py scripts/fuentes/parse_xbrl.py datos/xbrl -o datos/xbrl_facts.csv
py scripts/fuentes/ipc.py --base 2025
py scripts/fuentes/indicadores.py
Rscript scripts/fuentes/esi_cise.R
```

En Windows, R y Quarto están instalados pero no en el PATH:

```powershell
$env:PATH = "C:\Program Files\R\R-4.4.3\bin;C:\Program Files\RStudio\resources\app\bin\quarto\bin;$env:PATH"
```

## Chequeos

Ninguno usa framework: cada script falla solo si su lógica se rompe.

- `parse_xbrl.py --self-check <dir> <CencoQuinenco.csv>` reproduce el export
  ad-hoc que existía antes. Clasifica aparte los artefactos de Excel de esa
  referencia (redondeos, fechas serializadas, filas de relleno) y exige
  coincidencia exacta desde 2012, que es cuando la taxonomía se estabiliza.
  Estado actual: **0 discrepancias en 2012+**.
- `ipc.py` verifica que la serie recuperada reproduzca la inflación oficial
  dic-dic de 2021-2024 dentro de 0,5 puntos.
- `indicadores.py` exige que los ratios caigan en rango plausible y que el
  patrimonio real sea positivo en toda la serie.
- `esi_cise.R` verifica que las proporciones de cada año sumen 1.

## Lo que no está automatizado

- **`imm_serie.csv`.** Se produce en otro pipeline; acá solo se lee, y la ruta
  va por argumento o por la variable `IMM_SERIE`. `datos/ipc.csv` ya viene
  versionado, así que solo hace falta para regenerarlo.
- **Microdatos ESI.** No tienen URL de descarga estable.
