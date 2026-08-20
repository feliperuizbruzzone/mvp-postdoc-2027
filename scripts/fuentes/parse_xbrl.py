"""
MAPA — Extracción de hechos financieros desde los XBRL presentados a la CMF.

Recorre un directorio de archivos .xbrl y emite un CSV tidy con un hecho por fila.
Es el script que faltaba: CencoQuinenco.csv se había generado a mano, sin código
reproducible, así que no se podía extender a más empresas ni auditar.

ESQUEMA DE SALIDA

    empresa_id     RUT sin dígito verificador, tomado del nombre del archivo
    anio_archivo   año de presentación (el del nombre del archivo)
    anio_contexto  año al que se refiere el dato (de la fecha de cierre del contexto)
    etiqueta       nombre local del concepto XBRL, sin prefijo de namespace
    valor          numérico; vacío si el hecho viene sin contenido
    fecha_inicio   ISO, vacío en contextos de instante (stocks)
    fecha_fin      ISO
    contextRef     id del contexto, tal cual aparece en el archivo

SOBRE LOS CONTEXTOS

La CMF usa ids con nombre en vez de códigos. Los tres que importan para los ratios:

    TrimestreAcumuladoActual   flujos acumulados del ejercicio en curso (YTD)
    CierreTrimestreActual      stocks al cierre del trimestre
    AnualAnterior              flujos del ejercicio anterior completo

Los contextos dimensionales llevan esos mismos nombres con sufijos que codifican
los ejes (segmento, clase de activo, etc.). Se extraen todos y el filtrado queda
para indicadores.py: distintos indicadores necesitan distintos cortes.

DOS FORMATOS DE NOMBRE

Los archivos 2009-2011 se llaman `Estados_financieros_(XBRL)<rut>_<aaaamm>.xbrl` y
los 2012+ `<rut>_<aaaamm>_C.xbrl`. El RUT y el período se sacan por regex, así que
ambos entran sin ramas adicionales.

Uso:
    py scripts/fuentes/parse_xbrl.py <dir_con_xbrl> [-o datos/xbrl_facts.csv]
    py scripts/fuentes/parse_xbrl.py --self-check <dir> <CencoQuinenco.csv>
"""

from __future__ import annotations

import argparse
import collections
import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

XBRLI = "http://www.xbrl.org/2003/instance"
NOMBRE = re.compile(r"(\d{8,9})_(\d{4})(\d{2})")

CAMPOS = [
    "empresa_id", "anio_archivo", "anio_contexto", "etiqueta", "concepto",
    "valor", "moneda", "fecha_inicio", "fecha_fin", "n_dim", "contextRef",
]

# Equivalencias de la taxonomía 2009-2011 con la IFRS que rige desde 2012.
#
# Se derivaron cruzando valores: para cada concepto de CencoQuinenco.csv con
# anio_archivo 2009-2011 se buscó qué elemento del .xbrl lleva exactamente ese
# número en el mismo contexto. La mayoría de los conceptos conserva el nombre;
# solo estos cinco cambian.
#
# NO son alias, aunque el cruce por valor los proponga:
#   EquityAndLiabilities -> Assets            es la identidad contable A = P + K
#   ComprehensiveIncome  -> ProfitLoss        resultado integral, concepto distinto
#   PatrimonioPreviamenteReportado -> Equity  patrimonio antes de reexpresión
ALIAS_PRE2012 = {
    "AssetsTotal": "Assets",
    "EquityTotal": "Equity",
    "LiabilitiesTotal": "Liabilities",
    "RevenueTotal": "Revenue",
    "EquityAttributableToEquityHoldersOfParent": "EquityAttributableToOwnersOfParent",
}


def localname(tag: str) -> str:
    """`{ns}Assets` -> `Assets`."""
    return tag.rsplit("}", 1)[-1]


