# Reporte de descubrimiento de feeds

Corrida: 2026-09-18 15:10 UTC

- Autoridades sondeadas: **40**
- Con feed RSS/Atom válido: **19**
- Sin feed (necesitan scraper): **18**
- Sitio inaccesible desde el runner: **3**

Un feed cuenta como válido solo si el cuerpo se declara RSS, Atom o RDF y feedparser le saca al menos un item. La columna *Último item* es la que dice si el feed está vivo: un feed con fecha de hace dos años se trata como muerto y va a scraper.

La columna *Vía* decide si el feed sirve. **ruta de sección** y **autodiscovery** son feeds de la autoridad. **ruta del dominio** en una autoridad que vive dentro de un portal de gobierno es el feed del portal completo: trae las noticias de todo el gobierno y no se debe habilitar, porque el pipeline no filtra por tema.

## LatAm

| Autoridad | País | Estado | Feed encontrado | Items | Último item | Vía |
|---|---|---|---|---|---|---|
| AAIP | AR | RSS | `https://www.argentina.gob.ar/rss.xml` | 10 | 2026-09-04 | ruta del dominio |
| ANPD (BR) | BR | RSS | `https://www.gov.br/pt-br/assuntos/noticias/RSS` | 1 | 2026-07-01 | ruta del dominio |
| ↳ alterno | | | `https://www.gov.br/RSS` | 100 | 2026-09-17 | ruta del dominio |
| ↳ alterno | | | `https://www.gov.br/pt-br/RSS` | 100 | 2026-09-17 | ruta del dominio |
| ANTAI | PA | RSS | `https://antai.gob.pa/feed/` | 10 | 2026-08-20 | ruta del dominio |
| ANPD (PE) | PE | RSS | `https://www.gob.pe/busquedas.rss` | 25 | sin fecha | ruta del dominio |
| MITIC | PY | RSS | `https://mitic.gov.py/feed/` | 10 | 2026-09-18 | autodiscovery |
| SERNAC | CL | sin RSS | HTTP 200 en el home | | | |
| SIC | CO | inaccesible | SSLError: HTTPSConnectionPool(host='www.sic.gov.co', port=443): Max retries exceeded with url: / (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFIC | | | |
| PRODHAB | CR | sin RSS | HTTP 200 en el home | | | |
| SPDP | EC | sin RSS | HTTP 200 en el home | | | |
| SABG | MX | sin RSS | HTTP 200 en el home | | | |
| URCDP | UY | sin RSS | HTTP 200 en el home | | | |

## Europa

| Autoridad | País | Estado | Feed encontrado | Items | Último item | Vía |
|---|---|---|---|---|---|---|
| OCPDP | CY | RSS | `https://www.gov.cy/dataprotection/feed/` | 4 | 2026-02-17 | autodiscovery |
| ↳ alterno | | | `https://www.gov.cy/en/feed/` | 2636 | 2026-09-18 | ruta del dominio |
| ÚOOÚ (CZ) | CZ | RSS | `https://uoou.gov.cz/feed/cs-rss.xml` | 20 | 2026-08-11 | autodiscovery |
| BfDI | DE | RSS | `https://www.bfdi.bund.de/SiteGlobals/Functions/RSSFeed/Allgemein/rssnewsfeed.xml?nn=252136&archiv=true` | 30 | 2026-09-11 | autodiscovery |
| AKI | EE | RSS | `https://www.aki.ee/rss-feeds/rss.xml` | 100 | 2026-09-16 | autodiscovery |
| AEPD | ES | RSS | `https://www.aepd.es/noticias/feed.xml` | 25 | 2026-09-09 | ruta del dominio |
| CNIL | FR | RSS | `https://www.cnil.fr/fr/rss.xml` | 10 | 2026-09-17 | ruta de sección |
| AZOP | HR | RSS | `https://azop.hr/feed/` | 10 | 2026-09-17 | autodiscovery |
| ↳ alterno | | | `https://azop.hr/en/feed/` | 10 | 2026-07-20 | ruta del dominio |
| Garante | IT | RSS | `https://www.garanteprivacy.it/o/gpdp-rss/rss?t=news` | 10 | 2026-09-16 | autodiscovery |
| IDPC | MT | RSS | `https://idpc.org.mt/feed/` | 10 | 2026-09-09 | autodiscovery |
| AP | NL | RSS | `https://autoriteitpersoonsgegevens.nl/feed/article/rss.xml` | 10 | 2026-09-15 | ruta del dominio |
| ↳ alterno | | | `https://autoriteitpersoonsgegevens.nl/en/feed/article/rss.xml` | 10 | 2026-08-21 | ruta del dominio |
| ANSPDCP | RO | RSS | `https://www.dataprotection.ro/feed` | 5 | sin fecha | ruta del dominio |
| ↳ alterno | | | `https://www.dataprotection.ro/feed/` | 5 | sin fecha | ruta del dominio |
| IMY | SE | RSS | `https://www.imy.se/nyheter/rss` | 214 | 2026-09-18 | autodiscovery |
| ↳ alterno | | | `https://www.imy.se/nyheter/rss/` | 214 | 2026-09-18 | ruta del dominio |
| EDPB | UE | RSS | `https://www.edpb.europa.eu/feed/news_en` | 10 | 2026-09-11 | autodiscovery |
| ↳ alterno | | | `https://www.edpb.europa.eu/feed/publications_en` | 10 | 2026-07-31 | autodiscovery |
| ↳ alterno | | | `https://www.edpb.europa.eu/rss.xml_en` | 10 | 2026-09-11 | ruta del dominio |
| EDPS | UE | RSS | `https://www.edps.europa.eu/feed/news_en` | 10 | 2026-09-15 | autodiscovery |
| DSB | AT | sin RSS | HTTP 200 en el home | | | |
| APD-GBA | BE | inaccesible | ConnectTimeout: HTTPSConnectionPool(host='www.autoriteprotectiondonnees.be', port=443): Max retries exceeded with url: / (Caused by ConnectTimeoutError(<HTTPSConnecti | | | |
| KZLD | BG | inaccesible | SSLError: HTTPSConnectionPool(host='www.cpdp.bg', port=443): Max retries exceeded with url: / (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE | | | |
| Datatilsynet (DK) | DK | sin RSS | HTTP 200 en el home | | | |
| Tietosuoja | FI | sin RSS | HTTP 403 en el home | | | |
| HDPA | GR | sin RSS | HTTP 200 en el home | | | |
| NAIH | HU | sin RSS | HTTP 200 en el home | | | |
| DPC | IE | sin RSS | HTTP 200 en el home | | | |
| VDAI | LT | sin RSS | HTTP 403 en el home | | | |
| CNPD (LU) | LU | sin RSS | HTTP 200 en el home | | | |
| DVI | LV | sin RSS | HTTP 200 en el home | | | |
| UODO | PL | sin RSS | HTTP 200 en el home | | | |
| CNPD (PT) | PT | sin RSS | HTTP 200 en el home | | | |
| IP-RS | SI | sin RSS | HTTP 403 en el home | | | |
| ÚOOÚ (SK) | SK | sin RSS | HTTP 200 en el home | | | |

## Qué hacer con esto

Para cada autoridad con feed válido, en `config/feeds.yaml`: copiar la URL a `url`, poner `source: rss` y `enabled: true`. El campo `site` no se toca, queda como referencia y como insumo de la próxima corrida de este sondeo.

Para cada autoridad sin RSS: escribir un scraper en `src/scrapers/`, con firma `parse(url) -> list[dict]` y los campos `title`, `url`, `published` (string `YYYY-MM-DD`, **no** objeto datetime) y `summary`. Luego en el bloque: `url` con la página de noticias, `source: scraper`, `scraper_module` con el nombre del módulo y `enabled: true`.

Para las inaccesibles: reintentar el workflow. Si el error persiste, revisar si el organismo cambió de dominio; varios sitios del inventario siguen en HTTP sin certificado.
