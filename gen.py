

import pandas as pd, json, math, os, hmac, hashlib
import sys, glob
from entorno import cargar_env
cargar_env()
def hallar():
    p=sys.argv[1] if len(sys.argv)>1 else os.environ.get('ENTRADA')
    if p:
        if os.path.isdir(p):
            f=sorted(glob.glob(os.path.join(p,'*.xlsx')))
            if not f: raise SystemExit('No hay .xlsx en '+p)
            return f[-1]
        return p
    for c in ['/mnt/user-data/uploads','.']:
        f=sorted(glob.glob(os.path.join(c,'*.xlsx')))
        if f: return f[-1]
    raise SystemExit('No encontré ningún .xlsx. Uso: python gen.py <archivo-o-carpeta>, o define ENTRADA')
ARCH=hallar()
SAL=os.environ.get('SALIDA','/mnt/user-data/outputs')
# clave para firmar los tokens: sin ella, el token saldría solo del nombre y sería adivinable
SECRETO=os.environ.get('TOKEN_SECRETO','')
if len(SECRETO)<32:
    raise SystemExit('Falta TOKEN_SECRETO (mínimo 32 caracteres) en el .env o el entorno. Genera uno con:\n'
                     '  python3 -c "import secrets;print(secrets.token_hex(32))"')
print('Archivo:',ARCH)

AVISOS=[]
def aviso(nivel,msg):
    AVISOS.append({'nivel':nivel,'msg':msg})
    print(('  [CRÍTICO] ' if nivel=='critico' else '  [aviso] ')+msg)

x=pd.ExcelFile(ARCH); S={s:pd.read_excel(x,s) for s in x.sheet_names}
H0=S['Encabezado']
FIN=pd.Timestamp(H0.fecha_fin.max()); INI=pd.Timestamp(H0.fecha_inicio.min())
SEM=str(H0.semana_iso.iloc[0]); MESACT=int(FIN.month)
def cl(s): return str(s).strip()
for s in S:
    if 'vendedor_nombre' not in S[s].columns:
        c0=S[s].columns[0]
        S[s]=S[s].rename(columns={c0:'vendedor_nombre'})
        aviso('aviso', f'En «{s}» la columna de vendedor venía sin nombre; se tomó la primera columna ({c0}).')
    S[s]['vn']=S[s].vendedor_nombre.map(cl)
FUERA={'SIN AGENTE','Gustavo Casas Aquino','Gerardo Delgado','Jose Antonio Garcia Ramos','Lito','VXT'}
for s in S: S[s]['vn']=S[s]['vn'].apply(lambda v:'CARTERA SIN ASIGNAR' if v in FUERA else v)

H=S['Encabezado'].groupby('vn',as_index=False).agg({
 'vendedor_correo':'first','ops_cerradas_semana':'sum','ops_cerradas_mes':'sum','ops_cerradas_ano':'sum',
 'comision_devengada_ano':'sum','comision_pagada_ano':'sum','comision_pendiente_cobranza':'sum','comision_retenida_ano':'sum'})
FS=S['Fac Sem Ant']
vends=sorted(set(H.vn)|set(S['Presupuesto'].vn)|set(S['Oport abiertas'].vn)|set(S['Cartera'].vn)|set(FS.vn))
_actuales=set(vends)-{'CARTERA SIN ASIGNAR'}
# cobertura de roster: un vn que aparece en alguna hoja pero no en el roster (vends)
# significa que esas filas nunca se le van a asignar a nadie y desaparecen sin avisar.
_cubiertos=set(vends)
for _s in S:
    _serie=S[_s].vn.dropna()
    _vacios=int((_serie=='').sum())
    if _vacios:
        aviso('critico', f'«{_s}» tiene {_vacios} fila(s) sin nombre de vendedor.')
    for _n in sorted(n for n in _serie.unique() if n and n not in _cubiertos):
        aviso('critico', f'«{_n}» aparece en la hoja «{_s}» pero no en Encabezado/Presupuesto/Oport abiertas/Cartera/Fac Sem Ant — sus filas ahí no van a aparecer en ningún reporte.')

