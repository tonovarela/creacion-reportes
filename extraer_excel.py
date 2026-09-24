"""Ejecuta las consultas de sql/ contra SQL Server y arma el Excel semanal que consume gen.py.

Cada archivo NN-nombre.sql es una hoja: el orden sale del número inicial (01, 02, …) y el nombre
de la hoja del primer comentario del archivo (-- Encabezado). Los separadores GO se respetan.

Uso:
  python extraer_excel.py                 # escribe <ENTRADA>/<semana_iso>.xlsx
  python extraer_excel.py salida.xlsx     # a un archivo específico
  python extraer_excel.py --listar        # solo muestra qué hojas saldrían, sin conectarse
"""
import os, re, sys, glob, time, datetime, decimal
import pandas as pd
from entorno import cargar_env
cargar_env()

SQL_DIR=os.environ.get('FOLDER_SQL') or os.path.join(os.path.dirname(os.path.abspath(__file__)),'sql')
PROHIBIDOS=set('[]:*?/\\')
# columnas que se muestran como moneda (sin distinguir mayúsculas); si una consulta agrega un monto nuevo, va aquí
MONTOS={'importe','facturado_semana','facturado_mes','facturado_ano','comision_devengada_ano',
        'comision_pagada_ano','comision_pendiente_cobranza','comision_retenida_ano','venta_mes','meta_mes',
        'impultcobro','corriente','d0_30','d31_60','d61_90','d90_mas','saldo','venta'}
FMT_MONTO='"$"#,##0.00'
FMT_FECHA='mm/dd/yyyy'

def nombre_hoja(txt,ruta):
    # la primera línea con contenido tiene que ser el comentario con el nombre de la hoja
    for l in txt.splitlines():
        l=l.strip()
        if not l: continue
        n=l.lstrip('-').strip() if l.startswith('--') else ''
        if not n:
            raise SystemExit(f'{ruta}: la primera línea con texto debe ser el nombre de la hoja, p. ej. "-- Cartera".')
        if len(n)>31 or PROHIBIDOS & set(n):
            raise SystemExit(f'{ruta}: «{n}» no sirve como nombre de hoja (máx. 31 caracteres, sin []:*?/\\).')
        return n
    raise SystemExit(f'{ruta}: archivo vacío.')

def consultas(carpeta):
    arch=[]
    for ruta in glob.glob(os.path.join(carpeta,'*.sql')):
        m=re.match(r'(\d+)',os.path.basename(ruta))
        if not m:
            print(f'  [aviso] se ignora {os.path.basename(ruta)}: no empieza con número de orden'); continue
        arch.append((int(m.group(1)),ruta))
    if not arch: raise SystemExit(f'No hay archivos NN-*.sql en {carpeta}')
    arch.sort()
    nums=[n for n,_ in arch]
    if len(set(nums))!=len(nums):
        raise SystemExit('Hay dos .sql con el mismo número de orden: '+', '.join(os.path.basename(r) for n,r in arch if nums.count(n)>1))
    out=[]
    for n,ruta in arch:
        txt=open(ruta,encoding='utf-8-sig').read()
        out.append((n,nombre_hoja(txt,ruta),ruta,txt))
    hojas=[h for _,h,_,_ in out]
    rep={h for h in hojas if [x.lower() for x in hojas].count(h.lower())>1}
    if rep: raise SystemExit('Nombre de hoja repetido en sql/: '+', '.join(sorted(rep)))
    return out

def sin_comentarios(s):
    return re.sub(r'--[^\n]*','',re.sub(r'/\*.*?\*/','',s,flags=re.S)).strip()

def lotes(txt):
    # GO no es T-SQL, es el separador de lotes de SSMS/sqlcmd: cada lote se manda por separado
    return [l for l in re.split(r'^\s*GO\s*;?\s*$',txt,flags=re.I|re.M) if sin_comentarios(l)]

def ejecutar(cn,txt,ruta):
    cur=cn.cursor(); res=[]
    for lote in lotes(txt):
        cur.execute('SET NOCOUNT ON;\n'+lote)
        while True:
            if cur.description:
                res.append(pd.DataFrame.from_records(cur.fetchall(),columns=[c[0] for c in cur.description]))
            if not cur.nextset(): break
    if len(res)!=1:
        raise SystemExit(f'{ruta}: se esperaba exactamente un resultado (SELECT) y hubo {len(res)}.')
    df=res[0]
    # DECIMAL/MONEY llegan como Decimal: a float para que Excel los guarde como número
    for c in df.columns:
        if df[c].map(lambda x: isinstance(x,decimal.Decimal)).any(): df[c]=pd.to_numeric(df[c])
    # algunos montos llegan como texto ya formateado ("29,550.00"): a número para poder darles formato
    for c in df.columns:
        if str(c).lower() in MONTOS and not pd.api.types.is_numeric_dtype(df[c]):
            s=df[c].astype('string').str.replace(r'[$,\s]','',regex=True).replace('',pd.NA)
            df[c]=pd.to_numeric(s).astype(float)
    return df

