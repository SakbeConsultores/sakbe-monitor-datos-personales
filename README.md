# Monitor Regulatorio de Protección de Datos Personales

Sakbé Consultores. Réplica del [Monitor de Reguladores Financieros](https://github.com/SakbeConsultores/sakbe-monitor-reguladores) con un inventario de fuentes distinto: las autoridades de protección de datos personales de Latinoamérica y Europa.

La arquitectura es la misma y deliberadamente igual, para que lo que se aprenda manteniendo un monitor sirva para el otro: GitHub Actions dispara un script de Python, el script lee cada fuente, dedupea contra Notion, inserta lo nuevo, exporta un JSON y GitHub Pages lo sirve como dashboard.

```
GitHub Actions (cron 2x día)
        │
        ├─ src/ingest.py ──── lee config/feeds.yaml
        │                     ├─ source: rss     → src/rss_parser.py
        │                     └─ source: scraper → src/scrapers/<módulo>.py
        │
        ├─ dedup por URL contra Notion → inserta items nuevos
        ├─ exporta docs/data/monitor.json
        └─ commitea el JSON
                │
                └─ GitHub Pages sirve docs/index.html (dashboard)
```

## Qué cambia respecto al monitor financiero

Tres cosas, y solo tres.

**El inventario de fuentes.** 40 autoridades: las 27 nacionales de la UE, los dos órganos de coordinación europeos (EDPB y EDPS) y las 11 autoridades latinoamericanas con marco y autoridad activa. El inventario viene del documento *Autoridades de Protección de Datos Personales — Europa y Latinoamérica*, secciones 1.1, 1.2 y 2 (tabla principal). Quedan fuera por decisión de alcance el Espacio Económico Europeo, Reino Unido, Suiza, los países sin autoridad dedicada y los de marco parcial.

**El campo `region`.** Cada fuente declara si es `LatAm` o `Europa`. Ese campo viaja al item, se guarda en Notion como propiedad `Region` y es lo que alimenta las dos pestañas del dashboard. En el monitor financiero el primer corte era por país; aquí el primer corte es la región y el país quedó como subfiltro.

**El estado por fuente.** Los campos `enabled` y `source: pending` permiten declarar las 40 autoridades desde el arranque e irlas habilitando conforme se confirma cada feed, sin que el pipeline truene por las que faltan. El monitor financiero no lo necesitaba porque BIS, FMI y los bancos centrales publican RSS bien documentado. Aquí no: el inventario trae sitios institucionales, no feeds, y una autoridad europea pequeña puede perfectamente no tener ninguno.

## Estado actual

Pipeline completo y corriendo en falso: las 40 autoridades están declaradas, ninguna habilitada. Falta el paso de descubrimiento.

No se hizo desde el entorno donde se construyó el repo porque la política de salida a internet de esa sesión bloquea estos dominios, y adivinar rutas de feed habría dejado un `feeds.yaml` con URLs inventadas. El descubrimiento se resolvió moviéndolo a donde sí hay red abierta: GitHub Actions.

## Puesta en marcha

**1. Base de Notion.** Ya está creada en el workspace Sakbé, con las nueve propiedades y todas las opciones de los selects precargadas.

- Base: **Monitor de Protección de Datos Personales**
- Workspace: **SoyGustavoMondragon**, en Private
- `NOTION_DATABASE_ID` = `9c00e1df2fda836ea53301d00c7758cd`
- Integración conectada: *Sakbé Monitor Ingesta* (la misma del monitor financiero)

La base se creó primero en el workspace Sakbé y se duplicó a SoyGustavoMondragon con `•••` → Move to, que en Notion duplica en lugar de mover. El id de arriba es el del duplicado, que es el que vale. La base original en Sakbé (id `7990419157fd447496b246682961a83d`) quedó obsoleta y se borra.

Esquema, para referencia:

| Propiedad | Tipo | Contenido |
|---|---|---|
| `Título` | Title | Título de la publicación |
| `URL` | URL | Enlace original. Es la llave de deduplicación |
| `Resumen` | Text | Resumen del item |
| `Regulador` | Select | Acrónimo de la autoridad, ej. `AEPD`, `CNIL`, `SPDP` |
| `Region` | Select | `LatAm` o `Europa` |
| `Pais` | Select | Código ISO de 2 letras, o `UE` para EDPB y EDPS |
| `Tipo` | Select | Sección leída, ej. `Noticias` |
| `Fecha Publicación` | Date | Fecha del item |
| `Feed RSS` | Text | URL de la fuente que lo trajo, para auditar |

Los nombres de las propiedades tienen que coincidir letra por letra con lo que escribe `notion_client.py`, incluido el acento en `Título` y la falta de acento en `Pais` y `Region`. Si alguna se renombra desde Notion, la inserción empieza a fallar con error 400.

En los Secrets del repo:

- `NOTION_TOKEN` — token de *Sakbé Monitor Ingesta*, el mismo del monitor financiero
- `NOTION_DATABASE_ID` — `9c00e1df2fda836ea53301d00c7758cd`

Si la primera corrida devuelve 404 al consultar la base, el problema casi nunca es el id: es que la integración quedó conectada a la base equivocada (la original en Sakbé en lugar del duplicado) o que el token pertenece a otro workspace. Verificar en `•••` → Conexiones de la base duplicada.

**2. Descubrir los feeds.** En la pestaña Actions, correr **Descubrir feeds**. Sondea los 40 sitios, valida cada candidato y commitea `config/discovery-report.md` con una tabla por región: qué autoridad tiene RSS, con qué URL exacta, cuántos items trae y de qué fecha es el más reciente.

Toma unos minutos. El campo `only` permite sondear un subconjunto (`CNIL,AEPD,EDPB`) cuando solo se quiere reverificar algo.

**3. Llenar `feeds.yaml`.** Con el reporte en la mano, para cada autoridad con feed válido: copiar la URL a `url`, poner `source: rss` y `enabled: true`. El campo `site` no se toca nunca, es la referencia institucional y el insumo del próximo sondeo.

**4. Primera ingesta.** Correr **Ingest Protección de Datos** a mano. A partir de ahí el cron se encarga (9:05 y 15:05 CDMX).

**5. Publicar el dashboard.** Settings → Pages → source `main`, folder `/docs`.

## Las autoridades sin RSS

Las que el reporte marque como *sin RSS* necesitan un scraper en `src/scrapers/`, con el mismo contrato del monitor financiero:

```python
def parse(url: str) -> list[dict]:
    # cada dict: title (str), url (str),
    #            published (str 'YYYY-MM-DD' o None),
    #            summary (str, puede ser '')
```

`published` es **string**, no objeto `datetime`. Esa fue la causa de la única falla real del monitor financiero: `is_too_old()` hace `strptime` sobre el valor y truena con `TypeError` si recibe un datetime.

Para sitios que renderizan con JavaScript está `src/scrapers/_playwright_helper.py`, con la función `render_page(url, wait_for_selector, timeout_ms)`. Ya viene copiado del otro repo y el workflow ya cachea Chromium.

Orden sugerido, por valor sobre esfuerzo: primero EDPB y EDPS, que condicionan a los 27 y comparten plataforma `europa.eu`; luego AEPD, CNIL, Garante y DPC irlandesa, que son las autoridades nacionales que producen criterio; luego las latinoamericanas, agrupando por plataforma (`gov.br`, `gob.mx`, `gob.pe`, `gub.uy` comparten gestor de contenido entre sí, lo que permite reusar código); al final el resto de Europa.

## Estructura

```
config/feeds.yaml            inventario de las 40 autoridades
config/discovery-report.md   lo escribe el workflow de descubrimiento
src/ingest.py                orquestador
src/rss_parser.py            lector de RSS y Atom (idéntico al monitor financiero)
src/notion_client.py         cliente de Notion (+ propiedad Region)
src/scrapers/                un módulo por sitio sin RSS
tools/discover_feeds.py      sonda de feeds
docs/index.html              dashboard con pestañas Latam y Europa
docs/data/monitor.json       lo escribe el ingest
```

## Notas de operación

El insumo recomienda revisar el inventario cada trimestre, y con razón: Chile tiene una autoridad creada que aún no opera, Paraguay está en transición hasta noviembre de 2027, y México cambió de autoridad en 2025. Chile y Paraguay entran al monitor por sus entidades tutelares (SERNAC y MITIC), lo cual es una aproximación explícita, no la autoridad de datos. Cuando publiquen sitio propio hay que agregar su bloque y decidir si la tutelar se conserva.