# tokens: HMAC-SHA256(TOKEN_SECRETO, "<año>-W<semana>|<vendedor>"), solo hex (0-9a-f, 32 caracteres).
# El mismo vendedor en la misma semana siempre da el mismo token (volver a correr pisa los mismos
# archivos); otra semana u otro vendedor da uno distinto. Sin el secreto no se puede calcular.
# La liga es public/<año>/<semana>/<token>/index.html.
def token(v): return hmac.new(SECRETO.encode(),f'{SEM}|{v}'.encode(),hashlib.sha256).hexdigest()[:32]
TOKENS={_v:token(_v) for _v in list(_actuales)+['__direccion__']}
def r2(v):
    try:
        f=float(v); return 0 if (math.isnan(f) or abs(f)<0.005) else round(f,2)
    except: return 0
OW={'Presupuesto terminado':'ven','Pre registro':'ven','Solicitud de cotizacion':'ven',
    'Listo p/cotizar':'int','Listo p /presupuesto':'int','Cotizando':'int','Revisión Tecnica':'int',
    'Solicitud Prepensa':'int','Preprensa Concluida':'int','Autorización':'esp','Solicitud de OP':'esp'}
OUT={}
for v in vends:
    hh=H[H.vn==v]; h=hh.iloc[0] if len(hh) else None
    d={}
    p=S['Presupuesto']; p=p[p.vn==v]
    fw=FS[FS.vn==v]
    d['fact']={'s':r2(fw.venta.sum()),'m':r2(p[p.mes==MESACT].venta_mes.sum()),'a':r2(p[p.mes<=MESACT].venta_mes.sum()),
      'os':int(h.ops_cerradas_semana) if h is not None else 0,
      'om':int(h.ops_cerradas_mes) if h is not None else 0,
      'oa':int(h.ops_cerradas_ano) if h is not None else 0,
      'cs':int(fw.cliente.nunique()),
      'cm':int(p[(p.mes==MESACT)&(p.venta_mes.abs()>0.5)].cliente.nunique()),
      'ca':int(p[(p.mes<=MESACT)&(p.venta_mes.abs()>0.5)].cliente.nunique())}
    d['com']={'dev':r2(h.comision_devengada_ano) if h is not None else 0,
      'pag':r2(h.comision_pagada_ano) if h is not None else 0,
      'pen':r2(h.comision_pendiente_cobranza) if h is not None else 0,
      'ret':r2(h.comision_retenida_ano) if h is not None else 0}
    if abs(d['com']['dev']-(d['com']['pag']+d['com']['pen']))>1:
        aviso('aviso', f"{v}: comisión devengada ({d['com']['dev']:,.0f}) no cuadra con pagada+pendiente ({d['com']['pag']+d['com']['pen']:,.0f}).")
    d['facSem']=[{'f':str(z.movid),'c':cl(z.nombrecliente)[:40],'d':str(pd.Timestamp(z.fechaemision).date()),
                  'v':r2(z.venta),'nc':1 if 'Bonific' in str(z.mov) else 0}
                 for _,z in fw.sort_values('venta',ascending=False).iterrows()]
    # presupuesto por cliente
    cli=[]
    if len(p):
        # Opcion A: si una clave tiene meta como existente, todas sus ventas cuentan ahi.
        esb=p.groupby('cliente').es_bolsa.min()
        p=p.assign(es_bolsa=p.cliente.map(esb))
        g=p.groupby(['cliente','cliente_nombre','es_bolsa'],as_index=False).apply(lambda t: pd.Series({
          'vm':t[t.mes==MESACT].venta_mes.sum(),'mm':t[t.mes==MESACT].meta_mes.sum(),
          'va':t[t.mes<=MESACT].venta_mes.sum(),'ma':t[t.mes<=MESACT].meta_mes.sum(),
          'man':t.meta_mes.sum(),'sep':t[t.mes==MESACT+1].meta_mes.sum()}),include_groups=False)
        for _,r in g.iterrows():
            if abs(r.vm)+abs(r.mm)+abs(r.va)+abs(r.ma)+abs(r.man)+abs(r.sep)<1: continue
            cli.append({'n':cl(r.cliente_nombre)[:44],'al':str(int(r.cliente)),'b':int(r.es_bolsa),
                        'vm':r2(r.vm),'mm':r2(r.mm),'va':r2(r.va),'ma':r2(r.ma),'man':r2(r.man),'sep':r2(r.sep)})
    padre=next((c for c in cli if c['b'] and c['man']>0), None)
    if padre is None and any(c['b'] for c in cli):
        padre={'n':'Clientes nuevos','al':'99000','b':1,'vm':0,'mm':0,'va':0,'ma':0,'man':0,'sep':0}; cli.append(padre)
    if padre:
        hijos=[c for c in cli if c['b'] and c is not padre]
        _propio_va=padre['va']
        for k in ['vm','va']: padre[k]=r2(sum(z[k] for z in hijos))
        if abs(_propio_va)>500:
            aviso('aviso', f"{v}: la clave padre de «Clientes nuevos» tiene {_propio_va:,.0f} de venta registrada directamente ahí (no en un cliente hijo) — revisar si está mal codificada.")
        padre['n']='Clientes nuevos'
        padre['hijos']=sorted([{'n':z['n'],'vm':z['vm'],'va':z['va']} for z in hijos],key=lambda z:-z['va'])
        cli=[c for c in cli if not c['b'] or c is padre]
    d['cli']=sorted(cli,key=lambda c:-(c['ma']-c['va']))
    # fuga
    fuga=[]
    if len(p):
        piv=p.pivot_table(index='cliente_nombre',columns='mes',values='venta_mes',aggfunc='sum').fillna(0)
        prev=piv[[m for m in range(1,MESACT-1) if m in piv.columns]].sum(axis=1)
        rec=piv[[m for m in [MESACT-1,MESACT] if m in piv.columns]].sum(axis=1)
        for nm in piv.index:
            if prev.get(nm,0)>0 and rec.get(nm,0)==0:
                ult=max([m for m in piv.columns if piv.loc[nm,m]>0],default=None)
                fuga.append({'n':cl(nm)[:44],'v':r2(prev[nm]),'ult':int(ult) if ult else None})
    d['fuga']=sorted(fuga,key=lambda f:-f['v'])
    # facturación por cliente
    fc={'s':[],'m':[],'a':[]}
    if len(fw):
        gs=fw.groupby('nombrecliente').venta.sum().sort_values(ascending=False)
        fc['s']=[{'n':cl(i)[:42],'v':r2(z)} for i,z in gs.items() if abs(z)>0.5]
    if len(p):
        gf=p.groupby('cliente_nombre').apply(lambda t: pd.Series({
            'm':t[t.mes==MESACT].venta_mes.sum(),'a':t[t.mes<=MESACT].venta_mes.sum()}),include_groups=False)
        for per in ['m','a']:
            fc[per]=sorted([{'n':cl(i)[:42],'v':r2(r[per])} for i,r in gf.iterrows() if abs(r[per])>0.5],key=lambda t:-t['v'])
    d['factCli']=fc
    # pedidos
    pe=S['Pedidos']; pe=pe[pe.vn==v]; ped=[]
    if len(pe):
        g=pe.groupby(['op','cliente_nombre'],as_index=False).agg(pt=('importe','size'),v=('importe','sum'),fc=('fecha_emision','min'))
        for _,r in g.sort_values('v',ascending=False).iterrows():
            ln=pe[(pe.op==r.op)&(pe.cliente_nombre==r.cliente_nombre)]
            ped.append({'op':cl(r.op),'c':cl(r.cliente_nombre)[:40],'pt':int(r.pt),'v':r2(r.v),
                        'f':str(pd.Timestamp(r.fc).date()),'d':int((FIN-pd.Timestamp(r.fc)).days),
                        'ln':[{'d':str(z.descripcion)[:52],'v':r2(z.importe)} for _,z in ln.sort_values('importe',ascending=False).iterrows()]})
    d['ped']=ped
    # oportunidades abiertas
    oa=S['Oport abiertas']; oa=oa[oa.vn==v]; ab=[]
    for _,r in oa.sort_values('importe',ascending=False).iterrows():
        fa=pd.Timestamp(r.fecha_alta); iso=fa.isocalendar()
        ds=pd.Timestamp(r.fecha_cambio_estatus) if pd.notna(r.fecha_cambio_estatus) else None
        ab.append({'sem':f'{iso[0]}-W{iso[1]:02d}','c':cl(r.cliente_nombre)[:34],'d':str(r.descripcion)[:44],
          'v':r2(r.importe) if r.importe>1 else 0,'st':cl(r.estatus),'ow':OW.get(cl(r.estatus),'int'),
          'da':max(0,int((FIN-fa).days)),'ds':(max(0,int((FIN-ds).days)) if ds is not None else None),
          'tc':('Prospecto' if 'PROSPECTO' in str(r.tipo_cliente).upper() else
                'Inactivo' if 'INACTIVO' in str(r.tipo_cliente).upper() else 'Cliente')})
    d['ab']=ab
    # conversión y motivos
    oc=S['Oport cerradas']; oc=oc[oc.vn==v].copy()
    if len(oc): oc['fc']=pd.to_datetime(oc.fecha_cierre); oc['fa']=pd.to_datetime(oc.fecha_alta)
    oaf=oa.copy()
    if len(oaf): oaf['fa']=pd.to_datetime(oaf.fecha_alta)
    conv={}; mot={}
    for lbl,i0 in [('s',INI),('m',pd.Timestamp(FIN.year,MESACT,1)),('a',pd.Timestamp(FIN.year,1,1))]:
        emab=int(((oaf.fa>=i0)&(oaf.fa<=FIN)).sum()) if len(oaf) else 0
        em=emab+(int(((oc.fa>=i0)&(oc.fa<=FIN)).sum()) if len(oc) else 0)
        ce=oc[(oc.fc>=i0)&(oc.fc<=FIN)] if len(oc) else oc
        gan=int((ce.resultado=='OP Concluida').sum()) if len(ce) else 0
        conv[lbl]={'em':em,'emab':emab,'ce':int(len(ce)),'g':gan,'p':int(len(ce))-gan,
                   'tc':round(gan/len(ce)*100,1) if len(ce) else 0}
        per=ce[ce.resultado=='Perdido'] if len(ce) else ce
        mm=[]
        if len(per):
            for a_,b_ in per.motivo_rechazo.value_counts().items():
                sub=per[per.motivo_rechazo==a_].sort_values('importe',ascending=False)
                mm.append({'n':cl(a_)[:44],'c':int(b_),'v':r2(sub.importe.sum()),
                  'det':[{'c':cl(z.cliente_nombre)[:38],'v':r2(z.importe),'f':str(pd.Timestamp(z.fecha_cierre).date())}
                         for _,z in sub.head(20).iterrows()]})
        mot[lbl]={'n':int(len(per)),'d':mm}
    d['conv']=conv; d['mot']=mot
    # actividades
    ac=S['Actividades']; ac=ac[ac.vn==v].copy()
    T={'Reuniones':'Reunión','Llamadas':'Llamada'}
    def act(r):
        return {'f':str(pd.Timestamp(r.fecha).date()),'c':cl(r.cliente_nombre)[:38],
                't':T.get(cl(r.tipo_actividad),cl(r.tipo_actividad)),'e':cl(r.estatus),
                'm':int(r.tieneMinuta) if pd.notna(r.tieneMinuta) else 0}
    d['act']={'hechas':[],'prox':[],'noreal':[],'venc':[],'ano':0}
    if len(ac):
        ac['f']=pd.to_datetime(ac.fecha)
        d['act']['ano']=int((ac.estatus=='Realizada').sum())
        hs=ac[(ac.estatus=='Realizada')&(ac.f>=INI)&(ac.f<=FIN)].sort_values('f')
        # próximas: estrictamente después de la semana reportada. Lo planificado DENTRO de la
        # semana (INI..FIN) que nunca se marcó Realizada no es "próximo" — es una cita de esta
        # misma semana que no se cerró, va a su propio bucket (noreal), no al de citas futuras.
        pr=ac[(ac.estatus=='Planificada')&(ac.f>FIN)].sort_values('f')
        nr=ac[(ac.estatus=='Planificada')&(ac.f>=INI)&(ac.f<=FIN)].sort_values('f')
        vn=ac[(ac.estatus=='Planificada')&(ac.f<INI)].sort_values('f')
        d['act']['hechas']=[act(r) for _,r in hs.iterrows()]
        d['act']['prox']=[act(r) for _,r in pr.iterrows()]
        d['act']['noreal']=[dict(act(r),**{'d':int((FIN-r.f).days)}) for _,r in nr.iterrows()]
        d['act']['venc']=[dict(act(r),**{'d':int((INI-r.f).days)}) for _,r in vn.iterrows()]
    # entregas
    en=S['Entregas']; en=en[en.vn==v].copy()
    if len(en):
        for c_ in ['fecha_compromiso_original','fecha_entrega']: en[c_]=pd.to_datetime(en[c_],errors='coerce')
        d['en']={'ok':int((en.cumple==1).sum()),'t':int(len(en))}
        gc=en.groupby('cliente_nombre').cumple.agg(['sum','size'])
        d['encli']=[{'c':cl(i)[:40],'ok':int(r['sum']),'t':int(r['size'])} for i,r in gc.sort_values('size',ascending=False).iterrows()]
        en['dd']=(en.fecha_entrega-en.fecha_compromiso_original).dt.days
        en=en.sort_values(['cumple','fecha_compromiso_original'],ascending=[True,False])
        d['ennc']=[{'op':cl(r.op),'c':cl(r.cliente_nombre)[:36],
                    'cm':str(r.fecha_compromiso_original.date()) if pd.notna(r.fecha_compromiso_original) else '',
                    'fe':str(r.fecha_entrega.date()) if pd.notna(r.fecha_entrega) else '',
                    'dd':(int(r.dd) if pd.notna(r.dd) else None),'ok':int(r.cumple)} for _,r in en.iterrows()]
    else:
        d['en']={'ok':0,'t':0}; d['encli']=[]; d['ennc']=[]
    # cartera (nivel documento -> por cliente); bloqueo derivado de pedidos detenidos
    blq=set(S['Pedidos'][S['Pedidos'].detenido_credito==1].cliente.astype(int))
    ca=S['Cartera']; ca=ca[ca.vn==v]; d['car']=[]
    if len(ca):
        g=ca.groupby(['cliente','cliente_nombre'],as_index=False).agg(
            corriente=('corriente','sum'),d0_30=('d0_30','sum'),d31_60=('d31_60','sum'),
            d61_90=('d61_90','sum'),d90_mas=('d90_mas','sum'),dias=('DiasVencidos','max'),docs=('MovID','size'))
        d['car']=[{'n':cl(r.cliente_nombre)[:40],'al':str(int(r.cliente)),'dias':int(r.dias),'docs':int(r.docs),
                   'blq':1 if int(r.cliente) in blq else 0,
                   'r':[r2(r.corriente),r2(r.d0_30),r2(r.d31_60),r2(r.d61_90),r2(r.d90_mas)]}
                  for _,r in g.iterrows() if sum(abs(r[k]) for k in ['corriente','d0_30','d31_60','d61_90','d90_mas'])>0.5]
    # facturas sin revisión
    fa_=S['Fact Sin Rev']; fa_=fa_[fa_.vn==v]
    d['fac']=[{'f':cl(r.folio),'c':cl(r.cliente_nombre)[:38],'e':str(pd.Timestamp(r.fechaEmision).date()),
               'v':r2(r.saldo),'d':int((FIN-pd.Timestamp(r.fechaEmision)).days)} for _,r in fa_.iterrows()]
    OUT[v]=d
