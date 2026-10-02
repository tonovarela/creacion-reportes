-- Fac Sem Ant

DECLARE @FechaEjecucion DATE = CAST(GETDATE() AS DATE);  -- prueba: CAST('2026-10-02' AS DATE)
DECLARE @Hoy          DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @FechaEjecucion) / 7 * 7 + 6, 0);  -- domingo de la semana en curso

DECLARE @FechaFin     DATE = @Hoy;                             -- domingo de la semana en curso
DECLARE @FechaInicio  DATE = DATEADD(DAY, -6, @FechaFin);      -- lunes de la semana en curso
DECLARE @SemanaISO    VARCHAR(8) = CONCAT(YEAR(@FechaFin), '-W', DATEPART(ISO_WEEK, @FechaFin));
DECLARE @AnioFiscal   INT = YEAR(@FechaFin);
DECLARE @MesActual    INT = MONTH(@FechaFin);




Select 
isnull(a.alias, 'SIN AGENTE')  vendedor_nombre, 
v.año, concat(year(fechaEmision), '-W', datepart(ISO_WEEK, fechaEmision) ) as numsemana, 
v.mov, v.movid,  v.cliente, v.nombrecliente, v.fechaemision,  sum(v.importeP) venta
from etl_mstr.dbo.etl_VtasHist v
left join v_CatAgentes a on a.id_Agente = v.Agente 
where v.año =  @AnioFiscal
	AND datepart(wk,v.FechaEmision) = datepart(wk, @FechaInicio)
	AND year(v.FechaEmision) = year(@FechaInicio)
group by v.año, v.numsemana, v.mov, v.movid, v.agente, a.Alias, v.cliente, v.nombrecliente, v.fechaemision
order by v.FechaEmision