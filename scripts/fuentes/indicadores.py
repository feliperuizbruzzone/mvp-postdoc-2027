"""
MAPA - Indicadores anuales por empresa. Es el CSV que consume el dash.

ENTRADAS
    datos/xbrl_facts.csv     hechos crudos de parse_xbrl.py
    datos/ipc.csv            deflactor de ipc.py

SALIDA
    datos/indicadores.csv    largo: empresa, grupo, anio, indicador, valor, fuente

CÓMO SE ELIGEN LOS HECHOS DEL XBRL

No por el nombre del contexto. Los archivos 2012+ usan ids con nombre
(`CierreTrimestreActual`), pero varios 2009-2011 usan ids opacos (`id87`), así que
el nombre no sirve como criterio general. Se usa el período, que siempre está:

    flujo anual   fecha_inicio = AAAA-01-01 y fecha_fin = AAAA-12-31
    stock a cierre fecha_fin = AAAA-12-31

y en ambos casos n_dim == 0, o sea la cifra consolidada. Sin ese filtro se suman
las aperturas por segmento junto al total y los montos se duplican.

Uso:  py scripts/fuentes/indicadores.py
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

# Las notas a los estados financieros son hechos XBRL con texto largo: hay campos
# de varios cientos de KB que superan el límite por defecto de csv.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# RUT (sin dígito verificador) -> slug. Verificados contra la ficha de la CMF
# (pestaña 1, Identificación). Un RUT que no esté acá se ignora al leer el XBRL,
# así que agregar una empresa nueva es agregar su línea también en GRUPOS y NOMBRES.
EMPRESAS = {
    "91705000": ("quinenco", "Luksic"),
    "93834000": ("cencosud", "Paulmann"),
}
GRUPOS = {
    "quinenco": "Luksic",
    "cencosud": "Paulmann",
}
NOMBRES = {
    "quinenco": "Quiñenco S.A.",
    "cencosud": "Cencosud S.A.",
}

# Conceptos XBRL y si son flujo (período) o stock (instante).
FLUJOS = ["Revenue", "CostOfSales", "GrossProfit", "ProfitLoss",
          "ProfitLossAttributableToOwnersOfParent"]
STOCKS = ["Assets", "Equity", "EquityAttributableToOwnersOfParent", "Liabilities"]


def div(a, b):
    """División que devuelve None ante nulos, cero o resultado no finito."""
    if a is None or b in (None, 0):
        return None
    r = a / b
    return r if math.isfinite(r) else None


def leer_xbrl(ruta: Path, tc: dict[int, float]) -> dict[tuple[str, int], dict[str, float]]:
    """
    (slug, anio) -> {concepto: valor}, solo cifras consolidadas anuales, en CLP.

    No todos los emisores presentan en pesos: algunos reportan en dólares los
    años de su serie. Los montos en otra moneda se convierten con el promedio
    anual del tipo de cambio. Si no hay tipo de cambio para ese año, el valor se
    conserva en su moneda y el año queda marcado en `_moneda`: los ratios siguen
    siendo válidos porque numerador y denominador la comparten, y es indicadores()
    quien decide no emitir los montos.
    """
    out: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)
    conflictos = 0
    sin_tc: set[tuple[str, int, str]] = set()
    with ruta.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["n_dim"] != "0":
                continue
            emp = EMPRESAS.get(r["empresa_id"])
            if not emp:
                continue
            concepto, fin, ini = r["concepto"], r["fecha_fin"], r["fecha_inicio"]
            if not fin.endswith("-12-31"):
                continue
            if concepto in FLUJOS:
                if not ini.endswith("-01-01") or ini[:4] != fin[:4]:
                    continue
            elif concepto in STOCKS:
                pass
            else:
                continue
            try:
                valor = float(r["valor"])
            except ValueError:
                continue

            anio = int(fin[:4])
            clave = (emp[0], anio)
            moneda = r.get("moneda") or "CLP"
            if moneda != "CLP":
                if anio in tc and moneda == "USD":
                    valor *= tc[anio]
                    moneda = "CLP"
                    out[clave]["_convertida"] = True
                else:
                    # Se conserva en su moneda: los ratios siguen siendo válidos
                    # porque numerador y denominador la comparten. Los montos se
                    # marcan y no se emiten.
                    sin_tc.add((emp[0], anio, moneda))
            out[clave]["_moneda"] = moneda
            previo = out[clave].get(concepto)
            if previo is not None and abs(previo - valor) > max(1.0, abs(previo) * 1e-6):
                # Dos presentaciones distintas del mismo año (la del año y la
                # comparativa del siguiente). Gana la más reciente, que incorpora
                # reexpresiones.
                conflictos += 1
            out[clave][concepto] = valor
    if conflictos:
        print(f"  {conflictos} valores reexpresados entre presentaciones (se usó el más reciente)")
    if sin_tc:
        faltan = sorted({(e, a, m) for e, a, m in sin_tc})
        anios = sorted({a for _, a, _ in faltan})
        print(f"  SIN TIPO DE CAMBIO: {len(faltan)} pares empresa-año descartados "
              f"({faltan[0][0]} {anios[0]}-{anios[-1]}, moneda {faltan[0][2]}). "
              f"Sus ratios sí quedan; los montos no.")
    return out


def leer_sdx(ruta: Path) -> dict[tuple[str, int], dict[str, float]]:
    """Mismo formato que leer_xbrl, traduciendo los nombres de columna del MCP."""
    mapa = {
        "revenue": "Revenue",
        "gross_profit": "GrossProfit",
        "profit_loss": "ProfitLoss",
        "profit_attributable": "ProfitLossAttributableToOwnersOfParent",
        "total_assets": "Assets",
        "total_equity": "Equity",
        "equity_attributable": "EquityAttributableToOwnersOfParent",
    }
    out: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)
    if not ruta.exists():
        print(f"  {ruta} no está: solo XBRL propio")
        return out
    with ruta.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            anio = int(r["period_end"][:4])
            for col, concepto in mapa.items():
                try:
                    out[(r["empresa"], anio)][concepto] = float(r[col])
                except (ValueError, KeyError):
                    pass
    return out


def leer_tc(ruta: Path) -> dict[int, float]:
    """anio -> promedio anual USD/CLP. Serie corta a proposito: solo los anios
    con fuente verificada."""
    if not ruta.exists():
        print(f'  aviso: no existe {ruta}, no habra conversion de moneda')
        return {}
    with ruta.open(encoding='utf-8') as fh:
        return {int(r['anio']): float(r['usdclp']) for r in csv.DictReader(fh)}


def leer_trabajadores(ruta: Path) -> dict[tuple[str, int], int]:
    """
    Dotación por empresa-año, de las memorias anuales.

    Es la única entrada que no viene de estados financieros, y la que habilita
    las dos métricas de productividad laboral. Opcional: si el archivo no está,
    esas métricas simplemente no se emiten.
    """
    if not ruta.exists():
        print(f"  {ruta} no está: sin métricas por trabajador")
        return {}
    with ruta.open(encoding="utf-8") as fh:
        return {(r["empresa"], int(r["anio"])): int(r["trabajadores"])
                for r in csv.DictReader(fh)}


def leer_ipc(ruta: Path) -> dict[int, float]:
    with ruta.open(encoding="utf-8") as fh:
        return {int(r["anio"]): float(r["deflactor"]) for r in csv.DictReader(fh)}


def comparar(xbrl, sdx, convertidas: set[str]) -> None:
    """
    Chequeo del empalme sobre los años que ambas fuentes cubren.

    Se separan las empresas que presentan en otra moneda. Para ellas la
    comparación arrastra una diferencia de convención, no un error: el MCP
    convierte al tipo de cambio del mes de cierre y acá se usa el promedio anual,
    lo que en años de dólar volátil da varios puntos. La tolerancia es 1% para
    las que reportan en pesos y 15% para las convertidas.

    """
    comunes = sorted(set(xbrl) & set(sdx))
    if not comunes:
        print("  sin años solapados: el empalme no se puede verificar")
        return

    peor = {False: 0.0, True: 0.0}
    n = {False: 0, True: 0}
    revisar = []
    for clave in comunes:
        conv = clave[0] in convertidas
        for concepto, v in xbrl[clave].items():
            if concepto.startswith("_"):      # metadatos, no cifras
                continue
            w = sdx[clave].get(concepto)
            if w is None or v == 0:
                continue
            d = abs(v - w) / abs(v)
            n[conv] += 1
            peor[conv] = max(peor[conv], d)
            if d > (0.15 if conv else 0.01):
                revisar.append((clave, concepto, v, w, d))

    print(f"  empalme: {len(comunes)} años solapados")
    print(f"    en pesos     : {n[False]:>3} cifras, desvío máximo {peor[False]:.2%} (tolerancia 1%)")
    if n[True]:
        print(f"    convertidas  : {n[True]:>3} cifras, desvío máximo {peor[True]:.2%} (tolerancia 15%)")
    for clave, concepto, v, w, d in revisar[:8]:
        print(f"    FUERA DE TOLERANCIA {clave} {concepto}: xbrl={v:,.0f} sdx={w:,.0f} ({d:.1%})")
    if not revisar:
        print("    sin saltos de nivel en el empalme")
    assert not revisar, f"{len(revisar)} cifras fuera de tolerancia entre XBRL y sdx"


def indicadores(d: dict[str, float], deflactor: float | None,
                dotacion: int | None = None) -> dict[str, float | None]:
    """
    Indicadores de un año.

    Los ratios se calculan siempre: numerador y denominador comparten moneda, así
    que el tipo de cambio se cancela. Los montos solo se emiten si la cifra quedó
    en pesos, porque mezclarlos entre empresas exige una moneda común.
    """
    en_pesos = d.get("_moneda", "CLP") == "CLP"
    rev = d.get("Revenue")
    gp = d.get("GrossProfit")
    if gp is None and rev is not None and d.get("CostOfSales") is not None:
        # CostOfSales se presenta con signo negativo en algunas taxonomías.
        gp = rev - abs(d["CostOfSales"])
    pl = d.get("ProfitLoss")
    pl_c = d.get("ProfitLossAttributableToOwnersOfParent")
    act = d.get("Assets")
    pat = d.get("Equity")
    pat_c = d.get("EquityAttributableToOwnersOfParent")

    return {
        "patrimonio": pat if en_pesos else None,
        "patrimonio_real": pat * deflactor if (en_pesos and pat is not None and deflactor) else None,
        "activos": act if en_pesos else None,
        "ingresos": rev if en_pesos else None,
        "utilidad": pl if en_pesos else None,
        "margen_bruto": div(gp, rev),
        "margen_neto": div(pl, rev),
        "roa": div(pl, act),
        # ROE con numerador y denominador ambos atribuibles a la controladora,
        # cayendo al total cuando la empresa no abre el interés minoritario.
        "roe": div(pl_c if pl_c is not None else pl, pat_c if pat_c is not None else pat),
        "rotacion_activos": div(rev, act),
        "excedente_capital": div(gp, pat),
        # Productividad laboral. En pesos constantes para que la serie sea
        # comparable en el tiempo, y solo cuando la cifra ya está en pesos.
        "trabajadores": dotacion,
        "ingresos_por_trabajador": (
            rev * deflactor / dotacion
            if (en_pesos and rev is not None and deflactor and dotacion) else None),
        "excedente_por_trabajador": (
            gp * deflactor / dotacion
            if (en_pesos and gp is not None and deflactor and dotacion) else None),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--xbrl", type=Path, default=Path("datos/xbrl_facts.csv"))
    p.add_argument("--sdx", type=Path, default=Path("datos/sdx_scorecard.csv"))
    p.add_argument("--ipc", type=Path, default=Path("datos/ipc.csv"))
    p.add_argument("--trabajadores", type=Path, default=Path("datos/trabajadores.csv"))
    p.add_argument("--usdclp", type=Path, default=Path("datos/usdclp.csv"))
    p.add_argument("-o", "--salida", type=Path, default=Path("datos/indicadores.csv"))
    # El piloto esta circunscrito al corte de la tesis: el XBRL llega mas lejos,
    # pero la serie que se publica termina en 2019.
    p.add_argument("--desde", type=int, default=2009)
    p.add_argument("--hasta", type=int, default=2019)
    a = p.parse_args()

    print("Leyendo XBRL propio...")
    tc = leer_tc(a.usdclp)
    xbrl = leer_xbrl(a.xbrl, tc)
    print(f"  {len(xbrl)} pares empresa-año")
    print("Leyendo scorecard sdx...")
    sdx = leer_sdx(a.sdx)
    print(f"  {len(sdx)} pares empresa-año")
    ipc = leer_ipc(a.ipc)
    print("Leyendo dotación de trabajadores...")
    dotaciones = leer_trabajadores(a.trabajadores)
    print(f"  {len(dotaciones)} pares empresa-año")

    print("Verificando el empalme...")
    # Empresas cuyas cifras hubo que convertir desde otra moneda.
    convertidas = {e for (e, _), d in xbrl.items() if d.get("_convertida")}
    comparar(xbrl, sdx, convertidas)

    # El XBRL propio manda; el MCP rellena lo que falta.
    combinado: dict[tuple[str, int], tuple[dict, str]] = {}
    for clave, d in sdx.items():
        combinado[clave] = (dict(d), "sdx")
    for clave, d in xbrl.items():
        if clave in combinado:
            base = combinado[clave][0]
            base.update(d)                       # el propio pisa al del MCP
            combinado[clave] = (base, "xbrl+sdx")
        else:
            combinado[clave] = (dict(d), "xbrl")

    filas = []
    for (empresa, anio), (d, fuente) in sorted(combinado.items()):
        if not (a.desde <= anio <= a.hasta):
            continue
        dot = dotaciones.get((empresa, anio))
        for indicador, valor in indicadores(d, ipc.get(anio), dot).items():
            if valor is None:
                continue
            filas.append({
                "empresa": empresa,
                "nombre": NOMBRES.get(empresa, empresa),
                "grupo": GRUPOS.get(empresa, ""),
                "anio": anio,
                "indicador": indicador,
                "valor": round(valor, 6),
                "fuente": fuente,
            })

    a.salida.parent.mkdir(parents=True, exist_ok=True)
    with a.salida.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["empresa", "nombre", "grupo", "anio",
                                           "indicador", "valor", "fuente"])
        w.writeheader()
        w.writerows(filas)

    anios = sorted({f["anio"] for f in filas})
    print(f"\n{a.salida} - {len(filas)} filas, {anios[0]}-{anios[-1]}")
    for empresa in sorted({f["empresa"] for f in filas}):
        aa = sorted({f["anio"] for f in filas if f["empresa"] == empresa})
        print(f"  {empresa:<13} {aa[0]}-{aa[-1]}  ({len(aa)} años)")

    # Chequeos: los ratios tienen que caer en rangos plausibles.
    malos = [
        f for f in filas
        if f["indicador"] in ("margen_bruto", "margen_neto", "roa", "roe")
        and not -3 <= f["valor"] <= 3
    ]
    for f in malos[:5]:
        print(f"  FUERA DE RANGO: {f['empresa']} {f['anio']} {f['indicador']} = {f['valor']}")
    assert not malos, f"{len(malos)} ratios fuera de rango plausible"
    assert all(f["valor"] > 0 for f in filas if f["indicador"] == "patrimonio_real"), \
        "hay patrimonio real no positivo"
    print("  self-check ok: ratios en rango y patrimonio real positivo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