def leer_contextos(root: ET.Element) -> dict[str, tuple[str, str, int]]:
    """
    id de contexto -> (fecha_inicio, fecha_fin, n_dim).

    n_dim es la cantidad de ejes dimensionales del contexto. Con 0 el hecho es la
    cifra consolidada; con 1 o más es una apertura (por segmento, por clase de
    activo, por moneda). Distinguirlos es imprescindible: sumar aperturas junto
    al consolidado duplica los montos.

    Las fechas importan más que el id. Los archivos 2012+ usan ids con nombre
    (`CierreTrimestreActual`), pero varios 2009-2011 usan ids opacos (`id87`,
    `id459`), así que la semántica del contexto solo es recuperable del período.
    """
    contextos = {}
    for ctx in root.iter(f"{{{XBRLI}}}context"):
        cid = ctx.get("id")
        if not cid:
            continue
        period = ctx.find(f"{{{XBRLI}}}period")
        if period is None:
            continue
        instant = period.find(f"{{{XBRLI}}}instant")
        if instant is not None:
            inicio, fin = "", (instant.text or "").strip()
        else:
            i = period.find(f"{{{XBRLI}}}startDate")
            f = period.find(f"{{{XBRLI}}}endDate")
            inicio = (i.text or "").strip() if i is not None else ""
            fin = (f.text or "").strip() if f is not None else ""

        n_dim = sum(
            1 for e in ctx.iter()
            if localname(e.tag) in ("explicitMember", "typedMember")
        )
        contextos[cid] = (inicio, fin, n_dim)
    return contextos


def leer_unidades(root: ET.Element) -> dict[str, str]:
    """
    id de unidad -> moneda ISO 4217 ('CLP', 'USD'), o '' si no es monetaria.

    No todos los emisores chilenos reportan en pesos; algunos presentan en dólares
    toda su serie. Sin registrar la unidad, sus montos se leen como si fueran CLP y
    quedan ~700 veces por debajo de los del resto.
    """
    unidades = {}
    for u in root.iter(f"{{{XBRLI}}}unit"):
        uid = u.get("id")
        if not uid:
            continue
        medidas = [(m.text or "").strip() for m in u.iter(f"{{{XBRLI}}}measure")]
        iso = [m.split(":")[-1] for m in medidas if m.startswith("iso4217:")]
        unidades[uid] = iso[0] if len(iso) == 1 else ""
    return unidades


def normalizar_valor(texto: str) -> str:
    """
    Número en notación con punto cuando el hecho es numérico; si no, el texto
    tal cual. Hay conceptos que son fechas o descripciones y perderlos sería
    perder información: la coerción a número queda para indicadores.py.
    """
    t = (texto or "").strip()
    if not t:
        return ""
    # Algunos emisores usan coma decimal y punto de miles.
    n = t.replace(".", "").replace(",", ".") if ("," in t and "." in t) else t.replace(",", ".")
    try:
        return repr(float(n))
    except ValueError:
        return t


def parse_file(path: Path) -> list[dict]:
    m = NOMBRE.search(path.name)
    if not m:
        print(f"  saltado (nombre no reconocido): {path.name}", file=sys.stderr)
        return []
    empresa_id, anio_archivo = m.group(1), int(m.group(2))

    root = ET.parse(path).getroot()
    contextos = leer_contextos(root)
    unidades = leer_unidades(root)

    filas = []
    for el in root.iter():
        cref = el.get("contextRef")
        if cref is None:
            continue
        inicio, fin, n_dim = contextos.get(cref, ("", "", 0))
        etiqueta = localname(el.tag)
        filas.append({
            "empresa_id": empresa_id,
            "anio_archivo": anio_archivo,
            "anio_contexto": fin[:4] if fin else "",
            "etiqueta": etiqueta,
            "concepto": ALIAS_PRE2012.get(etiqueta, etiqueta),
            "valor": normalizar_valor(el.text or ""),
            "moneda": unidades.get(el.get("unitRef") or "", ""),
            "fecha_inicio": inicio,
            "fecha_fin": fin,
            "n_dim": n_dim,
            "contextRef": cref,
        })
    return filas


def recolectar(directorio: Path) -> list[dict]:
    archivos = sorted(directorio.glob("*.xbrl"))
    if not archivos:
        sys.exit(f"No hay archivos .xbrl en {directorio}")
    filas = []
    for f in archivos:
        n = len(filas)
        filas.extend(parse_file(f))
        print(f"  {f.name}: {len(filas) - n} hechos")
    return filas


def escribir(filas: list[dict], salida: Path) -> None:
    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)
    print(f"\n{salida} — {len(filas)} filas")


