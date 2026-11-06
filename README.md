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
│       └── playback.json
├── agenda_futbolenlatv.py
├── server.py                # Solo para pruebas locales
├── update_data.py           # Genera los JSON estáticos
├── requirements.txt
└── tests/
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
- Guarda los resultados en `docs/data/`.
- Hace commit únicamente si los JSON han cambiado.

Cada fuente se actualiza de forma independiente. Si una fuente falla temporalmente, se conserva el último JSON válido de esa fuente y se siguen procesando las demás.

GitHub Pages publica automáticamente los cambios de `docs/` mediante **Deploy from a branch**. No hace falta crear un workflow de Pages adicional.

### Importante: cuota de GitHub Actions

Un workflow cada cinco minutos equivale aproximadamente a 8.640 ejecuciones en un mes de 30 días. En repositorios privados, GitHub Free incluye 2.000 minutos mensuales de Actions y los minutos usados por las ejecuciones privadas cuentan para esa cuota. Si cada ejecución consume alrededor de un minuto facturable, el ritmo de cinco minutos superaría esa asignación. En repositorios públicos, los runners estándar de GitHub Actions son gratuitos, pero el código del repositorio queda visible para cualquiera.

Antes de dejarlo funcionando continuamente, decide la visibilidad del repositorio y revisa **Settings → Billing and licensing → Usage**. Si quieres mantenerlo privado y no consumir minutos adicionales, habrá que reducir la frecuencia (por ejemplo, cada 30 minutos) o estudiar otra forma de ejecutar la actualización. GitHub puede retrasar las ejecuciones programadas; el cron no garantiza que empiecen exactamente al minuto previsto.

## Catálogo de canales

Los canales se muestran en orden alfabético por nombre, también cuando se aplica un filtro o se ven los favoritos. El filtro de país utiliza los códigos que entrega CDN Live TV. Si la fuente agrupa muchos canales como `Otros` o no proporciona un país, Mi TV no inventa nacionalidades: para desglosarlos hará falta otra fuente de metadatos verificable.

## Favoritos y reproducción

- Los favoritos personales se guardan en el navegador mediante `localStorage`; no se escriben en los JSON públicos.
- La reproducción sigue deshabilitada salvo que se configure una fuente HTTPS y exista autorización expresa para insertarla en una web.
- `config/channels.json` contiene la configuración manual. `update_data.py` la publica como `docs/data/playback.json`.

No se intentan eludir geobloqueos, DRM, autenticación ni restricciones de acceso. La presencia de un canal en el catálogo no demuestra que su emisión esté autorizada o disponible en España.

## Pruebas locales opcionales

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -s tests
py update_data.py
py server.py
```

Después abre `http://127.0.0.1:8000`. El servidor local sirve la misma carpeta `docs/` que se publica en Pages.
