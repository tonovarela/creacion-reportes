# Reportes semanales de ventas

Genera los reportes HTML por vendedor y la vista de dirección a partir del Excel semanal.

Son dos pasos:

1. `extraer_excel.py` ejecuta las consultas de `sql/` contra SQL Server y arma `<ENTRADA>/<año>-W<semana>.xlsx`.
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
.venv/bin/python extraer_excel.py              # escribe <ENTRADA>/<año>-W<semana>.xlsx
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

## Publicar en Docker Hub

```bash
docker login
# imagen para Intel y Apple Silicon a la vez
docker buildx build --platform linux/amd64,linux/arm64 \
  -t TU_USUARIO/reportes-ventas:1.0.0 \
  -t TU_USUARIO/reportes-ventas:latest \
  --push .
```

Reemplazar `TU_USUARIO` también en `docker-compose.yml`.
