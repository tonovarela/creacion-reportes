# Reportes semanales de ventas

Genera los reportes HTML por vendedor y la vista de dirección a partir del Excel semanal.

Son dos pasos:

1. `extraer_excel.py` ejecuta las consultas de `sql/` contra SQL Server y arma `<ENTRADA>/<semana_iso>.xlsx` (semana_iso sale de la hoja Encabezado).
2. `gen.py` toma ese Excel y genera los reportes.

## Carpetas

| Carpeta en el host | En el contenedor  | Contenido |
|--------------------|-------------------|-----------|
| `entrada/`         | `/data/entrada`   | Los `.xlsx` semanales. Se toma el más reciente (orden alfabético). |
| `salida/`          | `/data/salida`    | `reportes/<año>/<semana>/reporte-<vendedor>.html` (uso interno), `avisos-*.json`, `ligas-*.csv` y `public/<año>/<semana>/<token>/index.html` (p. ej. `public/2026/38/`, lo único que se sube al hosting). |

## Uso sin Docker

La primera vez (o en otra máquina):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
python3 -c "import secrets;print(secrets.token_hex(32))"   # pegar el resultado en TOKEN_SECRETO del .env
```

La configuración vive en `.env` (copiar de `.env.example`). `gen.py` lo lee solo al arrancar;
las rutas relativas se resuelven contra la carpeta del proyecto, así que da igual desde dónde se ejecute.

Cada semana:

```bash
.venv/bin/python gen.py                       # usa ENTRADA del .env
.venv/bin/python gen.py entrada/2026-W39.xlsx  # o un archivo específico
BASE_URL=https://otro.com .venv/bin/python gen.py  # lo de la línea de comandos gana sobre el .env
```

- `ENTRADA` puede ser un archivo o una carpeta (se toma el `.xlsx` más reciente).
- `SALIDA` es obligatoria: sin ella intenta escribir en `/mnt/user-data/outputs`.

## Sacar el Excel de SQL Server

```bash
.venv/bin/python extraer_excel.py --listar     # revisa sql/ sin conectarse: orden y nombre de cada hoja
.venv/bin/python extraer_excel.py              # escribe <ENTRADA>/<semana_iso>.xlsx
.venv/bin/python extraer_excel.py otro.xlsx    # o a un archivo específico
```

Reglas para los archivos de `sql/`:

- El nombre empieza con el número de orden: `01-encabezados.sql`, `02-presupuestos.sql`… Ese número da el orden de las hojas.
- La primera línea con texto es el nombre de la hoja como comentario: `-- Encabezado`. Máximo 31 caracteres, sin `[]:*?/\`.
- Cada archivo debe devolver un solo `SELECT`. Se pueden usar `DECLARE` y separadores `GO`.
- Los nombres de hoja y de columna tienen que ser los que espera `gen.py`.

La semana del nombre del archivo sale de la columna `semana_iso` de la hoja Encabezado, con 2 dígitos (`2026-W05`).
El Excel se escribe primero como archivo oculto y se renombra al final, así que si una consulta falla no queda un Excel a medias.

## Uso con docker compose

```bash
mkdir -p entrada salida
cp 2026-W39.xlsx entrada/
BASE_URL=https://tu-dominio.com/reportes docker compose run --rm reportes
```

Para un archivo específico en lugar del más reciente:

```bash
docker compose run --rm reportes /data/entrada/2026-W39.xlsx
```

Para sacar el Excel de SQL Server con Docker (lo deja en `./entrada`):

```bash
docker compose run --rm extraer
docker compose run --rm reportes
```

Si SQL Server corre en la misma Mac que Docker, usar `SQL_SERVIDOR=host.docker.internal`.

## Uso con docker run

```bash
docker run --rm \
  -v "$PWD/entrada:/data/entrada:ro" \
  -v "$PWD/salida:/data/salida" \
  -e BASE_URL=https://tu-dominio.com/reportes \
  -e DIRECCION_CORREO=direccion@litoprocess.com \
  -e TOKEN_SECRETO=<la clave del .env> \
  TU_USUARIO/reportes-ventas:latest
