"""
Scraper de comunicados de prensa del EDPS (Supervisor Europeo de
Protección de Datos).

    https://www.edps.europa.eu/press-publications/press-news/press-releases_en

El EDPS no publica RSS: la sonda de descubrimiento lo confirmó en dos
corridas, probando autodiscovery, rutas convencionales y los patrones de
europa.eu. Por eso va por scraping.

Estructura real del listado, verificada en el sitio el 18-sep-2026. Es
Drupal, y cada comunicado es una fila así:

    <div class="views-row">
      <article class="node node--type-edpsweb-press-release ...">
        <div class="edpsweb-publication-date">
          <div>14</div><div>Aug</div><div>2026</div>
        </div>
        <div class="edpsweb-publication-content">
          <header>
            <div class="edpsweb-publication-type">Press Release</div>
            <h3 class="node__title"><a href="/press-publications/...">…</a></h3>
          </header>
          <div class="node__content">…resumen…</div>

Dos decisiones de diseño, aprendidas de los scrapers del monitor
financiero:

1. No se ancla a una clase única. Las filas se buscan por el <article>
   cuya clase mencione press-release, y si el sitio cambiara ese nombre
   se cae a div.views-row, y de ahí a cualquier bloque que contenga un
   enlace a /press-releases/. Un rediseño de Drupal renombra clases con
   frecuencia; lo que no cambia es que el comunicado vive detrás de un
   enlace a su propia URL.

2. La fecha se lee del bloque de tres divs, y si eso falla se busca el
   patrón "14 Aug 2026" en el texto de la fila. Nunca se inventa: si no
   hay fecha reconocible, published queda en None y el pipeline decide
   (los items sin fecha se conservan, por diseño del ingest).
"""

import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,es;q=0.9",
}

TIMEOUT = 30

MESES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# "14 Aug 2026" o "14 August 2026", con lo que haya en medio (saltos de
# línea incluidos, que es como viene el bloque de tres divs).
FECHA_TEXTO = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b"
)


def _a_fecha(dia: str, mes: str, anio: str) -> str | None:
    """
    Arma 'YYYY-MM-DD' desde sus tres partes. Devuelve string, nunca
    datetime: el ingest hace strptime sobre este valor.
    """
    m = MESES.get(mes.strip().lower()[:3])
    if not m:
        return None
    try:
        d, y = int(dia), int(anio)
        # Construir el datetime solo para validar (30 de febrero, etc.)
        datetime(y, m, d)
    except (ValueError, TypeError):
        return None
    return "%04d-%02d-%02d" % (y, m, d)


def _fecha_de_la_fila(fila) -> str | None:
    """Fecha del comunicado. Primero el bloque propio, luego el texto."""
    bloque = fila.find(
        lambda t: t.name == "div"
        and t.get("class")
        and any("publication-date" in c for c in t.get("class"))
    )
    if bloque:
        partes = [d.get_text(strip=True) for d in bloque.find_all("div")]
        partes = [p for p in partes if p]
        if len(partes) >= 3:
            f = _a_fecha(partes[0], partes[1], partes[2])
            if f:
                return f

    m = FECHA_TEXTO.search(fila.get_text(" ", strip=True))
    if m:
        return _a_fecha(m.group(1), m.group(2), m.group(3))
    return None


def _filas(soup):
    """
    Las filas del listado, con tres niveles de tolerancia a rediseños.
    """
    filas = soup.find_all(
        lambda t: t.name == "article"
        and t.get("class")
        and any("press-release" in c for c in t.get("class"))
    )
    if filas:
        return filas, "article press-release"

    filas = soup.select("div.views-row")
    if filas:
        return filas, "div.views-row"

    # Último recurso: cualquier contenedor con un enlace a un comunicado.
    vistos, filas = set(), []
    for a in soup.select('a[href*="/press-releases/"]'):
        cont = a.find_parent(["article", "li", "div"])
        if cont is not None and id(cont) not in vistos:
            vistos.add(id(cont))
            filas.append(cont)
    return filas, "contenedores con enlace a /press-releases/"


def _titulo_y_enlace(fila, base: str):
    """Enlace al comunicado. El título es el texto de ese enlace."""
    a = fila.select_one("h3 a[href], h2 a[href], h4 a[href]")
    if a is None:
        for cand in fila.select("a[href]"):
            href = cand.get("href", "")
            # El listado trae también enlaces de tipo ("Press Release") y
            # de redes. El del comunicado apunta a su propia página, que
            # cuelga de press-releases/<año>/<slug>.
            if re.search(r"/press-releases/\d{4}/", href):
                a = cand
                break
    if a is None:
        return None, None

    titulo = a.get_text(" ", strip=True)
    url = urljoin(base, a.get("href", ""))
    return (titulo or None), url


def _resumen(fila) -> str:
    cont = fila.find(
        lambda t: t.name == "div"
        and t.get("class")
        and any("node__content" in c or "publication-content" in c for c in t.get("class"))
    )
    texto = (cont or fila).get_text(" ", strip=True)
    # Quitar la etiqueta de tipo y el título, que ya van en sus campos.
    texto = re.sub(r"^\s*Press Release\s*", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto[:600]


def parse(url: str) -> list[dict]:
    """
    Devuelve los comunicados del listado.

    Contrato del pipeline: title (str), url (str absoluta),
    published (str 'YYYY-MM-DD' o None), summary (str).
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        log.error("EDPS: no se pudo descargar %s: %s", url, e)
        return []

    if r.status_code != 200:
        log.error("EDPS: %s devolvió HTTP %d", url, r.status_code)
        return []

    soup = BeautifulSoup(r.content, "lxml")
    filas, via = _filas(soup)
    log.info("EDPS: %d filas encontradas (%s)", len(filas), via)

    items, vistas = [], set()
    for fila in filas:
        titulo, enlace = _titulo_y_enlace(fila, r.url)
        if not titulo or not enlace:
            continue
        if enlace in vistas:
            continue
        vistas.add(enlace)

        items.append({
            "title": titulo,
            "url": enlace,
            "published": _fecha_de_la_fila(fila),
            "summary": _resumen(fila),
        })

    sin_fecha = sum(1 for i in items if not i["published"])
    log.info("EDPS: %d comunicados, %d sin fecha reconocible", len(items), sin_fecha)
    if items and sin_fecha == len(items):
        # Señal de que el bloque de fecha cambió: no es fatal (el ingest
        # conserva los items sin fecha) pero hay que saberlo.
        log.warning("EDPS: NINGÚN item trajo fecha. Revisar el bloque "
                    "publication-date, probablemente cambió el sitio.")
    return items
