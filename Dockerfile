FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    SALIDA=/data/salida \
    ESTADO=/data/estado/estado.json

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY gen.py plantilla.html ./

# Usuario sin privilegios; en Linux se puede sobreescribir con --user $(id -u):$(id -g)
RUN useradd --uid 1000 --create-home app \
 && mkdir -p /data/entrada /data/salida /data/estado \
 && chown -R app:app /data
USER app

# entrada: los .xlsx semanales (solo lectura)
# salida:  reportes, avisos, ligas y la carpeta publicar/
# estado:  estado.json con los tokens de las ligas fijas — NO perderlo
VOLUME ["/data/entrada", "/data/salida", "/data/estado"]

ENTRYPOINT ["python", "/app/gen.py"]
# Por defecto toma el .xlsx más reciente de la carpeta de entrada;
# se puede pasar un archivo concreto: docker run ... /data/entrada/2026-W38.xlsx
CMD ["/data/entrada"]