```

En Linux, si los archivos de salida quedan con otro dueño, agregar `--user "$(id -u):$(id -g)"`.

## Variables de entorno

Dentro del contenedor las rutas ya están fijas; `docker compose` toma `BASE_URL`, `DIRECCION_CORREO` y `TOKEN_SECRETO`
del mismo `.env` (el `.env` no se copia a la imagen).

| Variable           | Default (Docker)            | Uso |
|--------------------|-----------------------------|-----|
| `ENTRADA`          | `/data/entrada`             | Archivo `.xlsx` o carpeta de entrada. |
| `BASE_URL`         | vacío                       | URL donde se sube el contenido de `public/`; las ligas quedan `BASE_URL/<año>/<semana>/<token>/`. |
| `DIRECCION_CORREO` | vacío                       | Correo para la liga de dirección en `ligas-*.csv`. |
| `TOKEN_SECRETO`    | **obligatoria**             | Clave para firmar los tokens. Mismo vendedor + misma semana = mismo token. Si cambia, cambian todas las ligas; no compartirla. |
| `SALIDA`           | `/data/salida`              | Carpeta de salida. |
| `FOLDER_SQL`       | `/app/sql`                  | Carpeta con las consultas `NN-nombre.sql`. |
| `SQL_SERVIDOR`     | —                           | Host o IP de SQL Server. |
| `SQL_PUERTO`       | `1433`                      | Puerto de SQL Server. |
| `SQL_BASE_DATOS`   | —                           | Base de datos por defecto (donde están `v_CatAgentes`, `v_Ventas`, etc.). |
| `SQL_USUARIO`      | —                           | Usuario de SQL Server (basta con permisos de lectura). |
| `SQL_CONTRASENA`   | —                           | Contraseña. Solo en `.env`, nunca en el repo. |
| `SQL_TIMEOUT`      | `600`                       | Segundos máximos por consulta. |

## Web

Panel para correr el proceso, revisar el historial de semanas y mandar los correos, más la publicación
de los reportes de los vendedores. Envuelve los mismos scripts: la línea de comandos sigue funcionando igual.

```bash
.venv/bin/pip install -r requirements-web.txt
.venv/bin/uvicorn web.app.main:app --host 0.0.0.0 --port 8000     # o: docker compose up web
```

- **Proceso**: proceso completo o un paso suelto (extracción, reportes, correos), con el log en vivo.
  Solo corre un trabajo a la vez; el historial y los logs quedan en `<SALIDA>/trabajos/`.
- **Semanas**: por semana, Excel (descarga), avisos, ligas de cada vendedor y registro de envíos.
- **Correos**: vista previa de cada correo, envío de prueba a una cuenta y envío real. El envío real pide
  escribir la semana para confirmar y se bloquea si hay avisos críticos, salvo que se marque «ignorar avisos».
- **Reportes**: `/reportes/<año>/<semana>/<token>/` sirve `<SALIDA>/public/`. Con
  `BASE_URL=https://<host>/reportes` las ligas de los correos apuntan a esta misma app.

**Acceso (no hay login).** El panel (`/` y `/api/*`) solo responde a las IPs de `ADMIN_REDES`; fuera de ellas
devuelve 404. `/reportes/…` es público: cada reporte vive en una carpeta con un token no adivinable y las
carpetas no se listan. `<SALIDA>/reportes/` (nombres legibles) nunca se publica.

| Variable       | Por defecto | Descripción |
|----------------|-------------|-------------|
| `ADMIN_REDES`  | `127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` | Redes que pueden usar el panel, separadas por coma. |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | (de uvicorn) IPs de proxies en los que se confía para tomar la IP real de `X-Forwarded-For`. |

Si la app queda expuesta a internet detrás de un proxy (nginx, Caddy…), pon la IP del proxy en
`FORWARDED_ALLOW_IPS`; si no, el panel vería a todos con la IP del proxy. **Con Docker Desktop (Mac/Windows)**
las conexiones que entran por el puerto publicado llegan con la IP interna de Docker (`172.x`), que está en
`ADMIN_REDES`: no publiques el puerto a internet sin un proxy delante.

El CSS se compila con Tailwind standalone (sin Node) y `web/static/app.css` se versiona ya compilado:

```bash
web/tailwind.sh           # compila (la primera vez descarga el binario a web/bin/)
web/tailwind.sh --watch   # recompila al editar web/cliente/
```