def formatear(ws,df):
    # fechas en mm/dd/yyyy y montos como $#,##0.00; se ensancha la columna para que Excel no muestre ####
    for i,c in enumerate(df.columns,start=1):
        es_fecha=pd.api.types.is_datetime64_any_dtype(df[c]) or df[c].map(lambda x: isinstance(x,(datetime.date,datetime.datetime))).any()
        es_monto=str(c).lower() in MONTOS
        if not (es_fecha or es_monto): continue
        fmt=FMT_FECHA if es_fecha else FMT_MONTO
        for (celda,) in ws.iter_rows(min_row=2,min_col=i,max_col=i):
            celda.number_format=fmt
        ancho=10 if es_fecha else max((len(f'${v:,.2f}') for v in df[c].dropna()),default=0)
        ws.column_dimensions[ws.cell(1,i).column_letter].width=max(ancho,len(str(c)))+2

def nombre_archivo(hojas):
    # el nombre sale de semana_iso de la hoja Encabezado (sql/01-encabezados.sql); con la semana a 2 dígitos
    # para que el orden alfabético (el que usa gen.py para tomar el más reciente) sea el correcto
    df=hojas.get('Encabezado')
    if df is None or 'semana_iso' not in df.columns:
        raise SystemExit('La hoja Encabezado no trae la columna semana_iso: no se puede nombrar el Excel.')
    v=df.semana_iso.dropna().astype(str).str.strip().unique()
    m=re.match(r'^(\d{4})-W(\d{1,2})$',v[0]) if len(v)==1 else None
    if not m:
        raise SystemExit(f'semana_iso de Encabezado debe traer una sola semana tipo 2026-W38 y trae: {", ".join(v) or "(vacío)"}')
    return f'{m.group(1)}-W{int(m.group(2)):02d}.xlsx'

def conectar():
    import pymssql
    faltan=[k for k in ('SQL_SERVIDOR','SQL_BASE_DATOS','SQL_USUARIO','SQL_CONTRASENA') if not os.environ.get(k)]
    if faltan: raise SystemExit('Faltan en el .env o el entorno: '+', '.join(faltan))
    try:
        cn=pymssql.connect(server=os.environ['SQL_SERVIDOR'],port=os.environ.get('SQL_PUERTO') or '1433',
                           database=os.environ['SQL_BASE_DATOS'],user=os.environ['SQL_USUARIO'],
                           password=os.environ['SQL_CONTRASENA'],charset='UTF-8',login_timeout=30,
                           timeout=int(os.environ.get('SQL_TIMEOUT') or 600))
    except pymssql.OperationalError as e:
        msg=e.args[0][1].decode(errors='replace') if e.args and isinstance(e.args[0],tuple) else str(e)
        raise SystemExit('No se pudo conectar a SQL Server — revisa SQL_SERVIDOR, SQL_PUERTO, usuario y contraseña.\n'+msg.strip())
    # FreeTDS abre la sesión en us_english (mdy) aunque el login tenga otro idioma; las vistas que
    # convierten fechas varchar truenan con error 242. Se usa el idioma del login, igual que SSMS,
    # o el de SQL_IDIOMA si se define.
    cur=cn.cursor()
    idioma=os.environ.get('SQL_IDIOMA')
    if not idioma:
        cur.execute('SELECT default_language_name FROM sys.server_principals WHERE name=SUSER_SNAME()')
        r=cur.fetchone(); idioma=r[0] if r else None
    if idioma: cur.execute("SET LANGUAGE %s",(idioma,))
    return cn

def main(args):
    qs=consultas(SQL_DIR)
    if '--listar' in args:
        for n,h,r,t in qs: print(f'{n:>3}  {h:<20} {os.path.basename(r)}  ({len(lotes(t))} lote(s))')
        return
    destino=next((a for a in args if not a.startswith('--')),None)
    print(f'Conectando a {os.environ.get("SQL_SERVIDOR")}/{os.environ.get("SQL_BASE_DATOS")}…')
    cn=conectar(); hojas={}
    try:
        for n,h,r,t in qs:
            t0=time.time(); hojas[h]=ejecutar(cn,t,r)
            print(f'  {n:>3}  {h:<20} {len(hojas[h]):>7,} filas  {time.time()-t0:5.1f}s')
    finally:
        cn.close()
    if not destino:
        ent=os.environ.get('ENTRADA') or '.'
        carpeta=ent if not ent.lower().endswith('.xlsx') else os.path.dirname(ent) or '.'
        destino=os.path.join(carpeta,nombre_archivo(hojas))
    os.makedirs(os.path.dirname(os.path.abspath(destino)),exist_ok=True)
    # se escribe a un temporal oculto y se renombra: si algo falla, no queda un .xlsx a medias
    # que gen.py tome (su búsqueda con *.xlsx no ve archivos que empiezan con punto)
    tmp=os.path.join(os.path.dirname(os.path.abspath(destino)),'.'+os.path.basename(destino))
    with pd.ExcelWriter(tmp,engine='openpyxl') as w:
        for h,df in hojas.items():
            df.to_excel(w,sheet_name=h,index=False); formatear(w.sheets[h],df)
    os.replace(tmp,destino)
    print('Excel:',destino)

if __name__=='__main__':
    main(sys.argv[1:])