print('vendedores:',len(OUT),'| semana',SEM,'|',INI.date(),'a',FIN.date())
_fact_s_bu=round(sum(d['fact']['s'] for d in OUT.values()),2)
_fact_s_td=r2(FS.venta.sum())
if abs(_fact_s_bu-_fact_s_td)>max(5,abs(_fact_s_td)*0.001):
    aviso('critico', f"Facturación semanal: la suma por vendedor ({_fact_s_bu:,.0f}) no cuadra con el total de «Fac Sem Ant» ({_fact_s_td:,.0f}).")

# ================= AGREGADOS DE EMPRESA =================
E={}
P=S['Presupuesto']
mm=P.groupby('mes').agg(v=('venta_mes','sum'),m=('meta_mes','sum'))
E['meses']=[{'m':int(i),'v':r2(r.v),'me':r2(r.m)} for i,r in mm.iterrows()]
_fact_m_bu=round(sum(d['fact']['m'] for d in OUT.values()),2)
_fact_m_td=r2(mm.loc[MESACT,'v']) if MESACT in mm.index else 0
if abs(_fact_m_bu-_fact_m_td)>max(5,abs(_fact_m_td)*0.001):
    aviso('critico', f"Facturación del mes en curso: la suma por vendedor ({_fact_m_bu:,.0f}) no cuadra con el total de «Presupuesto» ({_fact_m_td:,.0f}).")