## Despliegue detrás de Apache (servidor Linux)

La imagen `tonovarela/reportes-ventas` (linux/amd64) se publica en Docker Hub. En el servidor solo hacen
falta `deploy/docker-compose.yml`, el `.env` y las carpetas de datos:

```bash
# /opt/reportes es solo un ejemplo: puede ser cualquier carpeta
mkdir -p /opt/reportes/entrada /opt/reportes/salida && cd /opt/reportes
# copiar aquí deploy/docker-compose.yml y el .env
sudo chown -R 1000:1000 entrada salida      # el contenedor corre con el uid 1000
docker compose pull && docker compose up -d
```

Apache publica la app en una subruta con `ProxyPass` (configuración lista en `deploy/apache-reportes.conf`,
se incluye dentro del `<VirtualHost>`):

| Pieza | Valor |
|---|---|
| Panel | `https://servicios.litoprocess.com/panel-reportes/` (solo red interna) |
| Reportes | `https://servicios.litoprocess.com/panel-reportes/reportes/<año>/<semana>/<token>/` (público) |
| `BASE_URL` en el `.env` | `https://servicios.litoprocess.com/panel-reportes/reportes` |
| Subruta | `ROOT_PATH` en el `.env` (por defecto `/panel-reportes`); debe coincidir con el `ProxyPass` |

Qué contempla la configuración para funcionar detrás del proxy:
- **Subruta**: uvicorn recibe el prefijo (`UVICORN_ROOT_PATH`) y el cliente usa rutas relativas;
  `/panel-reportes` sin barra final redirige a `/panel-reportes/`.
- **IP real del usuario**: el contenedor publica el puerto solo en `127.0.0.1` y confía en `X-Forwarded-For`
  únicamente cuando viene de Apache (la puerta de enlace `172.30.57.1` de la red fija del compose). Así el
  filtro `ADMIN_REDES` del panel funciona y un cliente no puede hacerse pasar por interno.
- **Doble candado al panel**: `Require ip` en Apache además del filtro de la app; `/reportes/` es público.
- **Log en vivo**: Apache no lo comprime (`no-gzip`) para que las líneas lleguen al momento.
- **Ligas ya enviadas**: si hoy `https://servicios.litoprocess.com/reportes/` es la carpeta donde se suben los
  reportes, las líneas opcionales del final de `apache-reportes.conf` la sirven desde el contenedor.

Para comprobar que la app ve la IP real: `docker compose logs web` debe mostrar la IP del usuario
(con puerto `:0`), no la de Apache.

### Proceso completo a mano (orquestador.py)

`orquestador.py` corre los tres pasos en orden (extracción → reportes → correos) y se detiene en el primero
que falle. Lo más sencillo es ejecutarlo dentro del contenedor `web` ya levantado, que tiene el `.env`
(SQL, SMTP, `CORREO_CCO`…) y los volúmenes `/data/entrada` y `/data/salida`. Desde la carpeta del
`docker-compose.yml`:

```bash
# solo vistas previas: extrae, genera y no manda ningún correo
docker compose exec web python /app/orquestador.py

# prueba: todos los correos a una cuenta (o a CORREO_PRUEBA del .env si se omite el correo)
docker compose exec web python /app/orquestador.py --prueba yo@litoprocess.com
docker compose exec web python /app/orquestador.py --prueba

# envío real a los vendedores (requiere CORREO_CCO en el .env)
docker compose exec web python /app/orquestador.py --enviar

# usar un Excel que ya existe y saltarse la extracción de SQL Server
docker compose exec web python /app/orquestador.py --excel /data/entrada/2026-W38.xlsx --enviar

# enviar aunque gen.py haya dejado avisos críticos (después de revisarlos)
docker compose exec web python /app/orquestador.py --excel /data/entrada/2026-W38.xlsx --enviar --ignorar-avisos
```

Si el contenedor `web` no está levantado, se puede lanzar uno temporal con la misma configuración:

```bash
docker compose run --rm --entrypoint python web /app/orquestador.py --prueba yo@litoprocess.com
```

