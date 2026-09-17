"""
Sonda de descubrimiento de feeds RSS/Atom.

Problema que resuelve: el inventario de autoridades de protección de
datos trae sitios institucionales, no feeds. A diferencia del monitor
financiero (donde BIS, IMF y los bancos centrales publican RSS bien
documentado), aquí no se sabe de antemano qué autoridad tiene feed.
Probar a mano 40 sitios es lento y adivinar rutas es peor: termina en
un feeds.yaml con URLs inventadas.

Este script sondea los 40 sitios y dice, con evidencia, cuál tiene feed
y cuál va a necesitar scraper. Corre en GitHub Actions (workflow
"Descubrir feeds"), que tiene salida a internet sin restricciones.

Para cada sitio declarado en config/feeds.yaml hace tres cosas:

    1. Descarga el home y lee los <link rel="alternate"> de
       autodiscovery, que es el mecanismo estándar por el que un sitio
       declara sus feeds.
    2. Si no encuentra nada, prueba las rutas convencionales (/rss,
       /feed, /rss.xml y variantes), más los patrones propios de los
       gestores de contenido que usan estos organismos: Plone (/RSS),
       Drupal (/rss.xml), WordPress (/?feed=rss2), GSB del gobierno
       alemán, y el patrón de los portales gob.mx / gob.pe / gub.uy.
    3. Valida cada candidato con feedparser: solo cuenta como feed si
       parsea y entrega al menos un item. Registra cuántos items trae
       y la fecha del más reciente, que es lo que permite distinguir un
       feed vivo de uno abandonado hace tres años.

Salida: config/discovery-report.md, una tabla por región con el estado
de cada autoridad y la URL exacta del feed encontrado, lista para
copiar al bloque correspondiente de feeds.yaml.

Uso local (si tienes salida a internet a estos dominios):
    python tools/discover_feeds.py
    python tools/discover_feeds.py --only CNIL,AEPD,EDPB
"""

import argparse
import logging
import re
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import requests
import urllib3
import yaml

warnings.filterwarnings("ignore")
urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("discover")

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "feeds.yaml"
REPORT = ROOT / "config" / "discovery-report.md"

# Varios de estos sitios devuelven 403 a clientes sin User-Agent de
# navegador. No es evasión de nada: es el mínimo para que un lector de
# feeds legítimo sea atendido.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es,en;q=0.9",
}

TIMEOUT = 30

# Rutas convencionales, ordenadas de más a menos probable.
COMMON_PATHS = [
    "/rss.xml",          # Drupal (CNIL, EDPB y varios sitios europa.eu)
    "/rss",
    "/feed",
    "/feed/",
    "/atom.xml",
    "/index.xml",
    "/RSS",              # Plone (portales gov.br)
    "/?feed=rss2",       # WordPress
    "/rss/noticias.xml",
    "/noticias/rss",
    "/news/rss",
    "/rss/news",
    "/en/rss",
    "/es/rss",
    "/sitemap-rss.xml",
]

# Rutas adicionales por dominio, cuando el gestor de contenido tiene un
# patrón conocido que no cae en la lista general.
DOMAIN_PATHS = {
    "bfdi.bund.de": [
        # Government Site Builder: el feed vive bajo SiteGlobals.
        "/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/RSSNewsfeed.xml",
        "/SiteGlobals/Functions/RSSFeed/RSSNewsfeed.xml",
    ],
    "gov.br": ["/pt-br/assuntos/noticias/RSS", "/RSS", "/pt-br/RSS"],
    "argentina.gob.ar": ["/noticias/rss", "/rss"],
    "gob.pe": ["/institucion/anpd/noticias.rss", "/busquedas.rss"],
    "gub.uy": ["/comunicacion/noticias/rss", "/rss"],
    "garanteprivacy.it": [
        "/web/guest/home/rss",
        "/rss/comunicati-stampa",
        "/-/rss",
    ],
    "aepd.es": ["/es/rss.xml", "/rss/prensa.xml", "/informes-y-resoluciones/rss"],
    "cnil.fr": ["/fr/rss.xml", "/fr/actualites/rss"],
    "edpb.europa.eu": ["/news/news_en/rss.xml", "/feed/news_en"],
    "edps.europa.eu": ["/press-publications/press-news/press-releases_en/rss"],
    "imy.se": ["/nyheter/rss/", "/rss/"],
    "dataprotection.ie": ["/en/rss.xml", "/en/news-media/rss"],
    "uodo.gov.pl": ["/pl/rss", "/pl/f/rss"],
    "autoriteitpersoonsgegevens.nl": ["/actueel/rss", "/nl/rss"],
    "sic.gov.co": ["/rss-noticias", "/noticias/rss"],
}