E['acum']={'v':r2(mm[mm.index<=MESACT].v.sum()),'m':r2(mm[mm.index<=MESACT].m.sum())}
E['anual']={'m':r2(mm.m.sum())}
E['resto']={'m':r2(mm[mm.index>MESACT].m.sum()),'meses':int((mm.index>MESACT).sum())}
B=P[P.es_bolsa==1]
E['bolsa']={'v':r2(B[B.mes<=MESACT].venta_mes.sum()),'m':r2(B[B.mes<=MESACT].meta_mes.sum()),
            'man':r2(B.meta_mes.sum()),'vend':int(B[B.meta_mes>0].vendedor_nombre.nunique())}
BH=[{'n':h2['n'],'v':h2['va'],'vend':v} for v,d in OUT.items() for c in d['cli'] if c.get('b') for h2 in c.get('hijos',[]) if h2['va']>0]
E['nuevos']={'n':len(BH),'vend':len(set(b['vend'] for b in BH)),'top':sorted(BH,key=lambda b:-b['v'])[:20]}
P8=P[P.mes<=MESACT]
gc=P8.groupby('cliente_nombre').venta_mes.sum().sort_values(ascending=False); gc=gc[gc>0]; T=gc.sum()
E['conc']={'n':int(len(gc)),'tot':r2(T),
  'top':[{'n':cl(i)[:42],'v':r2(z),'p':round(z/T*100,1)} for i,z in gc.head(15).items()],
  'acum':{str(n):round(gc.head(n).sum()/T*100,1) for n in [1,3,5,10,20]}}
