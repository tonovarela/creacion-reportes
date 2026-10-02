"""Web del proceso semanal de reportes.

  /reportes/<año>/<semana>/<token>/   reportes de los vendedores: público (la carpeta es un token no adivinable)
  /  y  /api/*                        panel y API: solo desde las redes de ADMIN_REDES (no hay login)

Arranque:  uvicorn web.app.main:app --host 0.0.0.0 --port 8000
Detrás de Apache: ver deploy/apache-reportes.conf (UVICORN_ROOT_PATH y FORWARDED_ALLOW_IPS).
"""
import os, re, json, ipaddress
from contextlib import asynccontextmanager
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import config, trabajos, semanas
import enviar_correos

@asynccontextmanager
async def vida(app):
    trabajos.cargar_historial()
    yield

# Detrás de Apache en una subruta (ProxyPass /panel-reportes/ → /), el prefijo se le da a uvicorn con
# UVICORN_ROOT_PATH=/panel-reportes: así llega en scope['root_path'] y los estáticos y /api/docs lo respetan.
# El cliente usa rutas relativas, así que no necesita saberlo.
app=FastAPI(title='Reportes semanales',lifespan=vida,docs_url='/api/docs',redoc_url=None,openapi_url='/api/openapi.json')

# ---------- acceso: el panel solo desde la red interna ----------
REDES=[ipaddress.ip_network(r.strip(),strict=False) for r in
       (os.environ.get('ADMIN_REDES') or '127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16').split(',') if r.strip()]

def ip_cliente(req):
    # detrás de un proxy, uvicorn ya pone aquí la IP real (X-Forwarded-For) solo si el proxy está en
    # --forwarded-allow-ips; así un cliente no puede hacerse pasar por interno mandando ese encabezado
    return req.client.host if req.client else ''

def es_interna(ip):
    try: a=ipaddress.ip_address(ip)
    except ValueError: return False
    if getattr(a,'ipv4_mapped',None): a=a.ipv4_mapped
    return any(a in r for r in REDES)

@app.middleware('http')
async def solo_red_interna(req:Request,call_next):
    # fuera de la red interna el panel «no existe» (404), para no anunciarlo; los reportes sí se sirven
    # ruta sin el prefijo del proxy (con UVICORN_ROOT_PATH, scope['path'] lo incluye)
    ruta,prefijo=req.scope['path'],req.scope.get('root_path','')
    if prefijo and ruta.startswith(prefijo+'/'): ruta=ruta[len(prefijo):]
    if not ruta.startswith('/reportes/') and not es_interna(ip_cliente(req)):
        return PlainTextResponse('No encontrado',status_code=404)
    return await call_next(req)

# ---------- estáticos ----------
os.makedirs(os.path.join(config.salida(),'public'),exist_ok=True)
# solo public/ (carpetas por token); salida/reportes/ lleva nombres de vendedor y no se publica
app.mount('/reportes',StaticFiles(directory=os.path.join(config.salida(),'public'),html=True),name='reportes')
app.mount('/static',StaticFiles(directory=os.path.join(config.WEB,'static')),name='static')
app.mount('/cliente',StaticFiles(directory=os.path.join(config.WEB,'cliente')),name='cliente')

@app.get('/',include_in_schema=False)
def inicio():
    return FileResponse(os.path.join(config.WEB,'cliente','index.html'))

# ---------- API ----------
def excels():
    d=config.entrada()
    return sorted((f for f in os.listdir(d) if f.lower().endswith('.xlsx') and not f.startswith('.')),reverse=True) if os.path.isdir(d) else []

@app.get('/api/estado')
def estado():
    try: cco=enviar_correos.lista_cco(); cco_ok=True
    except SystemExit: cco=[]; cco_ok=False
    a=trabajos.actual()
    return {'config':config.estado_config(),'cco':cco,'cco_valido':cco_ok,
            'excels':excels(),'trabajo_actual':a.resumen() if a else None}

class NuevoTrabajo(BaseModel):
    tipo:Literal['completo','extraer','generar','correos']
    excel:Optional[str]=None          # nombre de un .xlsx de ENTRADA
    semana:Optional[str]=None         # para tipo=correos
    modo:Literal['vista','prueba','enviar']='vista'
    correo_prueba:Optional[str]=None
    ignorar_avisos:bool=False
    confirmacion:Optional[str]=None   # envío real: la semana (correos) o ENVIAR (completo)

RE_CORREO=re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def ruta_excel(nombre):
    # solo archivos de la carpeta de entrada, por nombre: nada de rutas
    if not nombre or os.path.basename(nombre)!=nombre or not nombre.lower().endswith('.xlsx'):
        raise HTTPException(422,'Excel no válido')
    r=os.path.join(config.entrada(),nombre)
    if not os.path.isfile(r): raise HTTPException(404,f'No existe {nombre} en la carpeta de entrada')
    return r