def fetch(url: str, allow_http_fallback: bool = True):
    """
    GET tolerante. Devuelve la response o la excepción.

    Tres autoridades del inventario (SIC Colombia, KZLD Bulgaria y AZOP
    Croacia) sirven un certificado que Python rechaza, así que por HTTPS
    son inalcanzables y el sondeo las reportaba como caídas. Para esos
    casos se reintenta por HTTP plano en lugar de desactivar la
    verificación del certificado, que sería peor: aquí solo se leen
    titulares públicos, y un HTTP honesto es preferible a un HTTPS que
    finge validar. La response trae marcado `via_http` para que el
    reporte lo diga en lugar de esconderlo.
    """
    try:
        return requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except requests.exceptions.SSLError as e:
        if allow_http_fallback and url.startswith("https://"):
            try:
                r = requests.get(
                    "http://" + url[len("https://"):],
                    headers=HEADERS, timeout=TIMEOUT, allow_redirects=True,
                )
                setattr(r, "via_http", True)
                return r
            except Exception:
                return e
        return e
    except Exception as e:  # noqa: BLE001 - queremos registrar cualquier fallo
        return e


def validate_feed(url: str) -> dict | None:
    """
    Valida un candidato a feed. Devuelve None si no lo es.

    El criterio de "sí es feed" es deliberadamente estricto: el cuerpo
    tiene que declararse como RSS, Atom o RDF, y feedparser tiene que
    sacarle al menos un item. Un HTML que responde 200 en /rss no
    cuenta, y es un caso común en estos sitios.
    """
    r = fetch(url)
    if isinstance(r, Exception) or r.status_code != 200:
        return None

    head = r.content[:600].lower()
    if not (b"<rss" in head or b"<feed" in head or b"<rdf" in head):
        return None

    parsed = feedparser.parse(r.content)
    if not parsed.entries:
        return None

    dates = []
    for entry in parsed.entries[:10]:
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if stamp:
            dates.append(f"{stamp[0]:04d}-{stamp[1]:02d}-{stamp[2]:02d}")

    return {
        "feed_url": r.url,
        "entries": len(parsed.entries),
        "latest": max(dates) if dates else None,
        "feed_title": (parsed.feed.get("title") or "").strip()[:80],
        "http_only": bool(getattr(r, "via_http", False)) or r.url.startswith("http://"),
    }


