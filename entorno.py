import os
# .env junto a este archivo (opcional): una variable KEY=valor por línea. No pisa lo que ya venga
# definido en el entorno. Rutas relativas se resuelven contra la carpeta del proyecto,
# para que dé igual desde dónde se ejecute.
BASE=os.path.dirname(os.path.abspath(__file__))
RUTAS=('ENTRADA','SALIDA','FOLDER_SQL')
def cargar_env(ruta=os.path.join(BASE,'.env')):
    if not os.path.exists(ruta): return
    for l in open(ruta,encoding='utf-8'):
        l=l.strip()
        if not l or l.startswith('#') or '=' not in l: continue
        k,v=l.split('=',1); k=k.strip(); v=v.strip().strip('"\'')
        if k in RUTAS and v and not os.path.isabs(v):
            v=os.path.normpath(os.path.join(BASE,v))
        os.environ.setdefault(k,v)
