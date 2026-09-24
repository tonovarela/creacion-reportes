"""Corre el proceso semanal completo, en orden, y se detiene en el primer paso que falle:

  1. extraer_excel.py   consultas de sql/ → <ENTRADA>/<semana>.xlsx
  2. gen.py             ese Excel → reportes, avisos-<semana>.json y <SALIDA>/ligas-<semana>.csv
  3. enviar_correos.py  ese archivo de ligas → correos

Cada paso recibe el archivo que produjo el anterior, así que siempre trabajan sobre la misma semana.
Igual que enviar_correos.py, sin --prueba ni --enviar no se manda ningún correo (solo vistas previas).

Uso:
  python orquestador.py                              # extrae, genera y deja vistas previas de los correos
  python orquestador.py --prueba yo@litoprocess.com  # todos los correos a esa cuenta
  python orquestador.py --enviar                     # envío real a los vendedores
  python orquestador.py --excel entrada/2026-W38.xlsx --enviar   # se salta la extracción y usa ese Excel

Los correos reales van con copia oculta a CORREO_CCO del .env (obligatoria con --enviar).
Con --enviar, si gen.py dejó avisos críticos (cifras que no cuadran) no se envía nada, a menos que se
agregue --ignorar-avisos después de revisarlos.
"""
import os, re, sys, json, time, argparse, subprocess
from entorno import cargar_env
cargar_env()

BASE=os.path.dirname(os.path.abspath(__file__))

def paso(n,titulo,script,args):
    # corre el script con el mismo intérprete, muestra su salida en vivo y la devuelve para leer qué produjo
    print(f'\n=== {n}/3 {titulo} ===',flush=True)
    t0=time.time(); lineas=[]
    p=subprocess.Popen([sys.executable,'-u',os.path.join(BASE,script),*args],cwd=BASE,
                       stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
    for l in p.stdout:
        print(l,end='',flush=True); lineas.append(l)
    p.wait()
    if p.returncode:
        raise SystemExit(f'\n✗ Falló el paso {n} ({script}, código {p.returncode}); no se corren los siguientes.')
    print(f'--- paso {n} OK en {time.time()-t0:,.0f}s',flush=True)
    return ''.join(lineas)

def main(args):
    ap=argparse.ArgumentParser(prog='orquestador.py',description='Extrae el Excel, genera los reportes y envía los correos, en secuencia.')
    ap.add_argument('--excel',metavar='ARCHIVO',help='usar este Excel y saltarse la extracción de SQL Server')
    modo=ap.add_mutually_exclusive_group()
    modo.add_argument('--prueba',nargs='?',const='',metavar='CORREO',help='manda todos los correos a esta cuenta (o a CORREO_PRUEBA del .env)')
    modo.add_argument('--enviar',action='store_true',help='envío real a los vendedores')
    ap.add_argument('--ignorar-avisos',action='store_true',help='con --enviar, envía aunque gen.py haya dejado avisos críticos')
    a=ap.parse_args(args)
    if a.prueba=='' and not os.environ.get('CORREO_PRUEBA'):
        ap.error('--prueba necesita un correo: --prueba yo@dominio.com (o CORREO_PRUEBA en el .env)')
    if a.enviar and not (os.environ.get('CORREO_CCO') or '').strip():
        # se revisa aquí para no esperar toda la extracción y enterarse al final
        ap.error('falta CORREO_CCO en el .env: la lista de correos que va en copia oculta, separados por coma')

    # 1. extracción
    if a.excel:
        if not os.path.isfile(a.excel): raise SystemExit(f'No existe {a.excel}')
        excel=os.path.abspath(a.excel)
        print(f'\n=== 1/3 Extracción: se omite, se usa {excel} ===')
    else:
        out=paso(1,'Extracción de SQL Server','extraer_excel.py',[])
        m=re.search(r'^Excel: (.+)$',out,flags=re.M)
        if not m: raise SystemExit('extraer_excel.py terminó sin decir qué Excel escribió.')
        excel=m.group(1).strip()

    # 2. reportes
    out=paso(2,'Generación de reportes','gen.py',[excel])
    m=re.search(r'ligas-(\S+?)\.csv',out)
    if not m: raise SystemExit('gen.py terminó sin generar el archivo de ligas.')
    sem=m.group(1)
    sal=os.environ.get('SALIDA','/mnt/user-data/outputs')   # mismo valor por defecto que gen.py
    ligas=os.path.join(sal,f'ligas-{sem}.csv')
    if not os.path.isfile(ligas): raise SystemExit(f'No se encontró {ligas}')

    # antes de un envío real, frenar si hay cifras que no cuadran
    avisos_f=os.path.join(sal,f'avisos-{sem}.json')
    criticos=[x['msg'] for x in json.load(open(avisos_f,encoding='utf-8')) if x.get('nivel')=='critico'] if os.path.isfile(avisos_f) else []
    if a.enviar and criticos and not a.ignorar_avisos:
        print(f'\n✗ No se envió ningún correo: gen.py dejó {len(criticos)} aviso(s) crítico(s):')
        for c in criticos: print('   -',c)
        raise SystemExit(f'Revísalos en {avisos_f}. Para enviar de todos modos: python orquestador.py --excel "{excel}" --enviar --ignorar-avisos')

    # 3. correos
    if a.enviar: extra=['--enviar']; titulo='Envío de correos'
    elif a.prueba is not None: extra=['--prueba']+([a.prueba] if a.prueba else []); titulo='Envío de correos de prueba'
    else: extra=[]; titulo='Correos (solo vistas previas, no se envía nada)'
    paso(3,titulo,'enviar_correos.py',[ligas,*extra])
    print(f'\n✓ Proceso completo · semana {sem} · Excel {excel} · ligas {ligas}')

if __name__=='__main__':
    main(sys.argv[1:])
