FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    SALIDA=/data/salida

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY gen.py entorno.py extraer_excel.py ./
COPY plantillas/ ./plantillas/
# consultas por defecto; se pueden reemplazar montando otra carpeta en /app/sql
COPY sql/ ./sql/

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
CMD ["/data/entrada"]
