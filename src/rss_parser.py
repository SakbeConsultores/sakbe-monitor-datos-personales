"""
Lector de feeds RSS y Atom.

Usa la librería feedparser para procesar feeds estándar.
Devuelve una lista de items normalizados con la misma estructura
que producirán los scrapers (módulos en src/scrapers/), de modo
que el resto del pipeline no distingue entre RSS y scraping.
"""

import re
import logging
from datetime import datetime, timezone

import feedparser
import requests


log = logging.getLogger(__name__)

# Varios sitios de autoridades rechazan o sirven distinto a un cliente sin
# User-Agent de navegador. No es evasión: es el mínimo para que un lector de
# feeds legítimo sea atendido igual que un navegador.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    "Accept-Language": "es,en;q=0.9",
}

TIMEOUT = 30


def _download(url: str):
    """
    Descarga el feed y devuelve los bytes, o None si no se pudo.

    Reintenta por HTTP plano cuando el certificado TLS es inválido, igual
    que tools/discover_feeds.py: un HTTP honesto es preferible a
    desactivar la verificación del certificado, y aquí solo se leen
    titulares públicos.
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except requests.exceptions.SSLError:
        if not url.startswith("https://"):
            log.warning("Fallo de TLS irrecuperable en %s", url)
            return None
        try:
            r = requests.get(
                "http://" + url[len("https://"):],
                headers=HEADERS, timeout=TIMEOUT, allow_redirects=True,
            )
            log.info("Feed %s servido por HTTP (certificado TLS inválido)", url)
        except Exception as e:  # noqa: BLE001
            log.warning("No se pudo descargar %s: %s", url, e)
            return None
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo descargar %s: %s", url, e)
        return None

    if r.status_code != 200:
        log.warning("Feed %s devolvió HTTP %d", url, r.status_code)
        return None

    return r.content


def parse_feed(url: str) -> list[dict]:
    """
    Parsea un feed RSS y devuelve una lista de items.

    Cada item es un diccionario con:
        title     - título del comunicado (str)
        url       - URL al comunicado original (str)
        published - fecha en formato ISO 8601 YYYY-MM-DD (str, puede ser "")
        summary   - resumen del item, sin HTML (str, puede ser "")

    La descarga la hace requests y no feedparser. Parece un detalle y no lo
    es: en la primera ingesta real (17-sep-2026) cuatro feeds válidos
    (CNIL, ANTAI, AP holandesa y la oficina chipriota) devolvieron cero
    items con el error "not well-formed (invalid token)", mientras que la
    sonda de descubrimiento los había parseado sin problema en el mismo
    runner y con la misma versión de feedparser. La única diferencia era
    que la sonda descarga con requests y le entrega los bytes. Desde
    entonces el lector y la sonda comparten el mismo camino de descarga,
    que además es la única forma de mandar User-Agent de navegador y de
    reintentar por HTTP los sitios con certificado roto.
    """
    raw = _download(url)
    if raw is None:
        return []

    feed = feedparser.parse(raw)

    # Si feedparser marca un error y no obtuvo entries, abortamos
    if feed.bozo and not feed.entries:
        log.warning("Feed con problemas: %s - %s", url, feed.bozo_exception)
        return []

    # Feed mal formado del que aun así se rescataron items: se aprovechan,
    # pero queda en el log para saber que ese feed viene sucio.
    if feed.bozo and feed.entries:
        log.info("Feed %s mal formado pero recuperado (%s)", url, feed.bozo_exception)

    items = []
    for entry in feed.entries:
        title = _clean(entry.get("title", ""))
        link = entry.get("link", "")
        summary = _clean(
            entry.get("summary", "")
            or entry.get("description", "")
        )
        published = _parse_date(entry)

        # Skip items sin título o sin link, no nos sirven
        if not title or not link:
            continue

        items.append({
            "title": title,
            "url": link,
            "published": published,
            "summary": summary,
        })

    log.info("Feed %s entregó %d items", url, len(items))
    return items


def _clean(text: str) -> str:
    """Quita etiquetas HTML, normaliza espacios y decodifica entidades."""
    if not text:
        return ""
    # Quitar tags HTML
    text = re.sub(r"<[^>]+>", " ", text)
    # Decodificar entidades HTML básicas
    text = (text
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'"))
    # Normalizar espacios
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_date(entry) -> str:
    """
    Extrae la fecha del item RSS y devuelve YYYY-MM-DD.
    feedparser ya parsea la fecha en .published_parsed (tupla).
    Si no hay fecha válida, retorna "".
    """
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                return dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                continue
    return ""
