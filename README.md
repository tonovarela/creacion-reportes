# Reportes semanales de ventas

Genera los reportes HTML por vendedor y la vista de dirección a partir del Excel semanal.

## Carpetas

| Carpeta en el host | En el contenedor  | Contenido |
|--------------------|-------------------|-----------|
| `entrada/`         | `/data/entrada`   | Los `.xlsx` semanales. Se toma el más reciente (orden alfabético). |
| `salida/`          | `/data/salida`    | Reportes con fecha, `avisos-*.json`, `ligas-*.csv` y `publicar-<semana>/` (p. ej. `publicar-2026-W38/`, lo único que se sube al hosting). |
| `estado/`          | `/data/estado`    | `estado.json` con los tokens de las ligas fijas. **Respaldarlo: si se pierde, cambian todas las ligas.** |

## Uso sin Docker

La primera vez (o en otra máquina):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
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
- Fijar siempre `ESTADO`: sin ella se busca `estado.json` junto al Excel, y si no lo encuentra genera tokens nuevos y cambian todas las ligas.

## Uso con docker compose

```bash
mkdir -p entrada salida estado
cp estado.json estado/            # solo la primera vez, para conservar los tokens actuales
cp 2026-W39.xlsx entrada/
BASE_URL=https://tu-dominio.com/reportes docker compose run --rm reportes
```

Para un archivo específico en lugar del más reciente:

```bash
docker compose run --rm reportes /data/entrada/2026-W39.xlsx
```

## Uso con docker run

```bash
docker run --rm \
  -v "$PWD/entrada:/data/entrada:ro" \
  -v "$PWD/salida:/data/salida" \
  -v "$PWD/estado:/data/estado" \
  -e BASE_URL=https://tu-dominio.com/reportes \
  -e DIRECCION_CORREO=direccion@litoprocess.com \
  TU_USUARIO/reportes-ventas:latest
```

En Linux, si los archivos de salida quedan con otro dueño, agregar `--user "$(id -u):$(id -g)"`.

## Variables de entorno

Dentro del contenedor las rutas ya están fijas; `docker compose` toma `BASE_URL` y `DIRECCION_CORREO`
del mismo `.env` (el `.env` no se copia a la imagen).

| Variable           | Default (Docker)            | Uso |
|--------------------|-----------------------------|-----|
| `ENTRADA`          | `/data/entrada`             | Archivo `.xlsx` o carpeta de entrada. |
| `BASE_URL`         | vacío                       | Dominio donde se publican las ligas `r-<token>.html`. |
| `DIRECCION_CORREO` | vacío                       | Correo para la liga de dirección en `ligas-*.csv`. |
| `SALIDA`           | `/data/salida`              | Carpeta de salida. |
| `ESTADO`           | `/data/estado/estado.json`  | Ruta del archivo de estado. |

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
