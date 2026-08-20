# MVP postdoc 2027

Piloto de visualización para la postulación de Felipe Ruiz Bruzzone. Tres entradas al
mismo problema: cómo se diferencia internamente el campo empresarial chileno, quiénes
ocupan su cúspide, y qué muestra la información financiera de las empresas que controlan.

**Todo está circunscrito a 2019**, el corte del análisis de la tesis, y la sección 3
cubre los dos casos trabajados ahí: Quiñenco (Luksic) y Cencosud (Paulmann), con estados
financieros de 2009 a 2019.

## Renderizar

```powershell
$env:PATH = "C:\Program Files\R\R-4.4.3\bin;C:\Program Files\RStudio\resources\app\bin\quarto\bin;$env:PATH"
quarto render
```

El sitio queda en `_site/`. Abre con doble clic desde el disco: la sección 3 lleva los
datos embebidos con `ojs_define` y no los pide por `fetch`, así que no hace falta
levantar un servidor local para probar la interactividad.

## Publicar

`.github/workflows/publish.yml` renderiza y sube a GitHub Pages en cada push. Para que
el URL exista hay que activarlo una vez:

> Settings → Pages → Source: **GitHub Actions**

No es "Deploy from a branch": el sitio no está commiteado, se construye en el runner.

## Estructura

| Archivo | Qué es |
|---|---|
| `index.qmd` | Portada, alcance del piloto y lo que queda pendiente |
| `01-clase.qmd` | Estructura de clase: ESI, SII y ELE 2019 con análisis de correspondencias |
| `02-grupos.qmd` | Grupos económicos: ranking Forbes agrupado por familia |
| `03-mapa.qmd` | Mapa de la extrema riqueza: CMF/XBRL, la única sección interactiva |
| `R/setup.R` | Tema, formatos y el corte de 2019 |
| `scripts/fuentes/` | Descarga y procesamiento, un script por fuente |
| `datos/` | Lo procesado, más los insumos originales del repo |
| `codigo/` | Los scripts originales de la tesis |

## Datos

```powershell
py scripts/fuentes/cmf_descarga.py eeff 91705000 --desde 2009 --hasta 2019 --docs xbrl
py scripts/fuentes/cmf_descarga.py eeff 93834000 --desde 2009 --hasta 2019 --docs xbrl
py scripts/fuentes/parse_xbrl.py datos/xbrl -o datos/xbrl_facts.csv
py scripts/fuentes/ipc.py --base 2025
py scripts/fuentes/indicadores.py
Rscript scripts/fuentes/esi_cise.R
```

O `pwsh scripts/bajar_todo.ps1`, que hace todo eso seguido. Los XBRL crudos de la CMF no
se versionan porque son cientos de MB y se rebajan con el primer paso.

Cada script documenta su metodología en la cabecera y trae sus propios chequeos: ver
`scripts/README.md`.
