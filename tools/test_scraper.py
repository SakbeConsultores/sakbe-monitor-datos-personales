"""
Banco de pruebas de scrapers.

Corre UN scraper suelto y muestra lo que extrajo, sin tocar Notion ni
escribir nada. Existe porque el ciclo de trabajo de un scraper es
inevitablemente iterativo, y hacerlo con la ingesta completa significa
esperar la corrida entera y arriesgar basura en la base de producción.

Se dispara desde el workflow "Probar scraper" en la pestaña Actions,
que es donde hay salida a internet sin restricciones.

Además de imprimir los items, valida el contrato que el pipeline espera
y que ya rompió una vez en el monitor financiero:

    title      str no vacío
    url        str, absoluta (http/https)
    published  str 'YYYY-MM-DD' o None. NUNCA un objeto datetime:
               is_too_old() hace strptime sobre este valor y truena con
               TypeError si recibe datetime
    summary    str (puede ser '')

Uso local:
    python tools/test_scraper.py --module edps_press
    python tools/test_scraper.py --module edps_press --url https://...
"""

import argparse
import importlib
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("test-scraper")

FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def url_del_config(modulo: str) -> str | None:
    """Busca en feeds.yaml la url declarada para ese scraper_module."""
    cfg = yaml.safe_load((ROOT / "config" / "feeds.yaml").read_text(encoding="utf-8"))
    for f in cfg.get("feeds", []):
        if f.get("scraper_module") == modulo:
            return f.get("url") or f.get("site")
    return None


def revisar(items: list) -> list[str]:
    """Devuelve la lista de problemas encontrados. Vacía es aprobado."""
    fallas = []
    if not isinstance(items, list):
        return ["parse() no devolvió una lista, devolvió %s" % type(items).__name__]
    if not items:
        return ["parse() devolvió una lista vacía"]

    vistas = set()
    for i, it in enumerate(items):
        pre = "item %d" % i
        if not isinstance(it, dict):
            fallas.append("%s: no es un dict" % pre)
            continue

        t = it.get("title")
        if not isinstance(t, str) or not t.strip():
            fallas.append("%s: title vacío o no es str" % pre)

        u = it.get("url")
        if not isinstance(u, str) or not u.startswith(("http://", "https://")):
            fallas.append("%s: url no es absoluta (%r)" % (pre, u))
        elif u in vistas:
            fallas.append("%s: url repetida, el dedup de Notion la va a descartar (%s)" % (pre, u))
        else:
            vistas.add(u)

        p = it.get("published")
        if p is not None:
            if isinstance(p, datetime):
                fallas.append("%s: published es datetime. Debe ser string 'YYYY-MM-DD' "
                              "o el ingest truena en is_too_old()" % pre)
            elif not isinstance(p, str) or not FECHA.match(p):
                fallas.append("%s: published no tiene formato YYYY-MM-DD (%r)" % (pre, p))
            else:
                try:
                    datetime.strptime(p, "%Y-%m-%d")
                except ValueError:
                    fallas.append("%s: published no es una fecha real (%r)" % (pre, p))

        s = it.get("summary")
        if s is not None and not isinstance(s, str):
            fallas.append("%s: summary no es str" % pre)

    return fallas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True, help="Nombre del módulo en src/scrapers/, sin .py")
    ap.add_argument("--url", default="", help="URL a parsear. Si se omite, se toma de feeds.yaml")
    args = ap.parse_args()

    url = args.url.strip() or url_del_config(args.module)
    if not url:
        log.error("No hay url: pásala con --url o declárala en feeds.yaml para %s", args.module)
        sys.exit(1)

    log.info("Scraper: %s", args.module)
    log.info("URL:     %s", url)

    try:
        mod = importlib.import_module("scrapers.%s" % args.module)
    except ImportError as e:
        log.error("No se pudo importar scrapers.%s: %s", args.module, e)
        sys.exit(1)

    items = mod.parse(url)

    print()
    print("=" * 78)
    print("ITEMS EXTRAÍDOS: %d" % (len(items) if isinstance(items, list) else -1))
    print("=" * 78)
    for i, it in enumerate(items if isinstance(items, list) else []):
        print()
        print("[%02d] %s" % (i, (it.get("published") or "sin fecha")))
        print("     %s" % str(it.get("title"))[:110])
        print("     %s" % str(it.get("url"))[:110])
        res = (it.get("summary") or "").replace("\n", " ")
        print("     resumen: %s" % (res[:110] + ("…" if len(res) > 110 else "") if res else "(vacío)"))

    fallas = revisar(items)
    print()
    print("=" * 78)
    if fallas:
        print("CONTRATO: %d PROBLEMA(S)" % len(fallas))
        for f in fallas:
            print("  - %s" % f)
        print("=" * 78)
        sys.exit(1)
    con_fecha = sum(1 for i in items if i.get("published"))
    print("CONTRATO OK. %d items, %d con fecha, %d sin fecha." %
          (len(items), con_fecha, len(items) - con_fecha))
    print("=" * 78)


if __name__ == "__main__":
    main()