| Parámetro | Qué hace |
|---|---|
| *(sin modo)* | Solo deja vistas previas de los correos; no se envía nada. |
| `--prueba [CORREO]` | Manda todos los correos a esa cuenta, o a `CORREO_PRUEBA` si no se indica. |
| `--enviar` | Envío real a los vendedores. No se combina con `--prueba`. |
| `--excel ARCHIVO` | Usa ese Excel y se salta la extracción. Es la ruta **dentro del contenedor**: `./entrada/2026-W38.xlsx` del host es `/data/entrada/2026-W38.xlsx`. |
| `--ignorar-avisos` | Con `--enviar`, envía aunque haya avisos críticos (cifras que no cuadran). |

Todos los correos, reales y de prueba, van con copia oculta a `CORREO_CCO`.

### Ejecución automática (cron)

`deploy/correr-semanal.sh` corre `orquestador.py` dentro del contenedor `web` que ya está levantado
(`docker compose exec -T`), con el mismo `.env` y los mismos volúmenes que el panel. Sin argumentos usa `--prueba`
(todos los correos a `CORREO_PRUEBA`, con copia oculta a `CORREO_CCO`); cualquier argumento se pasa tal cual
al orquestador (los mismos de la tabla anterior).

El script **tiene que vivir en la misma carpeta que el `docker-compose.yml` y el `.env`** del servidor: al arrancar
hace `cd` a su propia carpeta para que `docker compose` encuentre el proyecto. En los pasos siguientes,
`/ruta/a/reportes` es esa carpeta; si no se sabe dónde quedó, con el contenedor levantado:

```bash
docker compose ls                     # columna CONFIG FILES: ruta completa del docker-compose.yml
# o bien
docker inspect --format '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' \
  $(docker ps -q --filter label=com.docker.compose.service=web)
```

1. Copiar el script junto al `docker-compose.yml` y el `.env` del servidor y darle permisos de ejecución:

   ```bash
   cp deploy/correr-semanal.sh /ruta/a/reportes/ && chmod +x /ruta/a/reportes/correr-semanal.sh
   ```

2. Revisar el `.env`: `CORREO_PRUEBA=yo@litoprocess.com` para el modo prueba y `CORREO_CCO` para `--enviar`.

3. Probarlo a mano, con el entorno mínimo que tendrá cron:

   ```bash
   env -i HOME=$HOME /ruta/a/reportes/correr-semanal.sh; echo $?
   ls -t /ruta/a/reportes/logs | head -1     # log de esa corrida
   ```

4. Agregarlo al crontab de un usuario que pueda usar docker (está en el grupo `docker` o es root):

   ```bash
   crontab -e
   ```

   ```
   # correo al que cron manda la salida de error si algo falla (requiere un MTA en el host)
   MAILTO=sistemas@litoprocess.com

   # min hora día-mes mes día-semana  comando
   # lunes 07:00, modo prueba (correos a CORREO_PRUEBA)
   0 7 * * 1 /ruta/a/reportes/correr-semanal.sh

   # o bien envío real (se frena solo si hay avisos críticos)
   # 0 7 * * 1 /ruta/a/reportes/correr-semanal.sh --enviar
   ```

   Verificar que quedó con `crontab -l`. Otros horarios: `30 6 * * 1` (lunes 06:30), `0 7 * * 1-5` (lunes a viernes).

- Cada corrida deja su log en `/ruta/a/reportes/logs/AAAAMMDD-HHMMSS.log` (se borran a los 90 días); los reportes
  y las ligas quedan en `salida/` como siempre y se ven en la pestaña Semanas del panel.
- Si el contenedor no está arriba, o ya hay otra corrida del script en curso, no se ejecuta y sale con error
  (cron lo manda por correo si el host tiene `MAILTO`).
- Cron usa la zona horaria del servidor (`timedatectl`); el contenedor usa `America/Mexico_City`.
- La corrida del cron no aparece en el historial del panel ni respeta su candado de «un trabajo a la vez»:
  no lanzar un proceso desde el panel a esa misma hora.
- Para confirmar que cron lo lanzó: `grep CRON /var/log/syslog` (Debian/Ubuntu) o `journalctl -u cron`
  (`-u crond` en RHEL/Rocky).

## Publicar en Docker Hub

```bash
docker login
docker buildx build --platform linux/amd64 \
  -t tonovarela/reportes-ventas:1.0.0 \
  -t tonovarela/reportes-ventas:latest \
  --push .
```
