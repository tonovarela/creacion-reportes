-- Fac Sem Ant

DECLARE @Hoy          DATE = CAST(GETDATE() AS DATE);
DECLARE @LunesActual  DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @Hoy) / 7 * 7, 0);  -- lunes de la semana en curso

DECLARE @FechaFin     DATE = DATEADD(DAY, -1, @LunesActual);   -- domingo anterior
DECLARE @FechaInicio  DATE = DATEADD(DAY, -6, @FechaFin);      -- lunes de esa semana

DECLARE @AnioFiscal   INT = YEAR(@FechaFin);



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