"""Historial de semanas armado con los archivos que ya dejan los scripts:
  <ENTRADA>/<sem>.xlsx · <SALIDA>/ligas-<sem>.csv · <SALIDA>/avisos-<sem>.json · <SALIDA>/envios-<sem>.csv

El Excel lleva la semana a 2 dígitos (2026-W05) y los archivos de gen.py la llevan tal cual viene de
semana_iso (2026-W5): todo se agrupa por la forma de 2 dígitos.
"""
import os, re, csv, glob, json
from . import config
import enviar_correos, orquestador

RE_SEM=re.compile(r'^(\d{4})-W(\d{1,2})$',re.I)

def clave(sem):
    m=RE_SEM.match(sem or '')
    return f'{m.group(1)}-W{int(m.group(2)):02d}' if m else None

def _archivos():
    ent,sal=config.entrada(),config.salida()
    por={}
    def add(sem,tipo,ruta):
        k=clave(sem)
        if k: por.setdefault(k,{})[tipo]=ruta
    for f in glob.glob(os.path.join(ent,'*.xlsx')):
        add(os.path.splitext(os.path.basename(f))[0],'excel',f)
    for tipo,patron in (('ligas','ligas-*.csv'),('avisos','avisos-*.json'),('envios','envios-*.csv')):
        for f in glob.glob(os.path.join(sal,patron)):
            add(re.sub(r'^[a-z]+-|\.[a-z]+$','',os.path.basename(f)),tipo,f)
    return por

def _leer_csv(f):
    return list(csv.DictReader(open(f,encoding='utf-8'))) if f and os.path.isfile(f) else []

def _avisos(f):
    try: return json.load(open(f,encoding='utf-8')) if f and os.path.isfile(f) else []
    except ValueError: return []

def _enviados(envios):
    return {r['correo'] for r in envios if r.get('estado')=='enviado'}

def liga_local(liga):
    # la liga del CSV apunta a BASE_URL; esta app sirve lo mismo en reportes/<año>/<semana>/<token>/
    m=re.search(r'/(\d{4})/(\d{1,2})/([0-9a-f]{32})/?$',liga or '')
    return f'reportes/{m.group(1)}/{m.group(2)}/{m.group(3)}/' if m else None   # relativa: funciona bajo cualquier prefijo del proxy

def listar():
    out=[]
    for k,a in _archivos().items():
        ligas=_leer_csv(a.get('ligas')); av=_avisos(a.get('avisos')); env=_leer_csv(a.get('envios'))
        con_correo={r['correo'] for r in ligas if r.get('correo')}
        out.append({'semana':k,'excel':os.path.basename(a['excel']) if 'excel' in a else None,
                    'generada':'ligas' in a,'destinatarios':len(ligas),
                    'avisos':len(av),'criticos':sum(1 for x in av if x.get('nivel')=='critico'),
                    'enviados':len(_enviados(env)&con_correo),'con_correo':len(con_correo)})
    return sorted(out,key=lambda s:s['semana'],reverse=True)

def archivos(sem):
    k=clave(sem)
    return k,(_archivos().get(k) if k else None)

def detalle(sem):
    k,a=archivos(sem)
    if not a: return None
    ligas=_leer_csv(a.get('ligas')); env=_leer_csv(a.get('envios')); ya=_enviados(env)
    return {'semana':k,'excel':os.path.basename(a['excel']) if 'excel' in a else None,
            'avisos':_avisos(a.get('avisos')),
            'ligas':[{'vendedor':r['vendedor'],'correo':r.get('correo',''),'liga':r['liga'],
                      'local':liga_local(r['liga']),'slug':enviar_correos.slug(r['vendedor']),
                      'enviado':bool(r.get('correo')) and r['correo'] in ya} for r in ligas],
            'envios':env}

def criticos(sem):
    # misma revisión que hace orquestador.py antes de un envío real
    k,a=archivos(sem)
    if not a or 'avisos' not in a: return []
    sem_archivo=re.sub(r'^avisos-|\.json$','',os.path.basename(a['avisos']))
    return orquestador.criticos(config.salida(),sem_archivo)

def vista_correo(sem,slug):
    k,a=archivos(sem)
    if not a or 'ligas' not in a: return None
    s,filas=enviar_correos.leer_ligas(a['ligas'])
    fila=next((f for f in filas if enviar_correos.slug(f['vendedor'])==slug),None)
    if not fila: return None
    remitente=os.environ.get('CORREO_REMITENTE') or os.environ.get('SMTP_USUARIO') or 'reportes@litoprocess.com'
    try: cco=enviar_correos.lista_cco()
    except SystemExit: cco=[]
    return enviar_correos.armar(fila,s,remitente,None,cco)[1]