def autodiscovery_candidates(response, html: str) -> list[str]:
    """
    Extrae los feeds declarados por el propio sitio en el <head>.
    Es el camino correcto: si el sitio declara su feed, lo usamos tal
    cual en lugar de adivinar rutas.
    """
    found = []
    for match in re.finditer(r"<link[^>]+>", html, re.I):
        tag = match.group(0)
        if not re.search(r'type\s*=\s*["\']application/(rss|atom)\+xml', tag, re.I):
            continue
        href = re.search(r'href\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        if href:
            found.append(urljoin(response.url, href.group(1).replace("&amp;", "&")))
    return found


def probe(feed_cfg: dict) -> dict:
    """Sondea una autoridad y devuelve su resultado."""
    regulator = feed_cfg.get("regulator", "?")
    site = feed_cfg.get("site", "")
    result = {
        "regulator": regulator,
        "authority": feed_cfg.get("authority", ""),
        "region": feed_cfg.get("region", ""),
        "country": feed_cfg.get("country", ""),
        "site": site,
        "home_status": None,
        "feeds": [],
        "error": "",
    }

    if not site:
        result["error"] = "sin sitio declarado en feeds.yaml"
        return result

    response = fetch(site)
    if isinstance(response, Exception):
        result["error"] = f"{type(response).__name__}: {str(response)[:150]}"
    else:
        result["home_status"] = response.status_code
        if response.status_code == 200:
            for candidate in autodiscovery_candidates(response, response.text[:500000]):
                valid = validate_feed(candidate)
                if valid and valid["feed_url"] not in [f["feed_url"] for f in result["feeds"]]:
                    valid["via"] = "autodiscovery"
                    result["feeds"].append(valid)

    # Base para las rutas convencionales: la URL final tras redirecciones,
    # porque varios de estos sitios redirigen de www a subdominio o de
    # http a https y las rutas cuelgan del destino real.
    final_url = site if isinstance(response, Exception) else response.url
    parts = urlparse(final_url)
    origin = f"{parts.scheme}://{parts.netloc}"

    # Varias autoridades no tienen sitio propio: viven dentro de un portal
    # de gobierno (argentina.gob.ar/aaip, gov.br/anpd, gob.pe/anpd,
    # gub.uy/unidad-..., gov.cy/dataprotection). Ahí el feed del dominio
    # existe pero es del portal completo y sirve de nada: trae las
    # noticias de todo el gobierno. El feed útil, si existe, cuelga de la
    # ruta de la autoridad. Por eso se sondean DOS bases y la de sección
    # va primero, para que gane en el reporte.
    section = parts.path.rstrip("/")
    bases = []
    if section and section != "":
        bases.append((origin + section, "ruta de sección"))
    bases.append((origin, "ruta del dominio"))

    extra = []
    for domain, paths in DOMAIN_PATHS.items():
        if domain in parts.netloc:
            extra.extend(paths)

    seen = {f["feed_url"] for f in result["feeds"]}
    for base, scope in bases:
        if len(result["feeds"]) >= 3:
            break
        for path in extra + COMMON_PATHS:
            candidate = base + path
            if candidate in seen:
                continue
            seen.add(candidate)
            valid = validate_feed(candidate)
            if valid and valid["feed_url"] not in [f["feed_url"] for f in result["feeds"]]:
                valid["via"] = scope
                result["feeds"].append(valid)
            if len(result["feeds"]) >= 3:
                break

    log.info(
        "%-16s %-7s home:%-4s feeds:%d %s",
        regulator, result["country"], result["home_status"],
        len(result["feeds"]), result["error"],
    )
    return result


def render_report(results: list[dict], regions: list[str]) -> str:
    """Arma el markdown del reporte, una tabla por región."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    con_feed = [r for r in results if r["feeds"]]
    sin_feed = [r for r in results if not r["feeds"] and not r["error"]]
    con_error = [r for r in results if not r["feeds"] and r["error"]]

    lines = [
        "# Reporte de descubrimiento de feeds",
        "",
        f"Corrida: {stamp}",
        "",
        f"- Autoridades sondeadas: **{len(results)}**",
        f"- Con feed RSS/Atom válido: **{len(con_feed)}**",
        f"- Sin feed (necesitan scraper): **{len(sin_feed)}**",
        f"- Sitio inaccesible desde el runner: **{len(con_error)}**",
        "",
        "Un feed cuenta como válido solo si el cuerpo se declara RSS, Atom o RDF "
        "y feedparser le saca al menos un item. La columna *Último item* es la "
        "que dice si el feed está vivo: un feed con fecha de hace dos años se "
        "trata como muerto y va a scraper.",
        "",
        "La columna *Vía* decide si el feed sirve. **ruta de sección** y "
        "**autodiscovery** son feeds de la autoridad. **ruta del dominio** en una "
        "autoridad que vive dentro de un portal de gobierno es el feed del portal "
        "completo: trae las noticias de todo el gobierno y no se debe habilitar, "
        "porque el pipeline no filtra por tema.",
        "",
    ]

    for region in regions:
        block = [r for r in results if r["region"] == region]
        if not block:
            continue
        lines += [
            f"## {region}",
            "",
            "| Autoridad | País | Estado | Feed encontrado | Items | Último item | Vía |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in sorted(block, key=lambda x: (not x["feeds"], x["country"])):
            if r["feeds"]:
                best = r["feeds"][0]
                aviso = " ⚠️ solo HTTP" if best.get("http_only") else ""
                lines.append(
                    f"| {r['regulator']} | {r['country']} | RSS{aviso} | "
                    f"`{best['feed_url']}` | {best['entries']} | "
                    f"{best['latest'] or 'sin fecha'} | {best['via']} |"
                )
                for alt in r["feeds"][1:]:
                    lines.append(
                        f"| ↳ alterno | | | `{alt['feed_url']}` | "
                        f"{alt['entries']} | {alt['latest'] or 'sin fecha'} | {alt['via']} |"
                    )
            else:
                estado = "inaccesible" if r["error"] else "sin RSS"
                detalle = r["error"] or f"HTTP {r['home_status']} en el home"
                lines.append(
                    f"| {r['regulator']} | {r['country']} | {estado} | "
                    f"{detalle} | | | |"
                )
        lines.append("")

    lines += [
        "## Qué hacer con esto",
        "",
        "Para cada autoridad con feed válido, en `config/feeds.yaml`: copiar la "
        "URL a `url`, poner `source: rss` y `enabled: true`. El campo `site` no "
        "se toca, queda como referencia y como insumo de la próxima corrida de "
        "este sondeo.",
        "",
        "Para cada autoridad sin RSS: escribir un scraper en `src/scrapers/`, "
        "con firma `parse(url) -> list[dict]` y los campos `title`, `url`, "
        "`published` (string `YYYY-MM-DD`, **no** objeto datetime) y `summary`. "
        "Luego en el bloque: `url` con la página de noticias, "
        "`source: scraper`, `scraper_module` con el nombre del módulo y "
        "`enabled: true`.",
        "",
        "Para las inaccesibles: reintentar el workflow. Si el error persiste, "
        "revisar si el organismo cambió de dominio; varios sitios del inventario "
        "siguen en HTTP sin certificado.",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--only",
        default="",
        help="Lista de acrónimos separados por coma, para sondear solo esos.",
    )
    ap.add_argument(
        "--workers", type=int, default=6,
        help="Sondeos en paralelo. Bajarlo si algún sitio devuelve 429.",
    )
    args = ap.parse_args()

    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    feeds = config.get("feeds", [])
    regions = config.get("settings", {}).get("regions", ["LatAm", "Europa"])

    if args.only:
        wanted = {x.strip().lower() for x in args.only.split(",") if x.strip()}
        feeds = [f for f in feeds if f.get("regulator", "").lower() in wanted]
        if not feeds:
            log.error("Ningún regulator coincide con --only %s", args.only)
            sys.exit(1)

    log.info("Sondeando %d autoridades con %d workers...", len(feeds), args.workers)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(probe, feeds))

    REPORT.write_text(render_report(results, regions), encoding="utf-8")
    log.info("Reporte escrito: %s", REPORT)

    con_feed = sum(1 for r in results if r["feeds"])
    log.info(
        "Resultado: %d de %d autoridades con feed RSS válido.",
        con_feed, len(results),
    )


if __name__ == "__main__":
    main()
