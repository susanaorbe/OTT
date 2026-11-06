# Mi TV — versión para GitHub Pages

Mi TV es una web estática para GitHub Pages. GitHub Actions ejecuta Python y genera los JSON que consulta la web. No necesita un servidor Python permanente.

## Estructura del repositorio

Sube el contenido de esta carpeta a la raíz de un **repositorio nuevo**, separado del repositorio `Agenda`:

```text
mi-tv/
├── .github/
│   └── workflows/
│       └── update_mi_tv.yml
├── config/
│   └── channels.json
├── docs/                    # Carpeta que publicará GitHub Pages
│   ├── .nojekyll
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── data/
│       ├── channels.json
│       ├── events_cdn.json
│       ├── events_futbolenlatv.json
│       ├── channel_checks.json # Caché de comprobaciones de reproductores
│       └── playback.json       # Archivo antiguo; ya no decide qué canales se muestran
├── agenda_futbolenlatv.py
├── channel_catalog.py       # Comprueba las páginas oficiales de reproductor
├── cdn_event_filter.py      # Aplica a CDN las reglas de competiciones de Futbolenlatv
├── server.py                # Solo para pruebas locales
├── update_data.py           # Genera los JSON estáticos
├── requirements.txt
└── tests/
    ├── test_cdn_event_filter.py
    ├── test_channel_catalog.py
    └── test_futbolenlatv.py
```

## Publicar en un repositorio nuevo sin tocar Agenda

1. En GitHub, crea un repositorio nuevo llamado, por ejemplo, `Mi-TV`.
2. No reutilices ni cambies el repositorio `Agenda`.
3. Puedes mantener `Mi-TV` privado. Ten en cuenta la cuota de GitHub Actions indicada más abajo.
4. Sube **todo el contenido** de esta carpeta a la raíz del repositorio nuevo. Conserva las carpetas y rutas exactamente como aparecen arriba. Es importante incluir `.github/workflows/update_mi_tv.yml` y la carpeta `docs`.
5. Comprueba que la rama principal se llame `main` (o adapta la rama predeterminada en GitHub Pages si eliges otro nombre).
6. En el repositorio nuevo, abre **Settings → Pages**.
7. En **Build and deployment**, selecciona **Deploy from a branch**.
8. En **Branch**, selecciona `main` y la carpeta `/docs`; guarda los cambios.
9. Abre **Actions → Actualizar datos de Mi TV** y ejecuta **Run workflow** para hacer la primera actualización manual.
10. Cuando termine, espera a que Pages publique la web. La dirección aparecerá en **Settings → Pages**.

No cambies la configuración de Pages ni los workflows del repositorio `Agenda`. Todos los pasos anteriores se hacen exclusivamente en el repositorio nuevo.

## Actualización automática

El workflow `update_mi_tv.yml` está configurado para ejecutarse cada cinco minutos y también permite ejecución manual. Hace lo siguiente:

- Instala las dependencias Python.
- Consulta los canales y eventos deportivos de CDN Live TV.
- Ejecuta el parser personalizado de Futbolenlatv.
- Filtra los eventos de fútbol y NBA de CDN con el mismo clasificador de competiciones que utiliza `agenda_futbolenlatv.py`; las competiciones no admitidas se descartan antes de publicar el JSON. NHL y NFL se conservan como excepción solo en «Todos» (no tienen pestaña deportiva propia).
- Guarda los resultados en `docs/data/`.
- Hace commit únicamente si los JSON han cambiado.

Cada fuente se actualiza de forma independiente. Si una fuente falla temporalmente, se conserva el último JSON válido de esa fuente y se siguen procesando las demás.

GitHub Pages publica automáticamente los cambios de `docs/` mediante **Deploy from a branch**. No hace falta crear un workflow de Pages adicional.

### Importante: cuota de GitHub Actions

Un workflow cada cinco minutos equivale aproximadamente a 8.640 ejecuciones en un mes de 30 días. En repositorios privados, GitHub Free incluye 2.000 minutos mensuales de Actions y los minutos usados por las ejecuciones privadas cuentan para esa cuota. Si cada ejecución consume alrededor de un minuto facturable, el ritmo de cinco minutos superaría esa asignación. En repositorios públicos, los runners estándar de GitHub Actions son gratuitos, pero el código del repositorio queda visible para cualquiera.

Antes de dejarlo funcionando continuamente, decide la visibilidad del repositorio y revisa **Settings → Billing and licensing → Usage**. Si quieres mantenerlo privado y no consumir minutos adicionales, habrá que reducir la frecuencia (por ejemplo, cada 30 minutos) o estudiar otra forma de ejecutar la actualización. GitHub puede retrasar las ejecuciones programadas; el cron no garantiza que empiecen exactamente al minuto previsto.

## Catálogo de canales y comprobación del reproductor

- La vista Televisión solo muestra canales que CDN Live TV marca como `online`, que incluyen una URL HTTPS con el formato de su reproductor oficial y cuya página de reproductor responde con HTTP 200 y contenido HTML.
- La comprobación se ejecuta en GitHub Actions durante cada actualización. Las comprobaciones correctas se reutilizan durante 6 horas; los fallos se vuelven a comprobar cada hora. Así la agenda y el estado del catálogo se refrescan cada cinco minutos sin consultar cientos de páginas de reproductor en cada ejecución.
- Las tarjetas se ordenan alfabéticamente. Se ha eliminado el filtro de países y el filtro de estado. El buscador de Televisión busca exclusivamente por nombre del canal.
- Al pulsar en cualquier parte de una tarjeta se abre el reproductor oficial dentro de Mi TV. El botón de favorito sigue siendo independiente.
- El catálogo no afirma que el vídeo vaya a reproducirse en todos los navegadores, dispositivos o regiones. HTTP 200 confirma que la página del reproductor responde, pero no verifica que el vídeo cargue ni que esté disponible desde España. La documentación de CDN Live TV muestra su URL de reproductor y el uso de iframe; la autorización de distribución de cada canal debe confirmarse con el proveedor correspondiente.

## Favoritos y reproducción

- Los favoritos personales se guardan en el navegador mediante `localStorage`; no se escriben en los JSON públicos.
- `channel_catalog.py` solo acepta URLs HTTPS del dominio y ruta oficiales de reproductor publicados por CDN Live TV. No extrae enlaces de vídeo ni intenta obtener fuentes ocultas.
- No se intentan eludir geobloqueos, DRM, autenticación ni restricciones de acceso. Si el proveedor no ofrece una página oficial de reproductor accesible, el canal no se publica en el catálogo.
- `config/channels.json` y `docs/data/playback.json` se conservan por compatibilidad, pero ya no controlan la lista visible.

## Pruebas locales opcionales

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -s tests
py update_data.py
py server.py
```

Después abre `http://127.0.0.1:8000`. El servidor local sirve la misma carpeta `docs/` que se publica en Pages.