fu=[{'n':f['n'],'v':f['v'],'ult':f['ult'],'vend':v} for v,d in OUT.items() for f in d['fuga']]
E['fuga']=sorted(fu,key=lambda f:-f['v'])[:25]
E['fugaT']={'n':len(fu),'v':r2(sum(f['v'] for f in fu))}
CA=S['Cartera']; cols=['corriente','d0_30','d31_60','d61_90','d90_mas']
E['cart']={'rangos':[r2(CA[c].sum()) for c in cols],'tot':r2(CA[cols].sum().sum())}
gca=CA.groupby(['cliente_nombre','vn'],as_index=False).agg(**{k:(k,'sum') for k in cols},dias=('DiasVencidos','max'))
gca['venc']=gca.d61_90+gca.d90_mas; gca['t']=gca[cols].sum(axis=1)
E['cartTop']=[{'n':cl(r.cliente_nombre)[:42],'vend':cl(r.vn),'venc':r2(r.venc),'t':r2(r.t),'dias':int(r.dias)}
              for _,r in gca[gca.venc>0].sort_values('venc',ascending=False).head(12).iterrows()]
E['incob']={'n':int((CA.DiasVencidos>1000).sum()),'v':r2(CA[CA.DiasVencidos>1000][cols].sum().sum())}
EN=S['Entregas']
ge=EN.groupby('cliente_nombre').cumple.agg(['sum','size']); ge=ge[ge['size']>=4].copy(); ge['p']=ge['sum']/ge['size']*100
E['entCli']=[{'n':cl(i)[:42],'ok':int(r['sum']),'t':int(r['size']),'p':round(r.p,1)} for i,r in ge.sort_values('p').head(12).iterrows()]
E['entT']={'ok':int((EN.cumple==1).sum()),'t':int(len(EN))}
_en_bu_t=sum(d['en']['t'] for d in OUT.values()); _en_bu_ok=sum(d['en']['ok'] for d in OUT.values())
if _en_bu_t!=E['entT']['t'] or _en_bu_ok!=E['entT']['ok']:
    aviso('critico', f"Entregas: la suma por vendedor ({_en_bu_ok}/{_en_bu_t}) no cuadra con el total de «Entregas» ({E['entT']['ok']}/{E['entT']['t']}).")
