"""
MAPA - Descarga de documentos de la CMF por RUT.

REEMPLAZA A CMFScraper.py, que usaba Selenium con XPaths fijos y guardaba
`page_source` dentro de un archivo .zip (o sea, HTML en vez del binario). Acá no
hace falta navegador: la ficha de cada entidad es una URL paramétrica y el
formulario de estados financieros es un POST normal.

    https://www.cmfchile.cl/institucional/mercados/entidad.php
        ?mercado=V&rut=<RUT>&tipoentidad=RVEMI&vig=VI&control=svs&pestania=<N>

PESTAÑAS ÚTILES

     3  Información Financiera   EEFF en XBRL y PDF, Análisis Razonado
     5  12 Mayores Accionistas   estructura de propiedad
    33  EEFF Filiales            perímetro del grupo
    46  Registro de Directores
    47  Registro de Gerentes y ejecutivos principales
    49  Memoria Anual

La pestaña 3 responde a un POST con:

    forma=P  mm=03|06|09|12  aa=<año>  tipo=C|I  tipo_norma=IFRS|NCH

(tipo C = consolidado, I = individual; NCH es la norma anterior a IFRS). La
respuesta trae anclas a `safec_ifrs_verarchivo.php?auth=...&send=...` con tokens
firmados por request: hay que leerlos de la respuesta, no se pueden construir.
Por eso la descarga es siempre en dos pasos, consulta y luego archivo.

IDEMPOTENTE: no vuelve a bajar lo que ya está en disco. Entre requests espera
`--pausa` segundos (1 por defecto) para no golpear el servicio.

Uso:
    py scripts/fuentes/cmf_descarga.py eeff    93834000 --desde 2009 --hasta 2025
    py scripts/fuentes/cmf_descarga.py memoria 93834000
    py scripts/fuentes/cmf_descarga.py listar  93834000
    py scripts/fuentes/cmf_descarga.py registro          # nomina de emisores
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import time
from pathlib import Path

import requests

BASE = "https://www.cmfchile.cl/institucional/mercados/entidad.php"
HOST = "https://www.cmfchile.cl"
RAIZ = HOST + "/institucional/"
UA = "Mozilla/5.0 (investigacion academica; contacto via repositorio del proyecto)"

PESTANAS = {
    "identificacion": 1,
    "eeff": 3,
    "accionistas": 5,
    "filiales": 33,
    "directores": 46,
    "gerentes": 47,
    "memoria": 49,
}

# Etiqueta del ancla -> sufijo del archivo guardado.
DOCS_EEFF = {
    "Estados financieros (XBRL)": "xbrl.zip",
    "Estados financieros (PDF)": "eeff.pdf",
    "Análisis Razonado": "analisis_razonado.pdf",
}

ANCLA = re.compile(r'<a[^>]*href="([^"]*verarchivo[^"]*)"[^>]*>(.*?)</a>', re.S)
CUALQUIER_ANCLA = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)


def sesion() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    return s


def url_ficha(rut: str, pestania: int) -> str:
    return (f"{BASE}?mercado=V&rut={rut}&grupo=&tipoentidad=RVEMI"
            f"&row=&vig=VI&control=svs&pestania={pestania}")


def texto(fragmento: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento))).strip()


def absoluta(href: str) -> str:
    """Los enlaces vienen relativos al directorio (`../inc/...`) o a la raíz
    (`/sitio/aplic/...`) según la pestaña."""
    href = html.unescape(href)
    if href.startswith("../"):
        return href.replace("../", RAIZ, 1)
    if href.startswith("/"):
        return HOST + href
    return href


def anclas(pagina: str, patron=ANCLA) -> list[tuple[str, str]]:
    """[(url_absoluta, etiqueta)] de la página."""
    return [(absoluta(m.group(1)), texto(m.group(2))) for m in patron.finditer(pagina)]


# Magic bytes de lo que sí es un archivo. Se comprueba el contenido en vez del
# content-type porque la CMF responde 200 con HTML tanto para los errores como
# para las páginas contenedoras.
MAGIC = (b"%PDF", b"PK\x03\x04", b"\xd0\xcf\x11\xe0")

# El gestor documental sirve primero un contenedor: `secuencia=-1` devuelve una
# página con un enlace verDocto() por cada documento (`secuencia=0`, `1`, ...).
VERDOCTO = re.compile(r"verDocto\('([^']+)'\)")


def bajar(s: requests.Session, url: str, destino: Path, pausa: float,
          profundidad: int = 0) -> int:
    """
    Descarga a disco y devuelve cuántos archivos nuevos quedaron.

    Si la respuesta es la página contenedora del gestor documental en vez del
    archivo, sigue los enlaces verDocto() que trae (un nivel).
    """
    if destino.exists() and destino.stat().st_size > 0:
        print(f"      ya está: {destino.name}")
        return 0

    r = s.get(url, timeout=120)
    r.raise_for_status()
    time.sleep(pausa)
    cuerpo = r.content

    if cuerpo.lstrip()[:8].startswith(MAGIC):
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(cuerpo)
        print(f"      {destino.name}  ({len(cuerpo) / 1024:.0f} KB)")
        return 1

    if profundidad == 0:
        internos = sorted(set(VERDOCTO.findall(r.text)))
        if internos:
            print(f"      contenedor con {len(internos)} documento(s)")
            n = 0
            for i, u in enumerate(internos):
                sufijo = "" if len(internos) == 1 else f"_{i:02d}"
                hijo = destino.with_name(f"{destino.stem}{sufijo}{destino.suffix}")
                n += bajar(s, html.unescape(u), hijo, pausa, profundidad + 1)
            return n

    print(f"      sin archivo (la respuesta no es un documento): {destino.name}")
    return 0


# La consulta sin RUT devuelve la nomina completa de emisores inscritos, que es
# de donde salen los RUT sin adivinarlos.
URL_NOMINA = (f"{HOST}/institucional/mercados/consulta.php"
              "?mercado=V&Estado=TO&entidad=RVEMI&control=svs&pestania=1")
ES_RUT = re.compile(r"^[\d.]+-?[\dkK]?$")


def cmd_registro(a) -> int:
    """Nomina de emisores de valores: RUT y razon social."""
    import csv

    r = sesion().get(URL_NOMINA, timeout=120)
    r.raise_for_status()
    filas = sorted({
        (rut, texto(nombre))
        for rut, nombre in re.findall(r'rut=(\d{7,9})[^>]*>(.*?)</a>', r.text, re.S)
        # La ficha repite el RUT como texto del ancla en algunas filas.
        if texto(nombre) and not ES_RUT.match(texto(nombre))
    })
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    with a.salida.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["rut", "razon_social"])
        w.writerows(filas)
    print(f"{len(filas)} entidades -> {a.salida}")
    return 0


def cmd_listar(a) -> int:
    s = sesion()
    print(f"RUT {a.rut} - pestañas con contenido:")
    for nombre, n in PESTANAS.items():
        r = s.get(url_ficha(a.rut, n), timeout=60)
        time.sleep(a.pausa)
        enlaces = anclas(r.text, CUALQUIER_ANCLA)
        docs = [e for e in enlaces if re.search(r"\.pdf|verarchivo|descarga", e[0], re.I)]
        print(f"  {n:>3} {nombre:<15} {len(docs)} documento(s)")
        for url, etiqueta in docs[:4]:
            print(f"        {etiqueta[:60]}")
    return 0


def cmd_eeff(a) -> int:
    s = sesion()
    destino = a.salida / a.rut
    url = url_ficha(a.rut, PESTANAS["eeff"])
    total = 0
    for anio in range(a.desde, a.hasta + 1):
        for mes in a.meses:
            # IFRS rige desde 2009; antes la norma es NCH y la ficha no publica XBRL.
            norma = "IFRS" if anio >= 2009 else "NCH"
            r = s.post(url, data={
                "forma": "P", "mm": f"{mes:02d}", "aa": str(anio),
                "tipo": a.tipo, "tipo_norma": norma,
            }, timeout=120)
            r.raise_for_status()
            time.sleep(a.pausa)

            encontrados = {e: u for u, e in anclas(r.text)}
            if not encontrados:
                print(f"   {anio}-{mes:02d}: sin documentos")
                continue
            print(f"   {anio}-{mes:02d}: {len(encontrados)} documento(s)")
            for etiqueta, sufijo in DOCS_EEFF.items():
                if a.docs and not any(d in sufijo for d in a.docs):
                    continue
                if etiqueta in encontrados:
                    nombre = f"{a.rut}_{anio}{mes:02d}_{a.tipo}_{sufijo}"
                    total += bajar(s, encontrados[etiqueta], destino / nombre, a.pausa)
    print(f"\n{total} archivos nuevos en {destino}")
    return 0


# La CMF sirve los archivos por dos vías distintas según la pestaña:
#   safec_ifrs_verarchivo.php   estados financieros (pestaña 3)
#   serdoc/ver_sgd.php          gestor documental: memorias, actas, prospectos
# Ambas llevan tokens firmados por request, así que solo sirven leídas de la
# respuesta; no se pueden construir.
DESCARGA = re.compile(r"\.pdf$|verarchivo|ver_sgd|descarga", re.I)
OCULTO = re.compile(r'<input[^>]*type="hidden"[^>]*name="(\w+)"[^>]*value="([^"]*)"')


def descargables(pagina: str) -> list[tuple[str, str]]:
    return [e for e in anclas(pagina, CUALQUIER_ANCLA) if DESCARGA.search(e[0])]


# Pestañas que traen la información en una tabla dentro de la página en vez de
# como archivo adjunto: se guarda el HTML y la extrae un parser. El valor es la
# marca que distingue una respuesta con datos de una vacía, porque la CMF
# responde 200 con la cabecera del período aunque no haya nada informado.
TABLA_HTML = {
    "accionistas": "%</td>",
    "filiales": "Descargar Archivo",
    "directores": "Fecha Nombramiento",
    "gerentes": "Fecha Nombramiento",
}


def cmd_tabla(a, s, url, destino) -> int:
    """
    Guarda el HTML de una pestaña con tabla, consultando el histórico si lo hay.

    Tres formas de histórico según la pestaña:
      accionistas  formulario mm + aa: un archivo por trimestre.
      filiales     igual, pero `aa` es un <select>.
      directores   rango de fechas txt_inicio/txt_termino: toda la serie de
                   nombramientos y ceses en una sola consulta.
    """
    r = s.get(url, timeout=120)
    r.raise_for_status()
    time.sleep(a.pausa)
    destino.mkdir(parents=True, exist_ok=True)
    marca = TABLA_HTML[a.seccion]
    ocultos = dict(OCULTO.findall(r.text))

    if 'name="txt_inicio"' in r.text:
        arch = destino / f"{a.rut}_{a.seccion}_{a.desde}_{a.hasta}.html"
        if arch.exists() and arch.stat().st_size > 0:
            print(f"      ya está: {arch.name}")
            return 0
        rr = s.post(url, data={"txt_inicio": f"01/01/{a.desde}",
                               "txt_termino": f"31/12/{a.hasta}"}, timeout=120)
        rr.raise_for_status()
        time.sleep(a.pausa)
        arch.write_text(rr.text, encoding="utf-8")
        print(f"      {arch.name}")
        return 1

    if not re.search(r'<(input|select)[^>]*name="aa"', r.text):
        (destino / f"{a.rut}_{a.seccion}.html").write_text(r.text, encoding="utf-8")
        print("   la pestaña no ofrece histórico; guardado el estado vigente")
        return 0

    total = 0
    for anio in range(a.desde, a.hasta + 1):
        for mes in a.meses:
            arch = destino / f"{a.rut}_{a.seccion}_{anio}{mes:02d}.html"
            if arch.exists() and arch.stat().st_size > 0:
                continue
            rr = s.post(url, data={**ocultos, "mm": f"{mes:02d}", "aa": str(anio)},
                        timeout=120)
            rr.raise_for_status()
            time.sleep(a.pausa)
            if marca not in rr.text:
                print(f"   {anio}-{mes:02d}: sin período informado")
                continue
            arch.write_text(rr.text, encoding="utf-8")
            total += 1
            print(f"      {arch.name}")
    return total


def cmd_documentos(a) -> int:
    """
    Memoria anual, accionistas, filiales, directores.

    Las de TABLA_HTML se guardan como página; el resto son adjuntos. De esas,
    algunas listan todo de una y otras (la memoria anual entre ellas) traen un
    formulario con un único selector de año, así que hay que consultar año por año.
    """
    s = sesion()
    pestania = PESTANAS[a.seccion]
    destino = a.salida / a.rut / a.seccion
    url = url_ficha(a.rut, pestania)

    if a.seccion in TABLA_HTML:
        total = cmd_tabla(a, s, url, destino)
        print(f"\n{total} páginas nuevas en {destino}")
        return 0

    r = s.get(url, timeout=120)
    r.raise_for_status()
    time.sleep(a.pausa)
    total, vacias = 0, 0

    if re.search(r'<select[^>]*name="aa"', r.text):
        print(f"   la pestaña {pestania} pide año: consultando {a.desde}-{a.hasta}")
        for anio in range(a.desde, a.hasta + 1):
            rr = s.post(url, data={"aa": str(anio)}, timeout=120)
            rr.raise_for_status()
            time.sleep(a.pausa)
            enlaces = descargables(rr.text)
            if not enlaces:
                vacias += 1
                continue
            print(f"   {anio}: {len(enlaces)} documento(s)")
            for i, (u, etiqueta) in enumerate(enlaces, 1):
                sufijo = "" if len(enlaces) == 1 else f"_{i:02d}"
                total += bajar(s, u, destino / f"{a.rut}_{a.seccion}_{anio}{sufijo}.pdf", a.pausa)
        if vacias:
            print(f"   {vacias} años sin documentos")
    else:
        for i, (u, etiqueta) in enumerate(descargables(r.text), 1):
            anio = re.search(r"(19|20)\d{2}", etiqueta)
            marca = anio.group(0) if anio else f"{i:02d}"
            total += bajar(s, u, destino / f"{a.rut}_{a.seccion}_{marca}.pdf", a.pausa)

    print(f"\n{total} archivos nuevos en {destino}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("comando", choices=["eeff", "listar", "registro"]
                   + [k for k in PESTANAS if k != "eeff"])
    p.add_argument("rut", nargs="?", default="",
                   help="RUT sin dígito verificador ni puntos, p.ej. 93834000. "
                        "No lo usa `registro`.")
    p.add_argument("--desde", type=int, default=2009)
    p.add_argument("--hasta", type=int, default=time.localtime().tm_year)
    p.add_argument("--meses", type=int, nargs="+", default=[12],
                   help="meses de cierre a consultar (default: solo diciembre)")
    p.add_argument("--tipo", choices=["C", "I"], default="C",
                   help="C consolidado, I individual")
    p.add_argument("--salida", type=Path, default=Path("datos/cmf"))
    p.add_argument("--pausa", type=float, default=1.0)
    p.add_argument("--docs", nargs="*", default=None,
                   help="filtra qué documentos de EEFF bajar: xbrl, eeff, analisis. "
                        "Sin el filtro baja los tres, y los PDF pesan ~8 MB por año.")
    a = p.parse_args()

    if a.comando == "registro":
        # Escribe a datos/, no a datos/cmf/: es una tabla derivada, no un crudo.
        if a.salida == Path("datos/cmf"):
            a.salida = Path("datos/registro_valores.csv")
        return cmd_registro(a)

    if not a.rut:
        p.error(f"el comando {a.comando} necesita un RUT")

    print(f"CMF - RUT {a.rut}, comando {a.comando}")
    if a.comando == "listar":
        return cmd_listar(a)
    if a.comando == "eeff":
        return cmd_eeff(a)
    a.seccion = a.comando
    return cmd_documentos(a)


if __name__ == "__main__":
    raise SystemExit(main())
