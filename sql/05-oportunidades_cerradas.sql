-- Oport cerradas
DECLARE @FechaEjecucion DATE = CAST(GETDATE() AS DATE);  -- prueba: CAST('2026-10-02' AS DATE)
DECLARE @Hoy          DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @FechaEjecucion) / 7 * 7 + 6, 0);  -- domingo de la semana en curso

DECLARE @FechaFin     DATE = @Hoy;                             -- domingo de la semana en curso
DECLARE @FechaInicio  DATE = DATEADD(DAY, -6, @FechaFin);      -- lunes de la semana en curso
DECLARE @SemanaISO    VARCHAR(8) = CONCAT(YEAR(@FechaFin), '-W', DATEPART(ISO_WEEK, @FechaFin));
DECLARE @AnioFiscal   INT = YEAR(@FechaFin);
DECLARE @MesActual    INT = MONTH(@FechaFin);


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