OC=S['Oport cerradas'].copy(); OC['fc']=pd.to_datetime(OC.fecha_cierre); OC['fa']=pd.to_datetime(OC.fecha_alta)
OA=S['Oport abiertas'].copy(); OA['fa']=pd.to_datetime(OA.fecha_alta)
conv={}
for lbl,i0 in [('s',INI),('m',pd.Timestamp(FIN.year,MESACT,1)),('a',pd.Timestamp(FIN.year,1,1))]:
    ce=OC[(OC.fc>=i0)&(OC.fc<=FIN)]; gan=ce[ce.resultado=='OP Concluida']; per=ce[ce.resultado=='Perdido']
    em=int(((OA.fa>=i0)&(OA.fa<=FIN)).sum()+((OC.fa>=i0)&(OC.fa<=FIN)).sum())
    conv[lbl]={'em':em,'ce':int(len(ce)),'g':int(len(gan)),'p':int(len(per)),
      'tc':round(len(gan)/len(ce)*100,1) if len(ce) else 0,'vg':r2(gan.importe.sum()),'vp':r2(per.importe.sum()),
      'tv':round(gan.importe.sum()/(gan.importe.sum()+per.importe.sum())*100,1) if (len(ce) and (gan.importe.sum()+per.importe.sum())) else 0,
      'mot':[{'n':cl(a_)[:44],'c':int(b_),'v':r2(per[per.motivo_rechazo==a_].importe.sum())}
             for a_,b_ in per.motivo_rechazo.value_counts().items()]}
