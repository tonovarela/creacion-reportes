
--Actividades
DECLARE @FechaEjecucion DATE = CAST(GETDATE() AS DATE);  -- prueba: CAST('2026-10-02' AS DATE)
DECLARE @Hoy          DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @FechaEjecucion) / 7 * 7 + 6, 0);  -- domingo de la semana en curso

DECLARE @FechaFin     DATE = @Hoy;                             -- domingo de la semana en curso
DECLARE @FechaInicio  DATE = DATEADD(DAY, -6, @FechaFin);      -- lunes de la semana en curso
DECLARE @SemanaISO    VARCHAR(8) = CONCAT(YEAR(@FechaFin), '-W', DATEPART(ISO_WEEK, @FechaFin));
DECLARE @AnioFiscal   INT = YEAR(@FechaFin);
DECLARE @MesActual    INT = MONTH(@FechaFin);


SELECT distinct
    isnull(v.alias, 'SIN AGENTE')  vendedor_nombre,
	a.fecha,
    COALESCE(c.id, '') AS cliente,	
    c.razonSocial cliente_nombre,   
    a.tipocli   tipoCliente,        
    a.tipo tipo_actividad,			
    a.estatus,						
	a.tieneMinuta
FROM v_Actividades a
left join v_CtesProspectos c on c.id = a.id
left join v_CatAgentes v on v.id_Agente = a.alias
WHERE
    a.estatus in ('Realizada', 'Planificada') 
	and year(a.fecha) = @AnioFiscal