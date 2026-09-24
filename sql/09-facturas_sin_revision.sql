
--Fact Sin Rev
SELECT
 	isnull(a.alias, 'SIN AGENTE')  vendedor_nombre,
	f.MovID as folio,
    f.cliente cliente,
    f.nombreCte cliente_nombre,
    convert(date,f.fechaEmision) fechaEmision,
    f.saldo
FROM etl_mstr.dbo.v_AntiguedadCxCST f
left join  v_catAgentes a on a.id_Agente = f.Agente
Where f.Situacion='NO INGRESADA'
and f.EstatusCxC not in ('1.0-30')
GO