@app.post('/api/trabajos',status_code=202)
async def crear_trabajo(t:NuevoTrabajo):   # async: el trabajo se agenda en el loop del servidor
    if trabajos.actual(): raise HTTPException(409,'Ya hay un trabajo en curso; espera a que termine.')
    modo_args=[]
    if t.tipo in ('completo','correos'):
        if t.modo=='prueba':
            dest=(t.correo_prueba or os.environ.get('CORREO_PRUEBA') or '').strip()
            if not RE_CORREO.match(dest): raise HTTPException(422,'Indica un correo válido para la prueba.')
            modo_args=['--prueba',dest]
        elif t.modo=='enviar':
            try:
                if not enviar_correos.lista_cco(): raise HTTPException(422,'Falta CORREO_CCO en el .env: el envío real no se puede hacer sin la lista de copia oculta.')
            except SystemExit as e: raise HTTPException(422,str(e))
            modo_args=['--enviar']
    params=t.model_dump(exclude={'confirmacion'})

    if t.tipo=='extraer':
        return trabajos.lanzar('extraer',params,'extraer_excel.py',[]).resumen()
    if t.tipo=='generar':
        return trabajos.lanzar('generar',params,'gen.py',[ruta_excel(t.excel)]).resumen()
    if t.tipo=='completo':
        args=(['--excel',ruta_excel(t.excel)] if t.excel else [])+modo_args
        if t.modo=='enviar':
            if (t.confirmacion or '').strip().upper()!='ENVIAR':
                raise HTTPException(422,'Para el envío real escribe ENVIAR en la confirmación.')
            if t.ignorar_avisos: args.append('--ignorar-avisos')
        return trabajos.lanzar('completo',params,'orquestador.py',args).resumen()
    # correos
    k,a=semanas.archivos(t.semana)
    if not a or 'ligas' not in a: raise HTTPException(404,'Esa semana no tiene archivo de ligas: genera primero los reportes.')
    if t.modo=='enviar':
        if (t.confirmacion or '').strip().upper()!=k:
            raise HTTPException(422,f'Para el envío real escribe la semana ({k}) en la confirmación.')
        crit=semanas.criticos(k)
        if crit and not t.ignorar_avisos:
            raise HTTPException(409,{'mensaje':f'La semana tiene {len(crit)} aviso(s) crítico(s); revísalos o marca «ignorar avisos».','criticos':crit})
    return trabajos.lanzar('correos',params,'enviar_correos.py',[a['ligas']]+modo_args).resumen()

@app.get('/api/trabajos')
def lista_trabajos(limite:int=30):
    ts=sorted(trabajos.TRABAJOS.values(),key=lambda t:t.inicio,reverse=True)[:limite]
    return [t.resumen() for t in ts]

def _trabajo(id):
    t=trabajos.TRABAJOS.get(id)
    if not t: raise HTTPException(404,'No existe ese trabajo')
    return t

@app.get('/api/trabajos/{id}')
def ver_trabajo(id:str):
    return _trabajo(id).resumen()

@app.get('/api/trabajos/{id}/log')
async def log_trabajo(id:str):
    t=_trabajo(id)
    async def eventos():
        async for tipo,dato in trabajos.seguir(t):
            if tipo=='latido': yield ': latido\n\n'      # comentario SSE: mantiene viva la conexión
            elif tipo=='fin': yield f'event: fin\ndata: {json.dumps(dato,ensure_ascii=False)}\n\n'
            else: yield f'data: {json.dumps(dato,ensure_ascii=False)}\n\n'
    return StreamingResponse(eventos(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.get('/api/semanas')
def lista_semanas():
    return semanas.listar()

@app.get('/api/semanas/{sem}')
def ver_semana(sem:str):
    d=semanas.detalle(sem)
    if not d: raise HTTPException(404,'No hay archivos de esa semana')
    return d

@app.get('/api/semanas/{sem}/excel')
def excel_semana(sem:str):
    k,a=semanas.archivos(sem)
    if not a or 'excel' not in a: raise HTTPException(404,'Esa semana no tiene Excel en la carpeta de entrada')
    return FileResponse(a['excel'],filename=os.path.basename(a['excel']),
                        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.get('/api/semanas/{sem}/correos/{slug}',response_class=HTMLResponse)
def vista_correo(sem:str,slug:str):
    html=semanas.vista_correo(sem,slug)
    if html is None: raise HTTPException(404,'No hay correo para ese destinatario')
    return HTMLResponse(html)
