-- Entregas

DECLARE @FechaEjecucion DATE = CAST(GETDATE() AS DATE);  -- prueba: CAST('2026-10-02' AS DATE)
DECLARE @Hoy          DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @FechaEjecucion) / 7 * 7 + 6, 0);  -- domingo de la semana en curso

DECLARE @FechaFin     DATE = @Hoy;                             -- domingo de la semana en curso
DECLARE @FechaInicio  DATE = DATEADD(DAY, -6, @FechaFin);      -- lunes de la semana en curso
DECLARE @SemanaISO    VARCHAR(8) = CONCAT(YEAR(@FechaFin), '-W', DATEPART(ISO_WEEK, @FechaFin));
DECLARE @AnioFiscal   INT = YEAR(@FechaFin);
DECLARE @MesActual    INT = MONTH(@FechaFin);



SELECT
	isnull(v.alias, 'SIN AGENTE')  vendedor_nombre,
	CONCAT(YEAR(e.fecIniXEntregar), '-W', DATEPART(ISO_WEEK, e.fecIniXEntregar))  AS semana_iso,
    e.numOrden AS op,
    e.idClienteINT cliente,
    e.cliente cliente_nombre,
    convert(date,e.fecIniXEntregar) fecha_compromiso_original,  
    convert(date,e.fecPriEntrega) fecha_entrega, 
    E.valido cumple  
FROM v_Entregas e
left join v_CtesProspectos c on c.id = e.idClienteINT
left join v_CatAgentes v on v.id_Agente = c.agente
WHERE YEAR(e.fecIniXEntregar) = @AnioFiscal