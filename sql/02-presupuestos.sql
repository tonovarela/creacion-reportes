--Presupuesto
/* =====================================================================
   2. presupuesto.csv - un renglón por vendedor + cliente
   ===================================================================== */

DECLARE @Hoy          DATE = CAST(GETDATE() AS DATE);
DECLARE @LunesActual  DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @Hoy) / 7 * 7, 0);  -- lunes de la semana en curso

DECLARE @FechaFin     DATE = DATEADD(DAY, -1, @LunesActual);   -- domingo anterior
DECLARE @FechaInicio  DATE = DATEADD(DAY, -6, @FechaFin);      -- lunes de esa semana
DECLARE @SemanaISO    VARCHAR(8) = CONCAT(YEAR(@FechaFin), '-W', DATEPART(ISO_WEEK, @FechaFin));
DECLARE @AnioFiscal   INT = YEAR(@FechaFin);
DECLARE @MesActual    INT = MONTH(@FechaFin);

SELECT
    isnull(a.Alias,'SIN AGENTE') vendedor_nombre,
	p.idCliente cliente,   
	isnull(c.razonsocial, '------------') cliente_nombre,
	p.tipo, 
	p.año, p.mes, 
	sum(p.vta) venta_mes, 
	sum(p.meta) meta_mes, 
    iif(p.tipo = 'Cliente Nuevo', 1,0) es_bolsa
FROM etl_mstr.dbo.etl_VtaVSMetaMEs p
left join v_CatAgentes a on a.id_Agente = p.Agente
left join v_CtesProspectos c on c.id = p.idCliente
where p.año = @AnioFiscal 
group by a.alias, p.idCliente, c.razonsocial, p.año , P.mes, p.tipo