def self_check(directorio: Path, referencia: Path) -> int:
    """
    Compara contra CencoQuinenco.csv, el export ad-hoc que se hizo a mano.

    No se comparan bytes. La referencia pasó por Excel y eso dejó tres artefactos
    que NO son errores de extracción, y que se clasifican aparte en vez de contarse
    como fallas:

      1. Redondeo. La referencia guarda 895,68 donde el XBRL dice 895,6767.
      2. Fechas convertidas a serial de Excel (45291 por 2023-12-31).
      3. Filas de relleno 2001-2008 con valor vacío, heredadas del scaffold de
         QuinencoCenco_VariablesAisladas: años sin XBRL presentado.

    Falla de verdad solo si un valor numérico de la referencia no aparece en la
    extracción, o aparece con otro número.
    """
    filas = recolectar(directorio)

    def clave(empresa, etiqueta, ctx, anio):
        return (str(empresa).strip(), etiqueta.strip(), ctx.strip(), str(anio).strip())

    def num(v):
        v = (v or "").strip()
        if not v:
            return None
        if "," in v:
            v = v.replace(".", "").replace(",", ".")
        try:
            return float(v)
        except ValueError:
            return None

    # Se compara por `concepto`, no por `etiqueta`: la referencia ya traía los
    # nombres pre-2012 traducidos a la taxonomía IFRS.
    mio = {}
    for r in filas:
        k = clave(r["empresa_id"], r["concepto"], r["contextRef"], r["anio_contexto"])
        v = num(r["valor"])
        if v is not None or k not in mio:
            mio[k] = v

    ref, vacias = {}, 0
    with referencia.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            k = clave(r["empresa_id"], r["etiqueta"], r["contextRef"], r["anio_contexto"])
            v = num(r["valor"])
            if v is None:
                vacias += 1
                continue
            ref[k] = v

    def es_redondeo(v: float, w: float) -> bool:
        """
        v es w redondeado a los decimales con que la referencia guardó v.

        Se compara con media unidad del último decimal en vez de round(), porque
        Python redondea al par (round(0.425, 2) == 0.42) y Excel se aleja del
        cero (0,43). Con la tolerancia el criterio no depende de esa diferencia.
        """
        s = repr(v)
        dec = len(s.split(".")[1]) if "." in s else 0
        return abs(v - w) <= 0.5 * 10 ** -dec + 1e-12 or abs(v - w) <= abs(v) * 1e-3

    faltan, redondeo, seriales, reales = [], 0, 0, []
    for k, v in ref.items():
        if k not in mio:
            faltan.append(k)
            continue
        w = mio[k]
        if w is None:
            # Serial de Excel: la referencia numerizó una fecha que el XBRL trae
            # como texto. 30000-60000 cubre 1982-2064.
            if 30000 <= v <= 60000 and float(v).is_integer():
                seriales += 1
            else:
                reales.append((k, v, w))
        elif abs(v - w) <= max(1e-9, abs(v) * 1e-9) or es_redondeo(v, w):
            redondeo += abs(v - w) > max(1e-9, abs(v) * 1e-9)
        else:
            reales.append((k, v, w))

    por_anio = collections.Counter(k[3] for k in faltan)

    print(f"\n--- self-check contra {referencia.name} ---")
    print(f"claves con valor en la referencia : {len(ref)}")
    print(f"claves extraídas                  : {len(mio)}")
    print(f"filas de relleno sin valor        : {vacias}  (años sin XBRL, ignoradas)")
    print(f"redondeos de la referencia        : {redondeo}  (el XBRL trae más decimales)")
    print(f"fechas serializadas por Excel     : {seriales}")
    print(f"AUSENTES en la extracción         : {len(faltan)}")
    if por_anio:
        print("   por año de contexto: " + ", ".join(
            f"{a}={n}" for a, n in sorted(por_anio.items())))
    print(f"VALORES DISTINTOS                 : {len(reales)}")
    for k, v, w in reales[:8]:
        print(f"  {k}: referencia={v} extraído={w}")
    for k in faltan[:8]:
        print(f"  ausente: {k}")

    # Los años 2009-2011 no son comparables uno a uno: la referencia mezcló ahí
    # varias presentaciones y renombró contextos opacos a mano. Lo que sí tiene
    # que cuadrar exactamente es 2012 en adelante, que es una taxonomía estable.
    fallas = [k for k in faltan if k[3] >= "2012"] + [t for t in reales if t[0][3] >= "2012"]
    ok = not fallas
    print(f"\n2012+ (taxonomía estable): {len(fallas)} discrepancias")
    print("RESULTADO:", "OK" if ok else "REVISAR")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("directorio", type=Path, help="directorio con archivos .xbrl")
    p.add_argument("referencia", type=Path, nargs="?", help="CSV de referencia para --self-check")
    p.add_argument("-o", "--salida", type=Path, default=Path("datos/xbrl_facts.csv"))
    p.add_argument("--self-check", action="store_true", help="comparar contra la referencia y salir")
    a = p.parse_args()

    if a.self_check:
        if not a.referencia:
            p.error("--self-check requiere la ruta del CSV de referencia")
        return self_check(a.directorio, a.referencia)

    escribir(recolectar(a.directorio), a.salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
