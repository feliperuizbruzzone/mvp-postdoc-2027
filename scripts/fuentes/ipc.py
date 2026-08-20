"""
MAPA - Deflactor anual (IPC) para expresar los montos en pesos constantes.

FUENTE Y POR QUÉ ESTE CAMINO

La serie primaria es el IPC empalmado del Banco Central, F074.IPC.IND.Z.EP23.C.M.
La API del BCCh exige credenciales, y montarlas acá dejaría el repo dependiendo de
una infraestructura externa. En vez de eso el índice se recupera aritméticamente de
un archivo ya publicado:

    imm_serie.csv  tiene imm_nominal e imm_real, con
                   imm_real = imm_nominal x ipc(base) / ipc(mes)
    por lo tanto   imm_nominal / imm_real = ipc(mes) / ipc(base)

que es exactamente el factor que se necesita, sin credenciales ni red.

VALIDACIÓN

Las inflaciones anuales que salen de la serie recuperada reproducen la serie
oficial: 2021 7,2%, 2022 12,8%, 2023 3,9%, 2024 4,5%. El self-check de abajo
verifica que se mantengan dentro de tolerancia.

LIMITACIÓN

imm_serie.csv arranca en 2010-01, así que no hay diciembre de 2009. Para el año
2009 se usa 2010-01, lo que subestima el deflactor en torno a 0,3%. Afecta solo a
la primera observación de las series en pesos constantes.

Uso:  py scripts/fuentes/ipc.py [ruta/a/imm_serie.csv] [--base 2025]
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

# Ruta al imm_serie.csv del pipeline que lo publica. Va por argumento o por la
# variable de entorno IMM_SERIE: no hay un default portable. datos/ipc.csv ya
# viene versionado, asi que esto solo hace falta para regenerarlo.
IMM_DEFECTO = Path(os.environ.get("IMM_SERIE", "datos/imm_serie.csv"))

# Inflación anual oficial (dic-dic) para validar la serie recuperada.
INFLACION_CONOCIDA = {2021: 7.2, 2022: 12.8, 2023: 3.9, 2024: 4.5}


def indice_mensual(ruta: Path) -> dict[str, float]:
    """mes 'YYYY-MM' -> ipc(mes)/ipc(base), recuperado del IMM nominal y real."""
    serie = {}
    with ruta.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                nominal, real = float(r["imm_nominal"]), float(r["imm_real"])
            except (ValueError, KeyError):
                continue
            if real:
                serie[r["fecha"]] = nominal / real
    if not serie:
        raise SystemExit(f"No se pudo recuperar el índice desde {ruta}")
    return serie


def indice_anual(mensual: dict[str, float]) -> dict[int, float]:
    """Diciembre de cada año. 2009 toma 2010-01, el mes más temprano disponible."""
    anual = {}
    for mes, v in mensual.items():
        anio, m = mes.split("-")
        if m == "12":
            anual[int(anio)] = v
    primer_mes = min(mensual)
    anual.setdefault(int(primer_mes[:4]) - 1, mensual[primer_mes])
    return anual


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("imm", type=Path, nargs="?", default=IMM_DEFECTO)
    p.add_argument("--base", type=int, default=None,
                   help="año base de los pesos constantes (default: último diciembre completo)")
    p.add_argument("-o", "--salida", type=Path, default=Path("datos/ipc.csv"))
    a = p.parse_args()

    anual = indice_anual(indice_mensual(a.imm))
    base = a.base or max(anual)
    if base not in anual:
        raise SystemExit(f"No hay diciembre de {base} en la serie (últimos: {sorted(anual)[-3:]})")

    filas = [
        {
            "anio": anio,
            "indice": round(anual[anio], 6),
            "deflactor": round(anual[base] / anual[anio], 6),
            "inflacion_anual": (
                round((anual[anio] / anual[anio - 1] - 1) * 100, 2)
                if anio - 1 in anual else ""
            ),
        }
        for anio in sorted(anual)
    ]

    a.salida.parent.mkdir(parents=True, exist_ok=True)
    with a.salida.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["anio", "indice", "deflactor", "inflacion_anual"])
        w.writeheader()
        w.writerows(filas)

    print(f"{a.salida} - {len(filas)} años ({min(anual)}-{max(anual)}), "
          f"pesos de diciembre {base}")

    # Self-check: la serie recuperada tiene que reproducir la inflación oficial.
    malas = []
    for anio, esperada in INFLACION_CONOCIDA.items():
        obtenida = next((f["inflacion_anual"] for f in filas if f["anio"] == anio), None)
        if obtenida == "" or obtenida is None:
            malas.append((anio, esperada, "sin dato"))
        elif abs(obtenida - esperada) > 0.5:
            malas.append((anio, esperada, obtenida))
    for anio, esperada, obtenida in malas:
        print(f"  DISCREPANCIA {anio}: oficial {esperada}% vs recuperada {obtenida}")
    assert not malas, "la serie recuperada no reproduce la inflación oficial"
    print(f"  self-check ok: inflación dic-dic reproducida en {len(INFLACION_CONOCIDA)} años")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
