"""Ejecuta los scripts del proceso como subprocesos, uno a la vez, con el log disponible en vivo.

Cada trabajo deja en <SALIDA>/trabajos/ su log (<id>.log) y sus datos (<id>.json), así el historial
sobrevive a un reinicio del servidor. Un trabajo que quedó «en curso» al reiniciar se marca «interrumpido».
"""
import os, sys, json, glob, time, asyncio, datetime, uuid
from . import config

class Ocupado(Exception): pass

class Trabajo:
    def __init__(s,tipo,params,script,args,id=None):
        s.id=id or datetime.datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:4]
        s.tipo=tipo; s.params=params; s.script=script; s.args=args
        s.estado='en_curso'; s.codigo=None
        s.inicio=time.time(); s.fin=None
        s.lineas=[]; s.subs=set()

    def carpeta(s):
        d=os.path.join(config.salida(),'trabajos'); os.makedirs(d,exist_ok=True); return d

    def resumen(s):
        return {'id':s.id,'tipo':s.tipo,'params':s.params,'estado':s.estado,'codigo':s.codigo,
                'inicio':s.inicio,'fin':s.fin,'duracion':round((s.fin or time.time())-s.inicio,1)}

    def guardar(s):
        json.dump(s.resumen(),open(os.path.join(s.carpeta(),s.id+'.json'),'w',encoding='utf-8'),ensure_ascii=False)

    def agregar(s,linea):
        s.lineas.append(linea)
        with open(os.path.join(s.carpeta(),s.id+'.log'),'a',encoding='utf-8') as f: f.write(linea)
        for q in list(s.subs): q.put_nowait(('linea',linea))

    def terminar(s,estado,codigo):
        s.estado=estado; s.codigo=codigo; s.fin=time.time(); s.guardar()
        for q in list(s.subs): q.put_nowait(('fin',s.resumen()))

TRABAJOS={}      # id → Trabajo (los de esta ejecución del servidor y los cargados del disco)
_actual=None

def actual():
    return _actual if _actual and _actual.estado=='en_curso' else None

def cargar_historial():
    for f in glob.glob(os.path.join(config.salida(),'trabajos','*.json')):
        try: d=json.load(open(f,encoding='utf-8'))
        except (OSError,ValueError): continue
        if d['id'] in TRABAJOS: continue
        t=Trabajo(d['tipo'],d.get('params',{}),'',[],id=d['id'])
        t.estado=d['estado']; t.codigo=d.get('codigo'); t.inicio=d['inicio']; t.fin=d.get('fin')
        if t.estado=='en_curso':
            t.estado='interrumpido'; t.fin=t.fin or os.path.getmtime(f); t.guardar()
        TRABAJOS[t.id]=t

def lineas_de(t):
    # en memoria si corrió en esta ejecución; si no, del archivo de log
    if t.lineas or t.estado=='en_curso': return list(t.lineas)
    f=os.path.join(config.salida(),'trabajos',t.id+'.log')
    return open(f,encoding='utf-8',errors='replace').readlines() if os.path.isfile(f) else []

def lanzar(tipo,params,script,args):
    global _actual
    if actual(): raise Ocupado(actual().id)
    t=Trabajo(tipo,params,script,args)
    t._tarea=asyncio.get_running_loop().create_task(_correr(t))   # guardar la referencia: evita que la recolecte el GC
    t.guardar()
    TRABAJOS[t.id]=_actual=t
    return t

async def _correr(t):
    t.agregar(f'$ python {t.script} {" ".join(t.args)}\n')
    try:
        p=await asyncio.create_subprocess_exec(sys.executable,'-u',os.path.join(config.RAIZ,t.script),*t.args,
            cwd=config.RAIZ,env=config.env_subproceso(),limit=1<<20,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
        async for raw in p.stdout:
            t.agregar(raw.decode('utf-8',errors='replace'))
        cod=await p.wait()
        t.terminar('ok' if cod==0 else 'fallo',cod)
    except Exception as e:   # no dejar el trabajo «en curso» para siempre si algo falla al lanzarlo
        t.agregar(f'\n[web] error al ejecutar {t.script}: {e}\n'); t.terminar('fallo',None)

async def seguir(t):
    """Generador para SSE: primero lo que ya hay, luego lo nuevo, y al final el estado."""
    q=asyncio.Queue()
    previas=lineas_de(t)
    en_curso=t.estado=='en_curso'
    if en_curso: t.subs.add(q)   # sin await entre la copia y la suscripción: no se pierde ninguna línea
    try:
        for l in previas: yield ('linea',l)
        if not en_curso:
            yield ('fin',t.resumen()); return
        while True:
            try: ev=await asyncio.wait_for(q.get(),timeout=15)
            except asyncio.TimeoutError:
                yield ('latido',None); continue
            yield ev
            if ev[0]=='fin': return
    finally:
        t.subs.discard(q)
