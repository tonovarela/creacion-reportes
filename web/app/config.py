"""Rutas y configuración compartidas por la web. Se apoya en entorno.cargar_env(), igual que los scripts."""
import os, sys

RAIZ=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RAIZ not in sys.path: sys.path.insert(0,RAIZ)
from entorno import cargar_env
cargar_env()
WEB=os.path.join(RAIZ,'web')

def entrada():
    # ENTRADA puede ser una carpeta o un .xlsx; la web siempre trabaja con la carpeta
    e=os.environ.get('ENTRADA') or os.path.join(RAIZ,'entrada')
    return os.path.dirname(e) if e.lower().endswith('.xlsx') else e

def salida():
    return os.environ.get('SALIDA') or os.path.join(RAIZ,'salida')

def env_subproceso():
    # los scripts reciben las mismas carpetas que ve la web, y salida en UTF-8 sin búfer para el log en vivo
    env=dict(os.environ)
    env.update(ENTRADA=entrada(),SALIDA=salida(),PYTHONUNBUFFERED='1',PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    return env

def estado_config():
    # solo si cada cosa está configurada; nunca los valores
    hay=lambda *ks: all((os.environ.get(k) or '').strip() for k in ks)
    return {
        'sql':hay('SQL_SERVIDOR','SQL_BASE_DATOS','SQL_USUARIO','SQL_CONTRASENA'),
        'smtp':hay('SMTP_SERVIDOR','SMTP_USUARIO','SMTP_CONTRASENA'),
        'token_secreto':len(os.environ.get('TOKEN_SECRETO') or '')>=32,
        'correo_cco':hay('CORREO_CCO'),
        'direccion_correo':hay('DIRECCION_CORREO'),
        'base_url':os.environ.get('BASE_URL') or '',
    }
