-- Cartera
DECLARE @Hoy          DATE = CAST(GETDATE() AS DATE);
DECLARE @LunesActual  DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @Hoy) / 7 * 7, 0);  -- lunes de la semana en curso

DECLARE @FechaFin     DATE = DATEADD(DAY, -1, @LunesActual);   -- domingo anterior
DECLARE @FechaInicio  DATE = DATEADD(DAY, -6, @FechaFin);      -- lunes de esa semana
--DECLARE @SemanaISO    VARCHAR(8) = CONCAT(YEAR(@FechaFin), '-W', DATEPART(ISO_WEEK, @FechaFin));
--DECLARE @AnioFiscal   INT = YEAR(@FechaFin);
--DECLARE @MesActual    INT = MONTH(@FechaFin);

SELECT
    isnull(v.alias, 'SIN AGENTE')  vendedor_nombre,
    ca.cliente cliente,
    ca.nombre cliente_nombre,
	ca.Vencimiento,
	ca.FecUltCobro, ca.ImpUltCobro,
	ca.MovID,  
	--ca.DiasVencidos, 
	datediff(day,ca.Vencimiento, @FechaFin) as DiasVencidos, 

    SUM(CASE WHEN DATEDIFF(DAY, ca.vencimiento, @FechaFin) < 0  THEN ca.TotalSaldo ELSE 0 END) AS corriente,
    SUM(CASE WHEN DATEDIFF(DAY, ca.vencimiento, @FechaFin) BETWEEN 0  AND 30 THEN ca.TotalSaldo ELSE 0 END) AS d0_30,
    SUM(CASE WHEN DATEDIFF(DAY, ca.vencimiento, @FechaFin) BETWEEN 31 AND 60 THEN ca.TotalSaldo ELSE 0 END) AS d31_60,
    SUM(CASE WHEN DATEDIFF(DAY, ca.vencimiento, @FechaFin) BETWEEN 61 AND 90 THEN ca.TotalSaldo ELSE 0 END) AS d61_90,
    SUM(CASE WHEN DATEDIFF(DAY, ca.vencimiento, @FechaFin) > 90 THEN ca.TotalSaldo ELSE 0 END) AS d90_mas
 FROM v_AntiguedadCxC ca
left join v_CatAgentes v on v.id_Agente = ca.agente
where mov in ('Factura Electronica', 'FActura Com Ext')
GROUP BY v.alias, agente, ca.MovID,  ca.Vencimiento, ca.cliente, ca.nombre, ca.DiasVencidos,ca.FecUltCobro, ca.ImpUltCobro;
