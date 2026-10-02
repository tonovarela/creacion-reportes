#!/bin/sh
# Corre el proceso semanal completo (extracción → reportes → correos) dentro del contenedor «web» que ya está
# levantado, para usarse desde cron. Va en la misma carpeta que docker-compose.yml y el .env del servidor.
#
# Uso:
#   ./correr-semanal.sh             # modo prueba: todos los correos a CORREO_PRUEBA del .env (con CCO a CORREO_CCO)
#   ./correr-semanal.sh --enviar    # envío real (se frena solo si gen.py deja avisos críticos)
#   (cualquier otro argumento se le pasa tal cual a orquestador.py)
#
# Crontab (crontab -e del usuario que puede usar docker), p. ej. lunes 07:00 hora del servidor:
#   0 7 * * 1 /ruta/a/reportes/correr-semanal.sh
#
# Cada corrida deja su log en logs/AAAAMMDD-HHMMSS.log; los de más de 90 días se borran solos.
set -u
# cron trae un PATH mínimo: sin esto puede no encontrar docker
PATH=/usr/local/bin:/usr/bin:/bin:$PATH
cd "$(dirname "$0")" || exit 1

[ $# -eq 0 ] && set -- --prueba

# logs en una carpeta del host: salida/ es del uid 1000 del contenedor
mkdir -p logs
find logs -name '*.log' -mtime +90 -delete 2>/dev/null
log="logs/$(date +%Y%m%d-%H%M%S).log"

# que dos corridas no se encimen (p. ej. una manual y la del cron)
exec 9>logs/.lock
if ! flock -n 9; then
    echo "$(date '+%F %T') ya hay una corrida en curso; no se lanzó otra" | tee "$log" >&2
    exit 1
fi

# subshell y no { }: su exit no debe terminar el script antes de reportar el código
(
    echo "=== $(date '+%F %T') inicio · orquestador.py $*"
    if [ -z "$(docker compose ps --status running -q web)" ]; then
        echo "El contenedor «web» no está corriendo: levántalo con «docker compose up -d» y vuelve a intentar."
        exit 1
    fi
    # -T porque cron no tiene TTY; usa el entorno y los volúmenes del mismo contenedor que el panel
    docker compose exec -T web python /app/orquestador.py "$@"
    cod=$?
    echo "=== $(date '+%F %T') fin · código $cod"
    exit $cod
) >"$log" 2>&1
cod=$?
# si falló, que cron lo reporte (llega por correo si el host tiene MAILTO)
[ $cod -ne 0 ] && echo "Falló el proceso semanal (código $cod); ver $(pwd)/$log" >&2
exit $cod
