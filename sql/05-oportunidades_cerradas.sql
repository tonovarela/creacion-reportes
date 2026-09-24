-- Oport cerradas
DECLARE @Hoy          DATE = CAST(GETDATE() AS DATE);
DECLARE @LunesActual  DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @Hoy) / 7 * 7, 0);  -- lunes de la semana en curso
DECLARE @FechaFin     DATE = DATEADD(DAY, -1, @LunesActual);   -- domingo anterior
DECLARE @AnioFiscal   INT = YEAR(@FechaFin);

SELECT distinct
    isnull(a.alias, 'SIN AGENTE')  vendedor_nombre,
    oc.folio oportunidad_id,
	COALESCE(c.id, '')  AS cliente, 
    oc.razonSocial cliente_nombre,
    convert(date, oc.fecCreacion) fecha_alta,
    oc.fecResultadoF fecha_cierre,
    oc.descEstatus resultado,                                 
    COALESCE(oc.descMotivoPErdida, '')  AS motivo_rechazo,    
    oc.valor importe
FROM v_Oportunidades oc
left join v_CtesProspectos c on c.idCandy = oc.idCliente
left join v_CatAgentes a on a.id_Agente = oc.cveAgente
WHERE oc.descEstatus IN ('OP Concluida', 'Perdido')
and YEAR(oc.fecResultadoF) = @AnioFiscal;