E['conv']=conv
E['pipe']={'n':int(len(OA)),'v':r2(OA[OA.importe>1].importe.sum()),'sin':int((OA.importe<=1).sum()),
  'det':sum(1 for d in OUT.values() for o in d['ab'] if o['ds'] is not None and o['ds']>21),
  'detv':r2(sum(o['v'] for d in OUT.values() for o in d['ab'] if o['ds'] is not None and o['ds']>21))}
E['ped']={'n':sum(len(d['ped']) for d in OUT.values()),'v':r2(sum(o['v'] for d in OUT.values() for o in d['ped']))}
AC=S['Actividades']
E['act']={'n':int(len(AC)),'min':int((AC.tieneMinuta==1).sum()),'vend':int(AC.vn.nunique()),
          'real':int((AC.estatus=='Realizada').sum())}
_act_bu=sum(d['act']['ano'] for d in OUT.values())
if _act_bu!=E['act']['real']:
    aviso('critico', f"Actividades realizadas: la suma por vendedor ({_act_bu}) no cuadra con el total de «Actividades» ({E['act']['real']}).")
MESN=['','enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
E['fin']=str(FIN.date()); E['ini']=str(INI.date()); E['sem']=SEM; E['mes']=MESACT
E['lbl']={'sem':'Semana '+SEM.split('-W')[1],
          'mes':MESN[MESACT].capitalize()+' '+str(FIN.year),
          'acu':'Acumulado enero–'+MESN[MESACT],
          'ano':'Enero–'+MESN[MESACT]+' '+str(FIN.year),
          'sig':MESN[MESACT+1] if MESACT<12 else 'enero',
          'rango':str(INI.day)+'–'+str(FIN.day)+' '+MESN[MESACT][:3]+' '+str(FIN.year)}

# reconciliaciones cruzadas: suma por vendedor contra el total de la empresa
_bolsa_bu=round(sum(c['va'] for _d in OUT.values() for c in _d['cli'] if c.get('b')),2)
if abs(_bolsa_bu-E['bolsa']['v'])>max(50,E['bolsa']['v']*0.005):
    aviso('critico', f"Bolsa de clientes nuevos: la suma por vendedor ({_bolsa_bu:,.0f}) no cuadra con el total de la empresa ({E['bolsa']['v']:,.0f}).")
_cart_bu=round(sum(sum(c['r']) for _d in OUT.values() for c in _d['car']),2)
if abs(_cart_bu-E['cart']['tot'])>max(500,E['cart']['tot']*0.005):
    aviso('critico', f"Cartera: la suma por vendedor ({_cart_bu:,.0f}) no cuadra con el total de la hoja Cartera ({E['cart']['tot']:,.0f}).")
E['avisos']=AVISOS

TPL=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'plantilla.html')).read()
os.makedirs(SAL,exist_ok=True)
# «public» es EXCLUSIVAMENTE lo que se sube al hosting público (su contenido va en BASE_URL):
# public/<año>/<semana>/<token>/index.html, una carpeta por semana que se acumula sin pisar las
# anteriores. Nada más de esta carpeta (avisos-*.json, reportes/ con nombres legibles)
# debe salir de aquí ni subirse a htdocs.
# «reportes» sigue el mismo patrón (reportes/<año>/<semana>/reporte-<vendedor>.html) para uso interno.
ANIO_ISO,NSEM=SEM.split('-W')
RUTA_SEM=f'{ANIO_ISO}/{NSEM}'
PUB=os.path.join(SAL,'public',ANIO_ISO,NSEM)
REP=os.path.join(SAL,'reportes',ANIO_ISO,NSEM)
os.makedirs(PUB,exist_ok=True); os.makedirs(REP,exist_ok=True)
import unicodedata,re as _re
def slug(s):
    s=''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
    return _re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
