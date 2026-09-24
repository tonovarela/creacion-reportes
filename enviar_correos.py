"""Manda a cada vendedor la liga de su reporte semanal, tomada del archivo de ligas que genera gen.py
(<SALIDA>/ligas-<semana>.csv). El archivo es obligatorio y la semana sale de su nombre.
Por seguridad, sin --prueba ni --enviar no se manda nada: solo se escriben vistas previas.

Uso:
  python enviar_correos.py salida/ligas-2026-W38.csv                          # vistas previas en <SALIDA>/correos-<semana>/, no envía
  python enviar_correos.py salida/ligas-2026-W38.csv --prueba yo@dominio.com  # manda TODOS los correos a esa cuenta, nadie más los recibe
  python enviar_correos.py salida/ligas-2026-W38.csv --enviar                 # envío real a los correos del CSV

En envío real se lleva un registro en <SALIDA>/envios-<semana>.csv: si se vuelve a correr, a quien ya
se le mandó no se le repite (útil si el envío se corta a medias).

Cada correo real va con copia oculta a la lista CORREO_CCO del .env (correos separados por coma); sin ella
--enviar no manda nada. En --prueba no se copia a nadie.
"""
import os, re, sys, csv, time, argparse, datetime, smtplib, unicodedata
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from string import Template
from entorno import cargar_env
cargar_env()

BASE=os.path.dirname(os.path.abspath(__file__))
SAL=os.environ.get('SALIDA') or os.path.join(BASE,'salida')
# versión para fondo claro: en la plantilla va sobre un recuadro blanco dentro de la franja azul
LOGO_URL=os.environ.get('LOGO_URL') or 'https://servicios.litoprocess.com/static/assets/img/lito-light.png'
MESES=['','ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']

def leer_ligas(ruta):
    # la semana sale del nombre que le pone gen.py: ligas-2026-W38.csv
    if not os.path.isfile(ruta): raise SystemExit(f'No existe el archivo de ligas {ruta}: corre primero gen.py.')
    m=re.match(r'^ligas-(\d{4}-W\d{1,2})\.csv$',os.path.basename(ruta),flags=re.I)
    if not m: raise SystemExit(f'{os.path.basename(ruta)}: el archivo de ligas debe llamarse ligas-<año>-W<semana>.csv, p. ej. ligas-2026-W38.csv')
    filas=list(csv.DictReader(open(ruta,encoding='utf-8')))
    faltan={'vendedor','correo','liga'}-set(filas[0].keys() if filas else ())
    if faltan: raise SystemExit(f'{ruta}: faltan las columnas {", ".join(sorted(faltan))} (o el archivo está vacío).')
    return m.group(1).upper(),filas

def rango(sem):
    a,s=map(int,re.match(r'^(\d{4})-W(\d{1,2})$',sem).groups())
    ini=datetime.date.fromisocalendar(a,s,1); fin=datetime.date.fromisocalendar(a,s,7)
    if ini.month==fin.month: return f'{ini.day}–{fin.day} {MESES[fin.month]} {fin.year}'
    return f'{ini.day} {MESES[ini.month]} – {fin.day} {MESES[fin.month]} {fin.year}'

def slug(s):
    s=''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
    return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')

