FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    SALIDA=/data/salida \
    TZ=America/Mexico_City

WORKDIR /app
COPY requirements.txt requirements-web.txt ./
RUN pip install -r requirements.txt -r requirements-web.txt

COPY gen.py entorno.py extraer_excel.py enviar_correos.py orquestador.py ./
COPY plantillas/ ./plantillas/
# consultas por defecto; se pueden reemplazar montando otra carpeta en /app/sql
COPY sql/ ./sql/
# panel web (FastAPI); el CSS ya va compilado en web/static/app.css
COPY web/ ./web/

# Usuario sin privilegios; en Linux se puede sobreescribir con --user $(id -u):$(id -g)
RUN useradd --uid 1000 --create-home app \
 && mkdir -p /data/entrada /data/salida \
 && chown -R app:app /data
USER app

# entrada: los .xlsx semanales (extraer_excel.py escribe aquí; gen.py lee de aquí)
# salida:  reportes, avisos, ligas y public/<año>/<semana>/
VOLUME ["/data/entrada", "/data/salida"]

ENTRYPOINT ["python", "/app/gen.py"]
# Por defecto genera los reportes con el .xlsx más reciente de la carpeta de entrada;
# para sacar el Excel de SQL Server: --entrypoint python … /app/extraer_excel.py
# se puede pasar un archivo concreto: docker run ... /data/entrada/2026-W38.xlsx
# panel web: --entrypoint uvicorn … web.app.main:app --host 0.0.0.0 --port 8000 (ver servicio «web» en docker-compose.yml)
CMD ["/data/entrada"]