def escribir(nom,payload):
    ruta=os.path.join(REP,nom)
    open(ruta,'w').write(TPL.replace('__DATA__',json.dumps(payload,ensure_ascii=False,separators=(',',':'))))
    return ruta
def escribir_pub(token,payload):
    # una carpeta por token con index.html, para que la liga quede …/<token>/ sin .html
    os.makedirs(os.path.join(PUB,token),exist_ok=True)
    ruta=os.path.join(PUB,token,'index.html')
    open(ruta,'w').write(TPL.replace('__DATA__',json.dumps(payload,ensure_ascii=False,separators=(',',':'))))
    return ruta
BASE_URL=os.environ.get('BASE_URL','').rstrip('/')
_liga=lambda t: (BASE_URL+'/' if BASE_URL else '<BASE_URL>/')+f'{RUTA_SEM}/{t}/'

gen=escribir('reporte-direccion.html',{'V':OUT,'E':E})
escribir_pub(TOKENS['__direccion__'],{'V':OUT,'E':E})
print('General (archivo interno):',gen)
print('General (liga de la semana):',_liga(TOKENS['__direccion__']))
n=0
LIGAS=[('Dirección (vista general)', os.environ.get('DIRECCION_CORREO',''), _liga(TOKENS['__direccion__']))]
for v,d in OUT.items():
    if v=='CARTERA SIN ASIGNAR': continue
    escribir(f'reporte-{slug(v)}.html',{'V':{v:d},'E':E,'solo':v})
    escribir_pub(TOKENS[v],{'V':{v:d},'E':E,'solo':v})
    hh=H[H.vn==v]; _c=hh.iloc[0].vendedor_correo if len(hh) else None
    correo=(str(_c).strip() if pd.notna(_c) and str(_c).strip() else '')
    LIGAS.append((v,correo,_liga(TOKENS[v]))); n+=1
print(f'Individuales: {n} archivos en {REP} (y sus ligas de la semana en {PUB}, listos para subir)')
print('OK · acum {:,.0f}/{:,.0f} = {:.1f}%'.format(E['acum']['v'],E['acum']['m'],E['acum']['v']/E['acum']['m']*100))
print('cartera {:,.0f} | pipeline {:,.0f} | fuga {} clientes'.format(E['cart']['tot'],E['pipe']['v'],E['fugaT']['n']))
print('conversion año: conteo {}% importe {}%'.format(E['conv']['a']['tc'],E['conv']['a']['tv']))
print('actividades: {} ({} con minuta) en {} vendedores'.format(E['act']['n'],E['act']['min'],E['act']['vend']))

open(os.path.join(SAL,f'avisos-{SEM}.json'),'w').write(json.dumps(AVISOS,ensure_ascii=False,indent=2))
if AVISOS:
    print(f"\n{len(AVISOS)} aviso(s) de datos — ver avisos-{SEM}.json y la vista de dirección del reporte.")
else:
    print('\nSin avisos de datos esta semana.')

import csv
with open(os.path.join(SAL,f'ligas-{SEM}.csv'),'w',newline='') as _f:
    _w=csv.writer(_f); _w.writerow(['vendedor','correo','liga'])
    for v,correo,liga in LIGAS: _w.writerow([v,correo,liga])

print(f'\nLigas de la semana {ANIO_ISO}/{NSEM} por vendedor (cambian cada semana; mandar las de este CSV):')
_sin_correo=[]
for v,correo,liga in LIGAS:
    print(f'  {v}: {liga}' + (f'  [{correo}]' if correo else ''))
    if not correo: _sin_correo.append(v)
print(f'(también guardado en ligas-{SEM}.csv, con columna de correo para armar el envío)')
if _sin_correo:
    print(f'  Sin correo en Encabezado, buscar a mano: {", ".join(_sin_correo)}')
if not BASE_URL:
    print('  (nota: fija la variable BASE_URL con el dominio real para que las ligas de arriba salgan completas)')