def lista_cco():
    # CORREO_CCO del .env: correos separados por coma o punto y coma; van en copia oculta en el envío real
    v=[c.strip() for c in re.split(r'[,;]',os.environ.get('CORREO_CCO') or '') if c.strip()]
    malos=[c for c in v if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$',c)]
    if malos: raise SystemExit('CORREO_CCO trae correos no válidos: '+', '.join(malos))
    return v

def armar(fila,sem,remitente,prueba,cco=()):
    es_dir=fila['vendedor'].startswith('Dirección')
    nombre='equipo de Dirección' if es_dir else fila['vendedor'].split()[0]
    num=str(int(sem.split('-W')[1])); rg=rango(sem)
    intro=(f'Ya está disponible la vista general de la semana {num} ({rg}), con los indicadores de toda la empresa y el detalle por vendedor.'
           if es_dir else
           f'Ya está disponible tu reporte de la semana {num} ({rg}). Incluye tu facturación contra presupuesto, pedidos, oportunidades, actividades, entregas y cartera.')
    aviso=(f'<div style="background:#fff3cd;color:#664d03;padding:10px 16px;font-size:13px;font-family:Arial,sans-serif;">'
           f'PRUEBA — en el envío real este correo iría a <b>{fila["correo"] or "(sin correo)"}</b> ({fila["vendedor"]})'
           +(f', con copia oculta a {len(cco)} contacto(s) de CORREO_CCO' if cco else '')+'.</div>') if prueba else ''
    v=dict(nombre=nombre,num_semana=num,rango=rg,liga=fila['liga'],intro=intro,aviso_prueba=aviso,logo_url=LOGO_URL)
    html=Template(open(os.path.join(BASE,'plantillas','plantilla_correo.html'),encoding='utf-8').read()).substitute(v)
    texto=(f'Hola {nombre},\n\n{intro}\n\nVer el reporte: {fila["liga"]}\n\n'
           'La liga es personal: no la reenvíes. Cambia cada semana.\n')
    if prueba: texto=f'[PRUEBA — iría a {fila["correo"] or "(sin correo)"}]\n\n'+texto
    msg=EmailMessage()
    msg['Subject']=('[PRUEBA] ' if prueba else '')+f'Reporte semanal · Semana {num} ({rg})'
    msg['From']=formataddr((os.environ.get('CORREO_NOMBRE') or 'Reportes Litoprocess',remitente))
    msg['To']=prueba or fila['correo']
    # en prueba no se copia a nadie: el correo solo debe llegar a la cuenta de prueba.
    # send_message quita el encabezado Bcc antes de transmitir, así que los destinatarios no ven la lista
    if cco and not prueba: msg['Bcc']=', '.join(cco)
    if os.environ.get('CORREO_RESPONDER_A'): msg['Reply-To']=os.environ['CORREO_RESPONDER_A']
    msg['Message-ID']=make_msgid(domain=remitente.split('@')[-1])
    msg.set_content(texto); msg.add_alternative(html,subtype='html')
    return msg,html

# fallas de red pasajeras (p. ej. «The handshake operation timed out» en el STARTTLS): se reintentan
TRANSITORIOS=(OSError,smtplib.SMTPServerDisconnected,smtplib.SMTPConnectError)

def conectar():
    faltan=[k for k in ('SMTP_SERVIDOR','SMTP_USUARIO','SMTP_CONTRASENA') if not os.environ.get(k)]
    if faltan: raise SystemExit('Faltan en el .env o el entorno: '+', '.join(faltan))
    srv=os.environ['SMTP_SERVIDOR']; puerto=int(os.environ.get('SMTP_PUERTO') or 587)
    intentos=int(os.environ.get('SMTP_REINTENTOS') or 3)
    for i in range(1,intentos+1):
        s=None
        try:
            # 465 es SSL desde el inicio; 587 (el de siempre) abre en claro y sube a TLS con STARTTLS
            if puerto==465: s=smtplib.SMTP_SSL(srv,puerto,timeout=30)
            else: s=smtplib.SMTP(srv,puerto,timeout=30); s.starttls()
            s.login(os.environ['SMTP_USUARIO'],os.environ['SMTP_CONTRASENA'])
            return s
        except smtplib.SMTPAuthenticationError as e:
            raise SystemExit('El servidor rechazó usuario/contraseña. En Google Workspace se necesita una contraseña de aplicación '
                             '(Cuenta de Google → Seguridad → Contraseñas de aplicaciones).\n'+e.smtp_error.decode(errors='replace'))
        except TRANSITORIOS as e:
            if s:
                try: s.close()
                except Exception: pass
            if i==intentos:
                raise SystemExit(f'No se pudo conectar a {srv}:{puerto} después de {intentos} intentos: {e}\n'
                                 'Suele ser la red: revisa la conexión, la VPN o el firewall/antivirus. '
                                 'Si la red bloquea el 587, prueba con SMTP_PUERTO=465 en el .env.')
            espera=5*i
            print(f'  [aviso] falló la conexión a {srv}:{puerto} ({e}); reintento {i+1}/{intentos} en {espera}s…',flush=True)
            time.sleep(espera)

def main(args):
    ap=argparse.ArgumentParser(prog='enviar_correos.py',description='Manda a cada vendedor la liga de su reporte semanal.')
    ap.add_argument('ligas',help='archivo de ligas que genera gen.py, p. ej. salida/ligas-2026-W38.csv')
    modo=ap.add_mutually_exclusive_group()
    modo.add_argument('--prueba',nargs='?',const='',metavar='CORREO',
                      help='manda todos los correos a esta cuenta (o a CORREO_PRUEBA del .env)')
    modo.add_argument('--enviar',action='store_true',help='envío real a los correos del archivo')
    a=ap.parse_args(args)
    prueba=None if a.prueba is None else (a.prueba or os.environ.get('CORREO_PRUEBA'))
    if a.prueba is not None and (not prueba or '@' not in prueba):
        ap.error('--prueba necesita un correo: --prueba yo@dominio.com (o CORREO_PRUEBA en el .env)')
    real=a.enviar
    ruta=a.ligas
    sem,filas=leer_ligas(ruta)
    remitente=os.environ.get('CORREO_REMITENTE') or os.environ.get('SMTP_USUARIO') or 'reportes@litoprocess.com'
    cco=lista_cco()
    if real and not cco:
        raise SystemExit('Falta CORREO_CCO en el .env: la lista de correos que va en copia oculta, separados por coma. No se envió nada.')
    print(f'Ligas: {ruta}  ({len(filas)} renglones, semana {sem})')
    print('Copia oculta: '+(', '.join(cco) if cco else '(falta CORREO_CCO en el .env; el envío real no correrá sin ella)')
          +(' — no se usa en --prueba' if prueba and cco else ''))

    registro=os.path.join(SAL,f'envios-{sem}.csv')
    ya=set()
    if real and os.path.exists(registro):
        ya={r['correo'] for r in csv.DictReader(open(registro,encoding='utf-8')) if r['estado']=='enviado'}

    if not (prueba or real):
        carpeta=os.path.join(SAL,f'correos-{sem}'); os.makedirs(carpeta,exist_ok=True)
        for f in filas:
            _,html=armar(f,sem,remitente,None)
            open(os.path.join(carpeta,slug(f['vendedor'])+'.html'),'w',encoding='utf-8').write(html)
            print(f'  {f["vendedor"]:<28} {f["correo"] or "(sin correo: no se enviaría)"}')
        print(f'\nVistas previas en {carpeta}. No se envió nada: usa --prueba <correo> o --enviar.')
        return

    smtp=conectar(); env=0; omit=0; err=0
    nuevo=not os.path.exists(registro)
    log=open(registro,'a',newline='',encoding='utf-8') if real else None
    w=csv.writer(log) if log else None
    if w and nuevo: w.writerow(['fecha','vendedor','correo','estado','detalle'])
    try:
        for f in filas:
            dest=prueba or f['correo']
            if not f['correo'] and not prueba:
                print(f'  [omitido] {f["vendedor"]}: sin correo'); omit+=1; continue
            if real and f['correo'] in ya:
                print(f'  [ya enviado] {f["vendedor"]} <{f["correo"]}>'); omit+=1; continue
            msg,_=armar(f,sem,remitente,prueba,cco)
            try:
                try: smtp.send_message(msg)
                except TRANSITORIOS as e:
                    # se cayó la conexión a media corrida: reconectar y reintentar este mismo correo una vez
                    print(f'  [aviso] se perdió la conexión ({e}); reconectando…',flush=True)
                    try: smtp.close()
                    except Exception: pass
                    smtp=conectar(); smtp.send_message(msg)
                env+=1
                print(f'  enviado  {f["vendedor"]:<28} → {dest}')
                if w: w.writerow([datetime.datetime.now().isoformat(timespec='seconds'),f['vendedor'],f['correo'],'enviado',''])
            except (smtplib.SMTPException,OSError) as e:
                err+=1; print(f'  [ERROR] {f["vendedor"]} <{dest}>: {e}')
                if w: w.writerow([datetime.datetime.now().isoformat(timespec='seconds'),f['vendedor'],f['correo'],'error',str(e)])
            if log: log.flush()
            time.sleep(float(os.environ.get('CORREO_PAUSA') or 1))  # no saturar el límite por minuto de Gmail
    finally:
        try: smtp.quit()
        except Exception: pass   # si la conexión ya estaba caída, no tapar el error real
        if log: log.close()
    print(f'\nEnviados: {env} · omitidos: {omit} · errores: {err}' + (f'  (registro: {registro})' if real else f'  (todo a {prueba})'))
    if err: sys.exit(1)

if __name__=='__main__':
    main(sys.argv[1:])
